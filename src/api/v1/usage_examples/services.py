"""Usage examples services."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.searching import apply_search
from api.v1.utils.ordering import apply_ordering
from api.v1.vocabulary.models import VOCAB_MODELS
from .schemas import ExampleIn, ExampleOut, PageOut


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


async def examples_list_service(
    *,
    session: AsyncSession,
    user_id,
    page: int,
    limit: int,
    ordering: str | None,
    search: str | None,
) -> PageOut:
    Example = VOCAB_MODELS["UsageExample"]

    params = _params(page, limit, ordering, search)
    stmt = (
        select(Example)
        .where(Example.author_id == user_id)
        .options(selectinload(Example.language))
    )
    stmt = apply_search(
        stmt, Example, params.search, ["text", "translation", "source_name"]
    )
    ordering_map = {
        "text": Example.text,
        "-text": Example.text.desc(),
        "created": Example.created,
        "-created": Example.created.desc(),
        "modified": Example.modified,
        "-modified": Example.modified.desc(),
    }
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default="-modified")

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (await session.execute(stmt.offset(params.offset).limit(params.limit)))
        .scalars()
        .all()
    )
    results = [
        ExampleOut(
            id=r.id,
            slug=r.slug,
            text=r.text,
            translation=r.translation,
            language=getattr(r.language, "isocode", None),
            source=r.source,
            source_name=r.source_name,
            source_url=r.source_url,
            created=r.created,
            modified=r.modified,
        )
        for r in rows
    ]
    return PageOut(page=page, limit=limit, count=total, results=results)


async def example_create_service(
    *,
    session: AsyncSession,
    user_id,
    payload: ExampleIn,
) -> ExampleOut:
    Example = VOCAB_MODELS["UsageExample"]
    Language = VOCAB_MODELS["Language"]
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
        source=payload.source or "OTH",
        source_name=payload.source_name,
        source_url=payload.source_url,
        language_id=lang_id,
        author_id=user_id,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return ExampleOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=payload.language,
        source=obj.source,
        source_name=obj.source_name,
        source_url=obj.source_url,
        created=obj.created,
        modified=obj.modified,
    )


async def example_retrieve_service(
    *,
    session: AsyncSession,
    user_id,
    slug: str,
) -> ExampleOut:
    Example = VOCAB_MODELS["UsageExample"]
    obj = (
        await session.execute(
            select(Example).where(Example.slug == slug, Example.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Example not found")
    return ExampleOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=getattr(obj.language, "isocode", None),
        source=obj.source,
        source_name=obj.source_name,
        source_url=obj.source_url,
        created=obj.created,
        modified=obj.modified,
    )


async def example_update_service(
    *,
    session: AsyncSession,
    user_id,
    slug: str,
    payload: ExampleIn,
) -> ExampleOut:
    Example = VOCAB_MODELS["UsageExample"]
    Language = VOCAB_MODELS["Language"]
    obj = (
        await session.execute(
            select(Example).where(Example.slug == slug, Example.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Example not found")
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
    obj.source = payload.source or obj.source
    obj.source_name = payload.source_name
    obj.source_url = payload.source_url
    await session.commit()
    await session.refresh(obj)
    return ExampleOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=payload.language,
        source=obj.source,
        source_name=obj.source_name,
        source_url=obj.source_url,
        created=obj.created,
        modified=obj.modified,
    )


async def example_delete_service(
    *,
    session: AsyncSession,
    user_id,
    slug: str,
) -> None:
    Example = VOCAB_MODELS["UsageExample"]
    obj = (
        await session.execute(
            select(Example).where(Example.slug == slug, Example.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not obj:
        return
    await session.delete(obj)
    await session.commit()
