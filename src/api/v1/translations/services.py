"""Translations services."""

from __future__ import annotations
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.ordering import apply_ordering
from api.v1.utils.pagination import build_pagination_links

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
    # Get translations from user's words (not directly from Translation)
    stmt = (
        select(Translation)
        .join(WordTranslations, WordTranslations.translation_id == Translation.id)
        .join(Word, Word.id == WordTranslations.word_id)
        .where(Word.author_id == user_id)
        .distinct()
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
                .where(Collection.id.in_(collections_list), Word.author_id == user_id)
                .distinct()
            )
            stmt = stmt.where(Translation.id.in_(translation_ids_subq))

    # Apply search: translation text, language, and related words text
    if params.search:
        search_term = params.search.strip()
        if search_term:
            pattern = f'%{search_term}%'
            search_conditions = []

            # Search in translation text
            search_conditions.append(Translation.text.ilike(pattern))

            # Search in translation language isocode (via subquery)
            language_subq = (
                select(Translation.id)
                .join(Language, Translation.language_id == Language.id)
                .where(Language.isocode.ilike(pattern))
            )
            search_conditions.append(Translation.id.in_(language_subq))

            # Search in related words text (via subquery) - only from user's words
            words_subq = (
                select(WordTranslations.translation_id)
                .join(Word, Word.id == WordTranslations.word_id)
                .where(Word.text.ilike(pattern), Word.author_id == user_id)
                .distinct()
            )
            search_conditions.append(Translation.id.in_(words_subq))

            if search_conditions:
                stmt = stmt.where(or_(*search_conditions))
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
    last_words_map: dict[UUID, list[str]] = {t_id: [] for t_id in translation_ids}
    counts_map: dict[UUID, int] = {t_id: 0 for t_id in translation_ids}
    if translation_ids:
        counts = (
            await session.execute(
                select(WordTranslations.translation_id, func.count())
                .join(Word, Word.id == WordTranslations.word_id)
                .where(
                    WordTranslations.translation_id.in_(translation_ids),
                    Word.author_id == user_id,
                )
                .group_by(WordTranslations.translation_id)
            )
        ).all()
        counts_map.update({t_id: count for t_id, count in counts})

        assoc_rows = (
            await session.execute(
                select(
                    WordTranslations.translation_id,
                    Word.text,
                    WordTranslations.created,
                )
                .join(Word, Word.id == WordTranslations.word_id)
                .where(
                    WordTranslations.translation_id.in_(translation_ids),
                    Word.author_id == user_id,
                )
                .order_by(WordTranslations.created.desc())
            )
        ).all()
        for t_id, word_text, _created in assoc_rows:
            if len(last_words_map[t_id]) >= 6:
                continue
            last_words_map[t_id].append(word_text)

    results = []
    for row in rows:
        last_words = last_words_map.get(row.id, [])
        words_count = counts_map.get(row.id, 0)
        other_words_count = max(words_count - len(last_words), 0)
        results.append(
            TranslationOut(
                id=row.id,
                slug=row.slug,
                text=row.text,
                language=getattr(row.language, 'isocode', None),
                words_count=words_count,
                other_words_count=other_words_count,
                last_6_words=last_words,
                created=row.created,
                modified=row.modified,
            )
        )

    next_link, previous_link = build_pagination_links(
        base_url='/translations',
        page=page,
        limit=limit,
        total=total,
        query_params={
            'ordering': ordering,
            'search': search,
            'collections': collections,
        },
    )

    return PageOut(
        page=page,
        limit=limit,
        count=total,
        next=next_link,
        previous=previous_link,
        results=results,
    )


async def translation_create_service(
    *,
    session: AsyncSession,
    user_id,
    payload: TranslationIn,
    models: dict = VOCAB_MODELS,
) -> TranslationOut:
    Translation = models['WordTranslation']
    Language = models['Language']
    Word = models['Word']
    WordTranslations = models['WordTranslations']

    lang_id = None
    if payload.language:
        lang_id = (
            await session.execute(
                select(Language.id).where(Language.isocode == payload.language)
            )
        ).scalar_one_or_none()

    obj = Translation(text=payload.text, author_id=user_id, language_id=lang_id)
    session.add(obj)
    await session.flush()

    # Add words if provided
    if payload.words:
        words = (
            (
                await session.execute(
                    select(Word).where(
                        Word.id.in_(payload.words), Word.author_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        if words:
            # Check for existing pairs to avoid duplicates
            existing_pairs = set(
                (
                    await session.execute(
                        select(
                            WordTranslations.word_id, WordTranslations.translation_id
                        ).where(
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
    await session.refresh(obj)

    # Calculate words_count
    words_count = (
        await session.execute(
            select(func.count())
            .select_from(WordTranslations)
            .where(WordTranslations.translation_id == obj.id)
        )
    ).scalar_one() or 0

    return TranslationOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        language=payload.language,
        words_count=words_count,
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
    WordTranslations = models['WordTranslations']
    Word = models['Word']

    # Check if translation exists and is associated with user's words
    obj = (
        await session.execute(
            select(Translation)
            .join(WordTranslations, WordTranslations.translation_id == Translation.id)
            .join(Word, Word.id == WordTranslations.word_id)
            .where(Translation.id == translation_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Translation not found')

    # Calculate words_count only from user's vocabulary
    words_count = (
        await session.execute(
            select(func.count())
            .select_from(WordTranslations)
            .join(Word, Word.id == WordTranslations.word_id)
            .where(WordTranslations.translation_id == obj.id, Word.author_id == user_id)
        )
    ).scalar_one() or 0

    return TranslationOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        language=getattr(obj.language, 'isocode', None),
        words_count=words_count,
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
    WordTranslations = models['WordTranslations']
    Word = models['Word']

    # Check if translation exists and is associated with user's words
    obj = (
        await session.execute(
            select(Translation)
            .join(WordTranslations, WordTranslations.translation_id == Translation.id)
            .join(Word, Word.id == WordTranslations.word_id)
            .where(Translation.id == translation_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()

    if not obj:
        raise HTTPException(status_code=404, detail='Translation not found')

    # Check if user is the author of the translation
    is_author = obj.author_id == user_id

    if not is_author:
        # User is not the author - create a new translation and copy word associations
        # Get user's words associated with the original translation
        user_word_ids = (
            (
                await session.execute(
                    select(WordTranslations.word_id)
                    .join(Word, Word.id == WordTranslations.word_id)
                    .where(
                        WordTranslations.translation_id == translation_id,
                        Word.author_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        if not user_word_ids:
            raise HTTPException(
                status_code=404, detail='No words found for this translation'
            )

        lang_id = None
        if payload.language:
            lang_id = (
                await session.execute(
                    select(Language.id).where(Language.isocode == payload.language)
                )
            ).scalar_one_or_none()

        # Create new translation with updated data
        new_translation = Translation(
            text=payload.text,
            language_id=lang_id if lang_id is not None else obj.language_id,
            author_id=user_id,
        )
        session.add(new_translation)
        await session.flush()

        # Disconnect user's words from the original translation
        await session.execute(
            delete(WordTranslations).where(
                WordTranslations.translation_id == translation_id,
                WordTranslations.word_id.in_(user_word_ids),
            )
        )

        # Copy word associations for user's words to the new translation
        for word_id in user_word_ids:
            session.add(
                WordTranslations(word_id=word_id, translation_id=new_translation.id)
            )

        await session.commit()
        await session.refresh(new_translation)

        # Calculate words_count for new translation
        words_count = (
            await session.execute(
                select(func.count())
                .select_from(WordTranslations)
                .join(Word, Word.id == WordTranslations.word_id)
                .where(
                    WordTranslations.translation_id == new_translation.id,
                    Word.author_id == user_id,
                )
            )
        ).scalar_one() or 0

        return TranslationOut(
            id=new_translation.id,
            slug=new_translation.slug,
            text=new_translation.text,
            language=payload.language,
            words_count=words_count,
            created=new_translation.created,
            modified=new_translation.modified,
        )
    else:
        # User is the author - update existing translation
        lang_id = None
        if payload.language:
            lang_id = (
                await session.execute(
                    select(Language.id).where(Language.isocode == payload.language)
                )
            ).scalar_one_or_none()
        obj.text = payload.text
        obj.language_id = lang_id if lang_id is not None else obj.language_id
        await session.commit()
        await session.refresh(obj)

        # Calculate words_count only from user's vocabulary
        words_count = (
            await session.execute(
                select(func.count())
                .select_from(WordTranslations)
                .join(Word, Word.id == WordTranslations.word_id)
                .where(
                    WordTranslations.translation_id == obj.id, Word.author_id == user_id
                )
            )
        ).scalar_one() or 0

    return TranslationOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        language=payload.language,
        words_count=words_count,
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

    # Check if translation exists and is associated with user's words
    obj = (
        await session.execute(
            select(Translation)
            .join(WordTranslations, WordTranslations.translation_id == Translation.id)
            .join(Word, Word.id == WordTranslations.word_id)
            .where(Translation.id == translation_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()

    if not obj:
        raise HTTPException(status_code=404, detail='Translation not found')

    # Check if user is the author of the translation
    is_author = obj.author_id == user_id

    if not is_author:
        # User is not the author - just unlink user's words from the translation
        user_word_ids = (
            (
                await session.execute(
                    select(WordTranslations.word_id)
                    .join(Word, Word.id == WordTranslations.word_id)
                    .where(
                        WordTranslations.translation_id == translation_id,
                        Word.author_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        if user_word_ids:
            await session.execute(
                delete(WordTranslations).where(
                    WordTranslations.translation_id == translation_id,
                    WordTranslations.word_id.in_(user_word_ids),
                )
            )
            await session.commit()
        return

    # User is the author - proceed with full deletion
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

    # Explicitly delete join table entries before deleting the translation
    await session.execute(
        delete(WordTranslations).where(WordTranslations.translation_id == obj.id)
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
