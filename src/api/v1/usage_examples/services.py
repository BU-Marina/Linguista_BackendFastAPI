"""Usage examples services."""

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
from .schemas import ExampleIn, ExampleOut, PageOut, ExampleResolveOut


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


async def examples_list_service(
    *,
    session: AsyncSession,
    user_id,
    page: int,
    limit: int,
    ordering: str | None,
    search: str | None,
    collections: str | None = None,
) -> PageOut:
    Example = VOCAB_MODELS['UsageExample']
    WordUsageExamples = VOCAB_MODELS['WordUsageExamples']
    Word = VOCAB_MODELS['Word']
    WordsInCollections = VOCAB_MODELS['WordsInCollections']
    Collection = VOCAB_MODELS['Collection']

    params = _params(page, limit, ordering, search)
    # Get examples from user's words (not directly from Example)
    stmt = (
        select(Example)
        .join(WordUsageExamples, WordUsageExamples.example_id == Example.id)
        .join(Word, Word.id == WordUsageExamples.word_id)
        .where(Word.author_id == user_id)
        .distinct()
        .options(selectinload(Example.language))
    )
    if collections:
        collections_list = [c for c in collections.split(',') if c]
        if collections_list:
            example_ids_subq = (
                select(WordUsageExamples.example_id)
                .join(Word, Word.id == WordUsageExamples.word_id)
                .join(WordsInCollections, WordsInCollections.word_id == Word.id)
                .join(Collection, Collection.id == WordsInCollections.collection_id)
                .where(Collection.id.in_(collections_list), Word.author_id == user_id)
                .distinct()
            )
            stmt = stmt.where(Example.id.in_(example_ids_subq))
    stmt = apply_search(
        stmt, Example, params.search, ['text', 'translation', 'source_name']
    )
    ordering_map = {
        'text': Example.text,
        '-text': Example.text.desc(),
        'created': Example.created,
        '-created': Example.created.desc(),
        'modified': Example.modified,
        '-modified': Example.modified.desc(),
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
    example_ids = [r.id for r in rows]
    last_words_map: dict[UUID, list[str]] = {e_id: [] for e_id in example_ids}
    counts_map: dict[UUID, int] = {e_id: 0 for e_id in example_ids}
    if example_ids:
        counts = (
            await session.execute(
                select(WordUsageExamples.example_id, func.count())
                .join(Word, Word.id == WordUsageExamples.word_id)
                .where(
                    WordUsageExamples.example_id.in_(example_ids),
                    Word.author_id == user_id,
                )
                .group_by(WordUsageExamples.example_id)
            )
        ).all()
        counts_map.update({e_id: count for e_id, count in counts})

        assoc_rows = (
            await session.execute(
                select(
                    WordUsageExamples.example_id,
                    Word.text,
                    WordUsageExamples.created,
                )
                .join(Word, Word.id == WordUsageExamples.word_id)
                .where(
                    WordUsageExamples.example_id.in_(example_ids),
                    Word.author_id == user_id,
                )
                .order_by(WordUsageExamples.created.desc())
            )
        ).all()
        for e_id, word_text, _created in assoc_rows:
            if len(last_words_map[e_id]) >= 4:
                continue
            last_words_map[e_id].append(word_text)

    results = []
    for r in rows:
        last_words = last_words_map.get(r.id, [])
        words_count = counts_map.get(r.id, 0)
        other_words_count = max(words_count - len(last_words), 0)
        results.append(
            ExampleOut(
                id=r.id,
                slug=r.slug,
                text=r.text,
                translation=r.translation,
                language=getattr(r.language, 'isocode', None),
                source=r.source,
                source_name=r.source_name,
                source_url=r.source_url,
                words_count=words_count,
                other_words_count=other_words_count,
                last_4_words=last_words,
                created=r.created,
                modified=r.modified,
            )
        )

    next_link, previous_link = build_pagination_links(
        base_url='/examples',
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


async def example_create_service(
    *,
    session: AsyncSession,
    user_id,
    payload: ExampleIn,
) -> ExampleOut:
    Example = VOCAB_MODELS['UsageExample']
    Language = VOCAB_MODELS['Language']
    Word = VOCAB_MODELS['Word']
    WordUsageExamples = VOCAB_MODELS['WordUsageExamples']

    lang_id = None
    if payload.language:
        lang_id = (
            await session.execute(
                select(Language.id).where(Language.isocode == payload.language)
            )
        ).scalar_one_or_none()
    obj = Example(
        text=payload.text,
        translation=payload.translation,
        source=payload.source or 'OTH',
        source_name=payload.source_name,
        source_url=payload.source_url,
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
                            WordUsageExamples.word_id, WordUsageExamples.example_id
                        ).where(
                            WordUsageExamples.example_id == obj.id,
                            WordUsageExamples.word_id.in_([w.id for w in words]),
                        )
                    )
                ).all()
            )
            for w in words:
                if (w.id, obj.id) in existing_pairs:
                    continue
                session.add(WordUsageExamples(word_id=w.id, example_id=obj.id))

    await session.commit()
    await session.refresh(obj)

    # Calculate words_count
    words_count = (
        await session.execute(
            select(func.count())
            .select_from(WordUsageExamples)
            .where(WordUsageExamples.example_id == obj.id)
        )
    ).scalar_one() or 0

    return ExampleOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=payload.language,
        source=obj.source,
        source_name=obj.source_name,
        source_url=obj.source_url,
        words_count=words_count,
        created=obj.created,
        modified=obj.modified,
    )


async def example_retrieve_service(
    *,
    session: AsyncSession,
    user_id,
    example_id: UUID,
) -> ExampleOut:
    Example = VOCAB_MODELS['UsageExample']
    WordUsageExamples = VOCAB_MODELS['WordUsageExamples']
    Word = VOCAB_MODELS['Word']

    # Check if example exists and is associated with user's words
    obj = (
        await session.execute(
            select(Example)
            .join(WordUsageExamples, WordUsageExamples.example_id == Example.id)
            .join(Word, Word.id == WordUsageExamples.word_id)
            .where(Example.id == example_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Example not found')

    # Calculate words_count only from user's vocabulary
    words_count = (
        await session.execute(
            select(func.count())
            .select_from(WordUsageExamples)
            .join(Word, Word.id == WordUsageExamples.word_id)
            .where(WordUsageExamples.example_id == obj.id, Word.author_id == user_id)
        )
    ).scalar_one() or 0

    return ExampleOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=getattr(obj.language, 'isocode', None),
        source=obj.source,
        source_name=obj.source_name,
        source_url=obj.source_url,
        words_count=words_count,
        created=obj.created,
        modified=obj.modified,
    )


async def example_update_service(
    *,
    session: AsyncSession,
    user_id,
    example_id: UUID,
    payload: ExampleIn,
) -> ExampleOut:
    Example = VOCAB_MODELS['UsageExample']
    Language = VOCAB_MODELS['Language']
    WordUsageExamples = VOCAB_MODELS['WordUsageExamples']
    Word = VOCAB_MODELS['Word']

    # Check if example exists and is associated with user's words
    obj = (
        await session.execute(
            select(Example)
            .join(WordUsageExamples, WordUsageExamples.example_id == Example.id)
            .join(Word, Word.id == WordUsageExamples.word_id)
            .where(Example.id == example_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()

    if not obj:
        raise HTTPException(status_code=404, detail='Example not found')

    # Check if user is the author of the example
    is_author = obj.author_id == user_id

    if not is_author:
        # User is not the author - create a new example and copy word associations
        # Get user's words associated with the original example
        user_word_ids = (
            (
                await session.execute(
                    select(WordUsageExamples.word_id)
                    .join(Word, Word.id == WordUsageExamples.word_id)
                    .where(
                        WordUsageExamples.example_id == example_id,
                        Word.author_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        if not user_word_ids:
            raise HTTPException(
                status_code=404, detail='No words found for this example'
            )

        lang_id = None
        if payload.language:
            lang_id = (
                await session.execute(
                    select(Language.id).where(Language.isocode == payload.language)
                )
            ).scalar_one_or_none()

        # Create new example with updated data
        new_example = Example(
            text=payload.text,
            translation=payload.translation,
            source=payload.source or obj.source or 'OTH',
            source_name=payload.source_name,
            source_url=payload.source_url,
            language_id=lang_id if lang_id is not None else obj.language_id,
            author_id=user_id,
        )
        session.add(new_example)
        await session.flush()

        # Disconnect user's words from the original example
        await session.execute(
            delete(WordUsageExamples).where(
                WordUsageExamples.example_id == example_id,
                WordUsageExamples.word_id.in_(user_word_ids),
            )
        )

        # Copy word associations for user's words to the new example
        for word_id in user_word_ids:
            session.add(WordUsageExamples(word_id=word_id, example_id=new_example.id))

        await session.commit()
        await session.refresh(new_example)

        # Calculate words_count for new example
        words_count = (
            await session.execute(
                select(func.count())
                .select_from(WordUsageExamples)
                .join(Word, Word.id == WordUsageExamples.word_id)
                .where(
                    WordUsageExamples.example_id == new_example.id,
                    Word.author_id == user_id,
                )
            )
        ).scalar_one() or 0

        return ExampleOut(
            id=new_example.id,
            slug=new_example.slug,
            text=new_example.text,
            translation=new_example.translation,
            language=payload.language,
            source=new_example.source,
            source_name=new_example.source_name,
            source_url=new_example.source_url,
            words_count=words_count,
            created=new_example.created,
            modified=new_example.modified,
        )
    else:
        # User is the author - update existing example
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
        obj.source = payload.source or obj.source
        obj.source_name = payload.source_name
        obj.source_url = payload.source_url
        await session.commit()
        await session.refresh(obj)

        # Calculate words_count only from user's vocabulary
        words_count = (
            await session.execute(
                select(func.count())
                .select_from(WordUsageExamples)
                .join(Word, Word.id == WordUsageExamples.word_id)
                .where(
                    WordUsageExamples.example_id == obj.id, Word.author_id == user_id
                )
            )
        ).scalar_one() or 0

    return ExampleOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=payload.language,
        source=obj.source,
        source_name=obj.source_name,
        source_url=obj.source_url,
        words_count=words_count,
        created=obj.created,
        modified=obj.modified,
    )


async def example_delete_service(
    *,
    session: AsyncSession,
    user_id,
    example_id: UUID,
    delete_words: bool = False,
) -> None:
    Example = VOCAB_MODELS['UsageExample']
    Word = VOCAB_MODELS['Word']
    WordUsageExamples = VOCAB_MODELS['WordUsageExamples']

    # Check if example exists and is associated with user's words
    obj = (
        await session.execute(
            select(Example)
            .join(WordUsageExamples, WordUsageExamples.example_id == Example.id)
            .join(Word, Word.id == WordUsageExamples.word_id)
            .where(Example.id == example_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()

    if not obj:
        raise HTTPException(status_code=404, detail='Example not found')

    # Check if user is the author of the example
    is_author = obj.author_id == user_id

    if not is_author:
        # User is not the author - just unlink user's words from the example
        user_word_ids = (
            (
                await session.execute(
                    select(WordUsageExamples.word_id)
                    .join(Word, Word.id == WordUsageExamples.word_id)
                    .where(
                        WordUsageExamples.example_id == example_id,
                        Word.author_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        if user_word_ids:
            await session.execute(
                delete(WordUsageExamples).where(
                    WordUsageExamples.example_id == example_id,
                    WordUsageExamples.word_id.in_(user_word_ids),
                )
            )
            await session.commit()
        return

    # User is the author - proceed with full deletion
    if delete_words:
        word_ids = (
            (
                await session.execute(
                    select(WordUsageExamples.word_id).where(
                        WordUsageExamples.example_id == obj.id
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

    # Explicitly delete join table entries before deleting the example
    await session.execute(
        delete(WordUsageExamples).where(WordUsageExamples.example_id == obj.id)
    )

    await session.delete(obj)
    await session.commit()


async def example_add_words_service(
    *,
    session: AsyncSession,
    user_id,
    example_id: UUID,
    word_ids: list[UUID],
) -> ExampleOut:
    Example = VOCAB_MODELS['UsageExample']
    Word = VOCAB_MODELS['Word']
    WordUsageExamples = VOCAB_MODELS['WordUsageExamples']

    obj = (
        await session.execute(
            select(Example).where(
                Example.id == example_id, Example.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Example not found')

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
                select(WordUsageExamples.word_id, WordUsageExamples.example_id).where(
                    WordUsageExamples.example_id == obj.id,
                    WordUsageExamples.word_id.in_([w.id for w in words]),
                )
            )
        ).all()
    )

    for w in words:
        if (w.id, obj.id) in existing_pairs:
            continue
        session.add(WordUsageExamples(word_id=w.id, example_id=obj.id))

    await session.commit()
    return await example_retrieve_service(
        session=session, user_id=user_id, example_id=example_id
    )


async def example_remove_words_service(
    *,
    session: AsyncSession,
    user_id,
    example_id: UUID,
    word_ids: list[UUID],
) -> ExampleOut:
    Example = VOCAB_MODELS['UsageExample']
    Word = VOCAB_MODELS['Word']
    WordUsageExamples = VOCAB_MODELS['WordUsageExamples']

    obj = (
        await session.execute(
            select(Example).where(
                Example.id == example_id, Example.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Example not found')

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
        delete(WordUsageExamples).where(
            WordUsageExamples.example_id == obj.id,
            WordUsageExamples.word_id.in_(word_ids),
        )
    )
    await session.commit()
    return await example_retrieve_service(
        session=session, user_id=user_id, example_id=example_id
    )


async def example_resolve_slug_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = VOCAB_MODELS,
) -> ExampleResolveOut:
    Example = models['UsageExample']
    row = (
        await session.execute(
            select(Example.id, Example.slug).where(
                Example.slug == slug, Example.author_id == user_id
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Example not found')
    return ExampleResolveOut(id=row.id, slug=row.slug)
