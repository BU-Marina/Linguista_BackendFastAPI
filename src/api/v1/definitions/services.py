"""Definitions services."""

from __future__ import annotations
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.searching import apply_search
from api.v1.utils.ordering import apply_ordering
from api.v1.utils.pagination import build_pagination_links
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
    # Get definitions from user's words (not directly from Definition)
    stmt = (
        select(Definition)
        .join(WordDefinitions, WordDefinitions.definition_id == Definition.id)
        .join(Word, Word.id == WordDefinitions.word_id)
        .where(Word.author_id == user_id)
        .distinct()
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
                .where(Collection.id.in_(collections_list), Word.author_id == user_id)
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
                .join(Word, Word.id == WordDefinitions.word_id)
                .where(
                    WordDefinitions.definition_id.in_(definition_ids),
                    Word.author_id == user_id,
                )
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
                .where(
                    WordDefinitions.definition_id.in_(definition_ids),
                    Word.author_id == user_id,
                )
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
        words_count = counts_map.get(r.id, 0)
        other_words_count = max(words_count - len(last_words), 0)
        results.append(
            DefinitionOut(
                id=r.id,
                slug=r.slug,
                text=r.text,
                translation=r.translation,
                language=getattr(r.language, 'isocode', None),
                words_count=words_count,
                other_words_count=other_words_count,
                last_4_words=last_words,
                created=r.created,
                modified=r.modified,
            )
        )

    next_link, previous_link = build_pagination_links(
        base_url='/definitions',
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


async def definition_create_service(
    *,
    session: AsyncSession,
    user_id,
    payload: DefinitionIn,
    models: dict = VOCAB_MODELS,
) -> DefinitionOut:
    Definition = models['Definition']
    Language = models['Language']
    Word = models['Word']
    WordDefinitions = models['WordDefinitions']

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
                            WordDefinitions.word_id, WordDefinitions.definition_id
                        ).where(
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
    await session.refresh(obj)

    # Calculate words_count
    words_count = (
        await session.execute(
            select(func.count())
            .select_from(WordDefinitions)
            .where(WordDefinitions.definition_id == obj.id)
        )
    ).scalar_one() or 0

    return DefinitionOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=payload.language,
        words_count=words_count,
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
    WordDefinitions = models['WordDefinitions']
    Word = models['Word']

    # Check if definition exists and is associated with user's words
    obj = (
        await session.execute(
            select(Definition)
            .join(WordDefinitions, WordDefinitions.definition_id == Definition.id)
            .join(Word, Word.id == WordDefinitions.word_id)
            .where(Definition.id == definition_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Definition not found')

    # Calculate words_count only from user's vocabulary
    words_count = (
        await session.execute(
            select(func.count())
            .select_from(WordDefinitions)
            .join(Word, Word.id == WordDefinitions.word_id)
            .where(WordDefinitions.definition_id == obj.id, Word.author_id == user_id)
        )
    ).scalar_one() or 0

    return DefinitionOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=getattr(obj.language, 'isocode', None),
        words_count=words_count,
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
    WordDefinitions = models['WordDefinitions']
    Word = models['Word']

    # Check if definition exists and is associated with user's words
    obj = (
        await session.execute(
            select(Definition)
            .join(WordDefinitions, WordDefinitions.definition_id == Definition.id)
            .join(Word, Word.id == WordDefinitions.word_id)
            .where(Definition.id == definition_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()

    if not obj:
        raise HTTPException(status_code=404, detail='Definition not found')

    # Check if user is the author of the definition
    is_author = obj.author_id == user_id

    if not is_author:
        # User is not the author - create a new definition and copy word associations
        # Get user's words associated with the original definition
        user_word_ids = (
            (
                await session.execute(
                    select(WordDefinitions.word_id)
                    .join(Word, Word.id == WordDefinitions.word_id)
                    .where(
                        WordDefinitions.definition_id == definition_id,
                        Word.author_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        if not user_word_ids:
            raise HTTPException(
                status_code=404, detail='No words found for this definition'
            )

        lang_id = None
        if payload.language:
            lang_id = (
                await session.execute(
                    select(Language.id).where(Language.isocode == payload.language)
                )
            ).scalar_one_or_none()

        # Create new definition with updated data
        new_definition = Definition(
            text=payload.text,
            translation=payload.translation,
            language_id=lang_id if lang_id is not None else obj.language_id,
            author_id=user_id,
        )
        session.add(new_definition)
        await session.flush()

        # Disconnect user's words from the original definition
        await session.execute(
            delete(WordDefinitions).where(
                WordDefinitions.definition_id == definition_id,
                WordDefinitions.word_id.in_(user_word_ids),
            )
        )

        # Copy word associations for user's words to the new definition
        for word_id in user_word_ids:
            session.add(
                WordDefinitions(word_id=word_id, definition_id=new_definition.id)
            )

        await session.commit()
        await session.refresh(new_definition)

        # Calculate words_count for new definition
        words_count = (
            await session.execute(
                select(func.count())
                .select_from(WordDefinitions)
                .join(Word, Word.id == WordDefinitions.word_id)
                .where(
                    WordDefinitions.definition_id == new_definition.id,
                    Word.author_id == user_id,
                )
            )
        ).scalar_one() or 0

        return DefinitionOut(
            id=new_definition.id,
            slug=new_definition.slug,
            text=new_definition.text,
            translation=new_definition.translation,
            language=payload.language,
            words_count=words_count,
            created=new_definition.created,
            modified=new_definition.modified,
        )
    else:
        # User is the author - update existing definition
        lang_id = None
        if payload.language:
            lang_id = (
                await session.execute(
                    select(Language.id).where(Language.isocode == payload.language)
                )
            ).scalar_one_or_none()
        obj.text = payload.text
        obj.translation = payload.translation
        obj.language_id = lang_id if lang_id is not None else obj.language_id
        await session.commit()
        await session.refresh(obj)

        # Calculate words_count only from user's vocabulary
        words_count = (
            await session.execute(
                select(func.count())
                .select_from(WordDefinitions)
                .join(Word, Word.id == WordDefinitions.word_id)
                .where(
                    WordDefinitions.definition_id == obj.id, Word.author_id == user_id
                )
            )
        ).scalar_one() or 0

    return DefinitionOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=payload.language,
        words_count=words_count,
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

    # Check if definition exists and is associated with user's words
    obj = (
        await session.execute(
            select(Definition)
            .join(WordDefinitions, WordDefinitions.definition_id == Definition.id)
            .join(Word, Word.id == WordDefinitions.word_id)
            .where(Definition.id == definition_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()

    if not obj:
        raise HTTPException(status_code=404, detail='Definition not found')

    # Check if user is the author of the definition
    is_author = obj.author_id == user_id

    if not is_author:
        # User is not the author - just unlink user's words from the definition
        user_word_ids = (
            (
                await session.execute(
                    select(WordDefinitions.word_id)
                    .join(Word, Word.id == WordDefinitions.word_id)
                    .where(
                        WordDefinitions.definition_id == definition_id,
                        Word.author_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        if user_word_ids:
            await session.execute(
                delete(WordDefinitions).where(
                    WordDefinitions.definition_id == definition_id,
                    WordDefinitions.word_id.in_(user_word_ids),
                )
            )
            await session.commit()
        return

    # User is the author - proceed with full deletion
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

    # Explicitly delete join table entries before deleting the definition
    await session.execute(
        delete(WordDefinitions).where(WordDefinitions.definition_id == obj.id)
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
