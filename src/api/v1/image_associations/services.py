"""Image associations services."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.utils.searching import apply_search
from api.v1.utils.ordering import apply_ordering
from api.v1.vocabulary.models import VOCAB_MODELS
from .schemas import ImageIn, ImageOut, PageOut


def _params(page, limit, ordering, search):
    return type(
        "Params",
        (),
        {
            "page": page,
            "limit": limit,
            "offset": (page - 1) * limit,
            "ordering": ordering,
            "search": search,
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
) -> PageOut:
    Image = VOCAB_MODELS["ImageAssociation"]

    params = _params(page, limit, ordering, search)
    stmt = select(Image).where(Image.author_id == user_id)
    stmt = apply_search(stmt, Image, params.search, ["image_url"])
    ordering_map = {
        "created": Image.created,
        "-created": Image.created.desc(),
        "modified": Image.modified,
        "-modified": Image.modified.desc(),
    }
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default="-created")

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (await session.execute(stmt.offset(params.offset).limit(params.limit)))
        .scalars()
        .all()
    )
    results = [
        ImageOut(
            id=r.id,
            image_url=r.image_url,
            width=r.width,
            height=r.height,
            num=r.num,
            created=r.created,
            modified=r.modified,
        )
        for r in rows
    ]
    return PageOut(page=page, limit=limit, count=total, results=results)


async def image_create_service(
    *,
    session: AsyncSession,
    user_id,
    payload: ImageIn,
) -> ImageOut:
    Image = VOCAB_MODELS["ImageAssociation"]
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
    Image = VOCAB_MODELS["ImageAssociation"]
    obj = (
        await session.execute(
            select(Image).where(Image.id == image_id, Image.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Image not found")
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
    Image = VOCAB_MODELS["ImageAssociation"]
    obj = (
        await session.execute(
            select(Image).where(Image.id == image_id, Image.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Image not found")
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
) -> None:
    Image = VOCAB_MODELS["ImageAssociation"]
    obj = (
        await session.execute(
            select(Image).where(Image.id == image_id, Image.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not obj:
        return
    await session.delete(obj)
    await session.commit()
