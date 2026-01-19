"""Image associations services."""

from __future__ import annotations
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.utils.searching import apply_search
from api.v1.utils.ordering import apply_ordering
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
    stmt = select(Image).where(Image.author_id == user_id)
    stmt = apply_search(stmt, Image, params.search, ['image_url'])
    if collections:
        collections_list = [c for c in collections.split(',') if c]
        if collections_list:
            image_ids_subq = (
                select(WordImageAssociations.image_id)
                .join(Word, Word.id == WordImageAssociations.word_id)
                .join(WordsInCollections, WordsInCollections.word_id == Word.id)
                .join(Collection, Collection.id == WordsInCollections.collection_id)
                .where(Collection.id.in_(collections_list))
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
        counts = (
            await session.execute(
                select(WordImageAssociations.image_id, func.count())
                .where(WordImageAssociations.image_id.in_(image_ids))
                .group_by(WordImageAssociations.image_id)
            )
        ).all()
        counts_map.update({i_id: count for i_id, count in counts})

        assoc_rows = (
            await session.execute(
                select(
                    WordImageAssociations.image_id,
                    Word.text,
                    WordImageAssociations.created,
                )
                .join(Word, Word.id == WordImageAssociations.word_id)
                .where(WordImageAssociations.image_id.in_(image_ids))
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
        other_words_count = max(counts_map.get(r.id, 0) - len(last_words), 0)
        results.append(
            ImageOut(
                id=r.id,
                image_url=r.image_url,
                width=r.width,
                height=r.height,
                num=r.num,
                other_words_count=other_words_count,
                last_6_words=last_words,
                created=r.created,
                modified=r.modified,
            )
        )
    return PageOut(page=page, limit=limit, count=total, results=results)


async def image_create_service(
    *,
    session: AsyncSession,
    user_id,
    payload: ImageIn,
) -> ImageOut:
    Image = VOCAB_MODELS['ImageAssociation']
    obj = Image(
        image_url=payload.image_url,
        width=payload.width,
        height=payload.height,
        num=payload.num,
        author_id=user_id,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return ImageOut(
        id=obj.id,
        image_url=obj.image_url,
        width=obj.width,
        height=obj.height,
        num=obj.num,
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
    obj = (
        await session.execute(
            select(Image).where(Image.id == image_id, Image.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Image not found')
    return ImageOut(
        id=obj.id,
        image_url=obj.image_url,
        width=obj.width,
        height=obj.height,
        num=obj.num,
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
    obj = (
        await session.execute(
            select(Image).where(Image.id == image_id, Image.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Image not found')
    obj.image_url = payload.image_url
    obj.width = payload.width
    obj.height = payload.height
    obj.num = payload.num
    await session.commit()
    await session.refresh(obj)
    return ImageOut(
        id=obj.id,
        image_url=obj.image_url,
        width=obj.width,
        height=obj.height,
        num=obj.num,
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
    obj = (
        await session.execute(
            select(Image).where(Image.id == image_id, Image.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not obj:
        return

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
