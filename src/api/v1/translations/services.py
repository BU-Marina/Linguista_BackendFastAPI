"""Translations services."""

from __future__ import annotations
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.searching import apply_search
from api.v1.utils.ordering import apply_ordering

from api.v1.vocabulary.models import VOCAB_MODELS
from .schemas import TranslationIn, TranslationOut, PageOut, TranslationResolveOut


def _make_params(page: int, limit: int, ordering: str | None, search: str | None):
    return type(
        'Params',
        (),
        {
            'page': page,
            'limit': limit,
            'offset': (page - 1) * limit,
            'ordering': ordering,
            'search': search,
        },
    )


async def translations_list_service(
    *,
    session: AsyncSession,
    user_id,
    page: int,
    limit: int,
    ordering: str | None,
    search: str | None,
    models: dict = VOCAB_MODELS,
    collections: str | None = None,
) -> PageOut:
    Translation = models['WordTranslation']
    WordTranslations = models['WordTranslations']
    Word = models['Word']
    WordsInCollections = models['WordsInCollections']
    Collection = models['Collection']
    Language = models['Language']

    params = _make_params(page, limit, ordering, search)
    stmt = (
        select(Translation)
        .where(Translation.author_id == user_id)
        .options(selectinload(Translation.language))
    )
    if collections:
        collections_list = [c for c in collections.split(',') if c]
        if collections_list:
            translation_ids_subq = (
                select(WordTranslations.translation_id)
                .join(Word, Word.id == WordTranslations.word_id)
                .join(WordsInCollections, WordsInCollections.word_id == Word.id)
                .join(Collection, Collection.id == WordsInCollections.collection_id)
                .where(Collection.id.in_(collections_list))
                .distinct()
            )
            stmt = stmt.where(Translation.id.in_(translation_ids_subq))
    stmt = apply_search(stmt, Translation, params.search, ['text'])
    ordering_map = {
        'text': Translation.text,
        '-text': Translation.text.desc(),
        'created': Translation.created,
        '-created': Translation.created.desc(),
        'modified': Translation.modified,
        '-modified': Translation.modified.desc(),
    }
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default='-modified')

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (await session.execute(stmt.offset(params.offset).limit(params.limit)))
        .scalars()
        .all()
    )
    translation_ids = [row.id for row in rows]
    last_words_map: dict[UUID, list[dict]] = {t_id: [] for t_id in translation_ids}
    counts_map: dict[UUID, int] = {t_id: 0 for t_id in translation_ids}
    if translation_ids:
        counts = (
            await session.execute(
                select(WordTranslations.translation_id, func.count())
                .where(WordTranslations.translation_id.in_(translation_ids))
                .group_by(WordTranslations.translation_id)
            )
        ).all()
        counts_map.update({t_id: count for t_id, count in counts})

        assoc_rows = (
            await session.execute(
                select(
                    WordTranslations.translation_id,
                    Word.text,
                    Language.isocode,
                    WordTranslations.created,
                )
                .join(Word, Word.id == WordTranslations.word_id)
                .join(Language, Word.language_id == Language.id)
                .where(WordTranslations.translation_id.in_(translation_ids))
                .order_by(WordTranslations.created.desc())
            )
        ).all()
        for t_id, word_text, lang_isocode, _created in assoc_rows:
            if len(last_words_map[t_id]) >= 6:
                continue
            last_words_map[t_id].append(
                {'text': word_text, 'language__isocode': lang_isocode}
            )

    results = []
    for row in rows:
        last_words = last_words_map.get(row.id, [])
        other_words_count = max(counts_map.get(row.id, 0) - len(last_words), 0)
        results.append(
            TranslationOut(
                id=row.id,
                slug=row.slug,
                text=row.text,
                language=getattr(row.language, 'isocode', None),
                other_words_count=other_words_count,
                last_6_words=last_words,
                created=row.created,
                modified=row.modified,
            )
        )
    return PageOut(page=page, limit=limit, count=total, results=results)


async def translation_create_service(
    *,
    session: AsyncSession,
    user_id,
    payload: TranslationIn,
    models: dict = VOCAB_MODELS,
) -> TranslationOut:
    Translation = models['WordTranslation']
    Language = models['Language']

    lang_id = None
    if payload.language:
        lang_id = (
            await session.execute(
                select(Language.id).where(Language.isocode == payload.language)
            )
        ).scalar_one_or_none()

    obj = Translation(text=payload.text, author_id=user_id, language_id=lang_id)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return TranslationOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        language=payload.language,
        created=obj.created,
        modified=obj.modified,
    )


async def translation_retrieve_service(
    *,
    session: AsyncSession,
    user_id,
    translation_id: UUID,
    models: dict = VOCAB_MODELS,
) -> TranslationOut:
    Translation = models['WordTranslation']
    obj = (
        await session.execute(
            select(Translation).where(
                Translation.id == translation_id, Translation.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Translation not found')
    return TranslationOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        language=getattr(obj.language, 'isocode', None),
        created=obj.created,
        modified=obj.modified,
    )


async def translation_update_service(
    *,
    session: AsyncSession,
    user_id,
    translation_id: UUID,
    payload: TranslationIn,
    models: dict = VOCAB_MODELS,
) -> TranslationOut:
    Translation = models['WordTranslation']
    Language = models['Language']
    obj = (
        await session.execute(
            select(Translation).where(
                Translation.id == translation_id, Translation.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Translation not found')
    lang_id = None
    if payload.language:
        lang_id = (
            await session.execute(
                select(Language.id).where(Language.isocode == payload.language)
            )
        ).scalar_one_or_none()
    obj.text = payload.text
    obj.language_id = lang_id
    await session.commit()
    await session.refresh(obj)
    return TranslationOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        language=payload.language,
        created=obj.created,
        modified=obj.modified,
    )


async def translation_delete_service(
    *,
    session: AsyncSession,
    user_id,
    translation_id: UUID,
    delete_words: bool = False,
    models: dict = VOCAB_MODELS,
) -> None:
    Translation = models['WordTranslation']
    Word = models['Word']
    WordTranslations = models['WordTranslations']
    obj = (
        await session.execute(
            select(Translation).where(
                Translation.id == translation_id, Translation.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        return
    if delete_words:
        word_ids = (
            (
                await session.execute(
                    select(WordTranslations.word_id).where(
                        WordTranslations.translation_id == obj.id
                    )
                )
            )
            .scalars()
            .all()
        )
        if word_ids:
            await session.execute(
                delete(Word).where(
                    and_(Word.id.in_(word_ids), Word.author_id == user_id)
                )
            )
    await session.delete(obj)
    await session.commit()


async def translation_add_words_service(
    *,
    session: AsyncSession,
    user_id,
    translation_id: UUID,
    word_ids: list[UUID],
    models: dict = VOCAB_MODELS,
) -> TranslationOut:
    Translation = models['WordTranslation']
    Word = models['Word']
    WordTranslations = models['WordTranslations']

    obj = (
        await session.execute(
            select(Translation).where(
                Translation.id == translation_id, Translation.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Translation not found')

    words = (
        (
            await session.execute(
                select(Word).where(Word.id.in_(word_ids), Word.author_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    if not words:
        raise HTTPException(status_code=400, detail='No words found')

    existing_pairs = set(
        (
            await session.execute(
                select(WordTranslations.word_id, WordTranslations.translation_id).where(
                    WordTranslations.translation_id == obj.id,
                    WordTranslations.word_id.in_([w.id for w in words]),
                )
            )
        ).all()
    )
    for w in words:
        if (w.id, obj.id) in existing_pairs:
            continue
        session.add(WordTranslations(word_id=w.id, translation_id=obj.id))

    await session.commit()
    return await translation_retrieve_service(
        session=session, user_id=user_id, translation_id=translation_id, models=models
    )


async def translation_remove_words_service(
    *,
    session: AsyncSession,
    user_id,
    translation_id: UUID,
    word_ids: list[UUID],
    models: dict = VOCAB_MODELS,
) -> TranslationOut:
    Translation = models['WordTranslation']
    Word = models['Word']
    WordTranslations = models['WordTranslations']

    obj = (
        await session.execute(
            select(Translation).where(
                Translation.id == translation_id, Translation.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Translation not found')

    word_ids = (
        (
            await session.execute(
                select(Word.id).where(Word.id.in_(word_ids), Word.author_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    if not word_ids:
        raise HTTPException(status_code=400, detail='No words found')

    await session.execute(
        delete(WordTranslations).where(
            WordTranslations.translation_id == obj.id,
            WordTranslations.word_id.in_(word_ids),
        )
    )
    await session.commit()
    return await translation_retrieve_service(
        session=session, user_id=user_id, translation_id=translation_id, models=models
    )


async def translation_resolve_slug_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = VOCAB_MODELS,
) -> TranslationResolveOut:
    Translation = models['WordTranslation']
    row = (
        await session.execute(
            select(Translation.id, Translation.slug).where(
                Translation.slug == slug, Translation.author_id == user_id
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Translation not found')
    return TranslationResolveOut(id=row.id, slug=row.slug)
