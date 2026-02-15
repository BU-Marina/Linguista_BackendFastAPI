"""Image associations services."""

from __future__ import annotations
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.utils.ordering import apply_ordering
from api.v1.utils.pagination import build_pagination_links
from api.v1.vocabulary.models import VOCAB_MODELS
from .schemas import ImageIn, ImageOut, PageOut, ImageResolveOut


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


async def images_list_service(
    *,
    session: AsyncSession,
    user_id,
    page: int,
    limit: int,
    ordering: str | None,
    search: str | None,
    collections: str | None = None,
) -> PageOut:
    Image = VOCAB_MODELS['ImageAssociation']
    WordImageAssociations = VOCAB_MODELS['WordImageAssociations']
    Word = VOCAB_MODELS['Word']
    WordsInCollections = VOCAB_MODELS['WordsInCollections']
    Collection = VOCAB_MODELS['Collection']

    params = _params(page, limit, ordering, search)
    # Get images from user's words (not directly from ImageAssociation)
    stmt = (
        select(Image)
        .join(WordImageAssociations, WordImageAssociations.image_id == Image.id)
        .join(Word, Word.id == WordImageAssociations.word_id)
        .where(Word.author_id == user_id)
        .distinct()
    )

    # Apply search on image_url and related words text
    if params.search:
        search_term = params.search.strip()
        if search_term:
            pattern = f'%{search_term}%'
            search_conditions = []

            # Search in image_url
            search_conditions.append(Image.image_url.ilike(pattern))

            # Search in related words text (via subquery)
            words_subq = (
                select(WordImageAssociations.image_id)
                .join(Word, Word.id == WordImageAssociations.word_id)
                .where(Word.author_id == user_id, Word.text.ilike(pattern))
                .distinct()
            )
            search_conditions.append(Image.id.in_(words_subq))

            if search_conditions:
                stmt = stmt.where(or_(*search_conditions))

    # Apply collections filter
    if collections:
        collections_list = [c for c in collections.split(',') if c]
        if collections_list:
            image_ids_subq = (
                select(WordImageAssociations.image_id)
                .join(Word, Word.id == WordImageAssociations.word_id)
                .join(WordsInCollections, WordsInCollections.word_id == Word.id)
                .join(Collection, Collection.id == WordsInCollections.collection_id)
                .where(Word.author_id == user_id, Collection.id.in_(collections_list))
                .distinct()
            )
            stmt = stmt.where(Image.id.in_(image_ids_subq))

    ordering_map = {
        'created': Image.created,
        '-created': Image.created.desc(),
        'modified': Image.modified,
        '-modified': Image.modified.desc(),
    }
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default='-created')

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (await session.execute(stmt.offset(params.offset).limit(params.limit)))
        .scalars()
        .all()
    )
    image_ids = [r.id for r in rows]
    last_words_map: dict[UUID, list[str]] = {i_id: [] for i_id in image_ids}
    counts_map: dict[UUID, int] = {i_id: 0 for i_id in image_ids}
    if image_ids:
        # Count only words from user's vocabulary
        counts = (
            await session.execute(
                select(WordImageAssociations.image_id, func.count())
                .join(Word, Word.id == WordImageAssociations.word_id)
                .where(
                    WordImageAssociations.image_id.in_(image_ids),
                    Word.author_id == user_id,
                )
                .group_by(WordImageAssociations.image_id)
            )
        ).all()
        counts_map.update({i_id: count for i_id, count in counts})

        # Get last words only from user's vocabulary
        assoc_rows = (
            await session.execute(
                select(
                    WordImageAssociations.image_id,
                    Word.text,
                    WordImageAssociations.created,
                )
                .join(Word, Word.id == WordImageAssociations.word_id)
                .where(
                    WordImageAssociations.image_id.in_(image_ids),
                    Word.author_id == user_id,
                )
                .order_by(WordImageAssociations.created.desc())
            )
        ).all()
        for i_id, word_text, _created in assoc_rows:
            if len(last_words_map[i_id]) >= 6:
                continue
            last_words_map[i_id].append(word_text)

    results = []
    for r in rows:
        last_words = last_words_map.get(r.id, [])
        words_count = counts_map.get(r.id, 0)
        other_words_count = max(words_count - len(last_words), 0)
        results.append(
            ImageOut(
                id=r.id,
                image_url=r.image_url,
                width=r.width,
                height=r.height,
                num=r.num,
                words_count=words_count,
                other_words_count=other_words_count,
                last_6_words=last_words,
                created=r.created,
                modified=r.modified,
            )
        )

    next_link, previous_link = build_pagination_links(
        base_url='/images',
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


async def image_create_service(
    *,
    session: AsyncSession,
    user_id,
    payload: ImageIn,
) -> ImageOut:
    Image = VOCAB_MODELS['ImageAssociation']
    Word = VOCAB_MODELS['Word']
    WordImageAssociations = VOCAB_MODELS['WordImageAssociations']

    obj = Image(
        image_url=payload.image_url,
        width=payload.width,
        height=payload.height,
        num=payload.num,
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
                            WordImageAssociations.word_id,
                            WordImageAssociations.image_id,
                        ).where(
                            WordImageAssociations.image_id == obj.id,
                            WordImageAssociations.word_id.in_([w.id for w in words]),
                        )
                    )
                ).all()
            )
            for w in words:
                if (w.id, obj.id) in existing_pairs:
                    continue
                session.add(WordImageAssociations(word_id=w.id, image_id=obj.id))

    await session.commit()
    await session.refresh(obj)

    # Calculate words_count
    words_count = (
        await session.execute(
            select(func.count())
            .select_from(WordImageAssociations)
            .where(WordImageAssociations.image_id == obj.id)
        )
    ).scalar_one() or 0

    return ImageOut(
        id=obj.id,
        image_url=obj.image_url,
        width=obj.width,
        height=obj.height,
        num=obj.num,
        words_count=words_count,
        created=obj.created,
        modified=obj.modified,
    )


async def image_retrieve_service(
    *,
    session: AsyncSession,
    user_id,
    image_id,
) -> ImageOut:
    Image = VOCAB_MODELS['ImageAssociation']
    WordImageAssociations = VOCAB_MODELS['WordImageAssociations']
    Word = VOCAB_MODELS['Word']

    # Check if image is associated with user's words (not directly by author_id)
    obj = (
        await session.execute(
            select(Image)
            .join(WordImageAssociations, WordImageAssociations.image_id == Image.id)
            .join(Word, Word.id == WordImageAssociations.word_id)
            .where(Image.id == image_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Image not found')

    # Calculate words_count only from user's vocabulary
    words_count = (
        await session.execute(
            select(func.count())
            .select_from(WordImageAssociations)
            .join(Word, Word.id == WordImageAssociations.word_id)
            .where(WordImageAssociations.image_id == obj.id, Word.author_id == user_id)
        )
    ).scalar_one() or 0

    return ImageOut(
        id=obj.id,
        image_url=obj.image_url,
        width=obj.width,
        height=obj.height,
        num=obj.num,
        words_count=words_count,
        created=obj.created,
        modified=obj.modified,
    )


async def image_update_service(
    *,
    session: AsyncSession,
    user_id,
    image_id,
    payload: ImageIn,
) -> ImageOut:
    Image = VOCAB_MODELS['ImageAssociation']
    WordImageAssociations = VOCAB_MODELS['WordImageAssociations']
    Word = VOCAB_MODELS['Word']

    # Check if image is associated with user's words
    obj = (
        await session.execute(
            select(Image)
            .join(WordImageAssociations, WordImageAssociations.image_id == Image.id)
            .join(Word, Word.id == WordImageAssociations.word_id)
            .where(Image.id == image_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Image not found')

    # Check if user is the author of the image
    is_author = obj.author_id == user_id

    if not is_author:
        # User is not the author - create a new image and copy word associations
        # Get user's words associated with the original image
        user_word_ids = (
            (
                await session.execute(
                    select(WordImageAssociations.word_id)
                    .join(Word, Word.id == WordImageAssociations.word_id)
                    .where(
                        WordImageAssociations.image_id == image_id,
                        Word.author_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        if not user_word_ids:
            raise HTTPException(status_code=404, detail='No words found for this image')

        # Create new image by copying original data first, then applying patch
        # image_url is required in payload, so always use it
        # For optional fields, use payload value if provided, otherwise use original
        new_image = Image(
            image_url=payload.image_url,
            width=payload.width if payload.width is not None else obj.width,
            height=payload.height if payload.height is not None else obj.height,
            num=payload.num if payload.num is not None else obj.num,
            author_id=user_id,
        )
        session.add(new_image)
        await session.flush()

        # Disconnect user's words from the original image
        await session.execute(
            delete(WordImageAssociations).where(
                WordImageAssociations.image_id == image_id,
                WordImageAssociations.word_id.in_(user_word_ids),
            )
        )

        # Connect user's words to the new image
        for word_id in user_word_ids:
            session.add(WordImageAssociations(word_id=word_id, image_id=new_image.id))

        await session.commit()
        await session.refresh(new_image)

        # Calculate words_count for new image
        words_count = (
            await session.execute(
                select(func.count())
                .select_from(WordImageAssociations)
                .join(Word, Word.id == WordImageAssociations.word_id)
                .where(
                    WordImageAssociations.image_id == new_image.id,
                    Word.author_id == user_id,
                )
            )
        ).scalar_one() or 0

        return ImageOut(
            id=new_image.id,
            image_url=new_image.image_url,
            width=new_image.width,
            height=new_image.height,
            num=new_image.num,
            words_count=words_count,
            created=new_image.created,
            modified=new_image.modified,
        )
    else:
        # User is the author - update existing image (apply patch)
        obj.image_url = payload.image_url
        # For optional fields, only update if provided in payload
        if payload.width is not None:
            obj.width = payload.width
        if payload.height is not None:
            obj.height = payload.height
        if payload.num is not None:
            obj.num = payload.num
        await session.commit()
        await session.refresh(obj)

        # Calculate words_count only from user's vocabulary
        words_count = (
            await session.execute(
                select(func.count())
                .select_from(WordImageAssociations)
                .join(Word, Word.id == WordImageAssociations.word_id)
                .where(
                    WordImageAssociations.image_id == obj.id, Word.author_id == user_id
                )
            )
        ).scalar_one() or 0

        return ImageOut(
            id=obj.id,
            image_url=obj.image_url,
            width=obj.width,
            height=obj.height,
            num=obj.num,
            words_count=words_count,
            created=obj.created,
            modified=obj.modified,
        )


async def image_delete_service(
    *,
    session: AsyncSession,
    user_id,
    image_id,
    delete_words: bool = False,
) -> None:
    Image = VOCAB_MODELS['ImageAssociation']
    Word = VOCAB_MODELS['Word']
    WordImageAssociations = VOCAB_MODELS['WordImageAssociations']

    # Check if image exists and is associated with user's words
    obj = (
        await session.execute(
            select(Image)
            .join(WordImageAssociations, WordImageAssociations.image_id == Image.id)
            .join(Word, Word.id == WordImageAssociations.word_id)
            .where(Image.id == image_id, Word.author_id == user_id)
            .distinct()
        )
    ).scalar_one_or_none()

    if not obj:
        raise HTTPException(status_code=404, detail='Image not found')

    # Check if user is the author of the image
    is_author = obj.author_id == user_id

    if not is_author:
        # User is not the author - just unlink user's words from the image
        user_word_ids = (
            (
                await session.execute(
                    select(WordImageAssociations.word_id)
                    .join(Word, Word.id == WordImageAssociations.word_id)
                    .where(
                        WordImageAssociations.image_id == image_id,
                        Word.author_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        if user_word_ids:
            await session.execute(
                delete(WordImageAssociations).where(
                    WordImageAssociations.image_id == image_id,
                    WordImageAssociations.word_id.in_(user_word_ids),
                )
            )
            await session.commit()
        return

    # User is the author - proceed with full deletion
    if delete_words:
        word_ids = (
            (
                await session.execute(
                    select(WordImageAssociations.word_id).where(
                        WordImageAssociations.image_id == obj.id
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

    # Explicitly delete join table entries before deleting the image
    await session.execute(
        delete(WordImageAssociations).where(WordImageAssociations.image_id == obj.id)
    )

    await session.delete(obj)
    await session.commit()


async def image_add_words_service(
    *,
    session: AsyncSession,
    user_id,
    image_id,
    word_ids: list[UUID],
) -> ImageOut:
    Image = VOCAB_MODELS['ImageAssociation']
    Word = VOCAB_MODELS['Word']
    WordImageAssociations = VOCAB_MODELS['WordImageAssociations']

    img = (
        await session.execute(
            select(Image).where(Image.id == image_id, Image.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail='Image not found')

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
                select(
                    WordImageAssociations.word_id, WordImageAssociations.image_id
                ).where(
                    WordImageAssociations.image_id == img.id,
                    WordImageAssociations.word_id.in_([w.id for w in words]),
                )
            )
        ).all()
    )

    for w in words:
        if (w.id, img.id) in existing_pairs:
            continue
        session.add(WordImageAssociations(word_id=w.id, image_id=img.id))

    await session.commit()
    return await image_retrieve_service(
        session=session, user_id=user_id, image_id=image_id
    )


async def image_remove_words_service(
    *,
    session: AsyncSession,
    user_id,
    image_id,
    word_ids: list[UUID],
) -> ImageOut:
    Image = VOCAB_MODELS['ImageAssociation']
    Word = VOCAB_MODELS['Word']
    WordImageAssociations = VOCAB_MODELS['WordImageAssociations']

    img = (
        await session.execute(
            select(Image).where(Image.id == image_id, Image.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail='Image not found')

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
        delete(WordImageAssociations).where(
            WordImageAssociations.image_id == img.id,
            WordImageAssociations.word_id.in_(word_ids),
        )
    )
    await session.commit()
    return await image_retrieve_service(
        session=session, user_id=user_id, image_id=image_id
    )


async def image_resolve_slug_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = VOCAB_MODELS,
) -> ImageResolveOut:
    Image = models['ImageAssociation']
    row = (
        await session.execute(
            select(Image.id, Image.slug).where(
                Image.slug == slug, Image.author_id == user_id
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Image not found')
    return ImageResolveOut(id=row.id, slug=row.slug)
