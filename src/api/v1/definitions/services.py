"""Definitions services."""

from __future__ import annotations
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.searching import apply_search
from api.v1.utils.ordering import apply_ordering
from api.v1.vocabulary.models import VOCAB_MODELS
from .schemas import DefinitionIn, DefinitionOut, PageOut, DefinitionResolveOut


def _params(page, limit, ordering, search):
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


async def definitions_list_service(
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
    Definition = models['Definition']
    WordDefinitions = models['WordDefinitions']
    Word = models['Word']
    WordsInCollections = models['WordsInCollections']
    Collection = models['Collection']

    params = _params(page, limit, ordering, search)
    stmt = (
        select(Definition)
        .where(Definition.author_id == user_id)
        .options(selectinload(Definition.language))
    )
    if collections:
        collections_list = [c for c in collections.split(',') if c]
        if collections_list:
            definition_ids_subq = (
                select(WordDefinitions.definition_id)
                .join(Word, Word.id == WordDefinitions.word_id)
                .join(WordsInCollections, WordsInCollections.word_id == Word.id)
                .join(Collection, Collection.id == WordsInCollections.collection_id)
                .where(Collection.id.in_(collections_list))
                .distinct()
            )
            stmt = stmt.where(Definition.id.in_(definition_ids_subq))
    stmt = apply_search(stmt, Definition, params.search, ['text', 'translation'])
    ordering_map = {
        'text': Definition.text,
        '-text': Definition.text.desc(),
        'created': Definition.created,
        '-created': Definition.created.desc(),
        'modified': Definition.modified,
        '-modified': Definition.modified.desc(),
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
    definition_ids = [r.id for r in rows]
    last_words_map: dict[UUID, list[str]] = {d_id: [] for d_id in definition_ids}
    counts_map: dict[UUID, int] = {d_id: 0 for d_id in definition_ids}
    if definition_ids:
        counts = (
            await session.execute(
                select(WordDefinitions.definition_id, func.count())
                .where(WordDefinitions.definition_id.in_(definition_ids))
                .group_by(WordDefinitions.definition_id)
            )
        ).all()
        counts_map.update({d_id: count for d_id, count in counts})

        assoc_rows = (
            await session.execute(
                select(
                    WordDefinitions.definition_id,
                    Word.text,
                    WordDefinitions.created,
                )
                .join(Word, Word.id == WordDefinitions.word_id)
                .where(WordDefinitions.definition_id.in_(definition_ids))
                .order_by(WordDefinitions.created.desc())
            )
        ).all()
        for d_id, word_text, _created in assoc_rows:
            if len(last_words_map[d_id]) >= 4:
                continue
            last_words_map[d_id].append(word_text)

    results = []
    for r in rows:
        last_words = last_words_map.get(r.id, [])
        other_words_count = max(counts_map.get(r.id, 0) - len(last_words), 0)
        results.append(
            DefinitionOut(
                id=r.id,
                slug=r.slug,
                text=r.text,
                translation=r.translation,
                language=getattr(r.language, 'isocode', None),
                other_words_count=other_words_count,
                last_4_words=last_words,
                created=r.created,
                modified=r.modified,
            )
        )
    return PageOut(page=page, limit=limit, count=total, results=results)


async def definition_create_service(
    *,
    session: AsyncSession,
    user_id,
    payload: DefinitionIn,
    models: dict = VOCAB_MODELS,
) -> DefinitionOut:
    Definition = models['Definition']
    Language = models['Language']
    lang_id = None
    if payload.language:
        lang_id = (
            await session.execute(
                select(Language.id).where(Language.isocode == payload.language)
            )
        ).scalar_one_or_none()
    obj = Definition(
        text=payload.text,
        translation=payload.translation,
        language_id=lang_id,
        author_id=user_id,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return DefinitionOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=payload.language,
        created=obj.created,
        modified=obj.modified,
    )


async def definition_retrieve_service(
    *,
    session: AsyncSession,
    user_id,
    definition_id: UUID,
    models: dict = VOCAB_MODELS,
) -> DefinitionOut:
    Definition = models['Definition']
    obj = (
        await session.execute(
            select(Definition).where(
                Definition.id == definition_id, Definition.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Definition not found')
    return DefinitionOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=getattr(obj.language, 'isocode', None),
        created=obj.created,
        modified=obj.modified,
    )


async def definition_update_service(
    *,
    session: AsyncSession,
    user_id,
    definition_id: UUID,
    payload: DefinitionIn,
    models: dict = VOCAB_MODELS,
) -> DefinitionOut:
    Definition = models['Definition']
    Language = models['Language']
    obj = (
        await session.execute(
            select(Definition).where(
                Definition.id == definition_id, Definition.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Definition not found')
    lang_id = None
    if payload.language:
        lang_id = (
            await session.execute(
                select(Language.id).where(Language.isocode == payload.language)
            )
        ).scalar_one_or_none()
    obj.text = payload.text
    obj.translation = payload.translation
    obj.language_id = lang_id
    await session.commit()
    await session.refresh(obj)
    return DefinitionOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=payload.language,
        created=obj.created,
        modified=obj.modified,
    )


async def definition_delete_service(
    *,
    session: AsyncSession,
    user_id,
    definition_id: UUID,
    delete_words: bool = False,
    models: dict = VOCAB_MODELS,
) -> None:
    Definition = models['Definition']
    Word = models['Word']
    WordDefinitions = models['WordDefinitions']
    obj = (
        await session.execute(
            select(Definition).where(
                Definition.id == definition_id, Definition.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        return
    if delete_words:
        word_ids = (
            (
                await session.execute(
                    select(WordDefinitions.word_id).where(
                        WordDefinitions.definition_id == obj.id
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


async def definition_add_words_service(
    *,
    session: AsyncSession,
    user_id,
    definition_id: UUID,
    word_ids: list[UUID],
    models: dict = VOCAB_MODELS,
) -> DefinitionOut:
    Definition = models['Definition']
    Word = models['Word']
    WordDefinitions = models['WordDefinitions']

    obj = (
        await session.execute(
            select(Definition).where(
                Definition.id == definition_id, Definition.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Definition not found')

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
                select(WordDefinitions.word_id, WordDefinitions.definition_id).where(
                    WordDefinitions.definition_id == obj.id,
                    WordDefinitions.word_id.in_([w.id for w in words]),
                )
            )
        ).all()
    )
    for w in words:
        if (w.id, obj.id) in existing_pairs:
            continue
        session.add(WordDefinitions(word_id=w.id, definition_id=obj.id))

    await session.commit()
    return await definition_retrieve_service(
        session=session, user_id=user_id, definition_id=definition_id, models=models
    )


async def definition_remove_words_service(
    *,
    session: AsyncSession,
    user_id,
    definition_id: UUID,
    word_ids: list[UUID],
    models: dict = VOCAB_MODELS,
) -> DefinitionOut:
    Definition = models['Definition']
    Word = models['Word']
    WordDefinitions = models['WordDefinitions']

    obj = (
        await session.execute(
            select(Definition).where(
                Definition.id == definition_id, Definition.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Definition not found')

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
        delete(WordDefinitions).where(
            WordDefinitions.definition_id == obj.id,
            WordDefinitions.word_id.in_(word_ids),
        )
    )
    await session.commit()
    return await definition_retrieve_service(
        session=session, user_id=user_id, definition_id=definition_id, models=models
    )


async def definition_resolve_slug_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = VOCAB_MODELS,
) -> DefinitionResolveOut:
    Definition = models['Definition']
    row = (
        await session.execute(
            select(Definition.id, Definition.slug).where(
                Definition.slug == slug, Definition.author_id == user_id
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Definition not found')
    return DefinitionResolveOut(id=row.id, slug=row.slug)
