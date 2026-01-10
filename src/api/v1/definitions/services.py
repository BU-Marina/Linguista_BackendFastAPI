"""Definitions services."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.searching import apply_search
from api.v1.utils.ordering import apply_ordering
from api.v1.vocabulary.models import VOCAB_MODELS
from .schemas import DefinitionIn, DefinitionOut, PageOut


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


async def definitions_list_service(
    *,
    session: AsyncSession,
    user_id,
    page: int,
    limit: int,
    ordering: str | None,
    search: str | None,
    models: dict = VOCAB_MODELS,
) -> PageOut:
    Definition = models["Definition"]

    params = _params(page, limit, ordering, search)
    stmt = (
        select(Definition)
        .where(Definition.author_id == user_id)
        .options(selectinload(Definition.language))
    )
    stmt = apply_search(stmt, Definition, params.search, ["text", "translation"])
    ordering_map = {
        "text": Definition.text,
        "-text": Definition.text.desc(),
        "created": Definition.created,
        "-created": Definition.created.desc(),
        "modified": Definition.modified,
        "-modified": Definition.modified.desc(),
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
        DefinitionOut(
            id=r.id,
            slug=r.slug,
            text=r.text,
            translation=r.translation,
            language=getattr(r.language, "isocode", None),
            created=r.created,
            modified=r.modified,
        )
        for r in rows
    ]
    return PageOut(page=page, limit=limit, count=total, results=results)


async def definition_create_service(
    *,
    session: AsyncSession,
    user_id,
    payload: DefinitionIn,
    models: dict = VOCAB_MODELS,
) -> DefinitionOut:
    Definition = models["Definition"]
    Language = models["Language"]
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
    slug: str,
    models: dict = VOCAB_MODELS,
) -> DefinitionOut:
    Definition = models["Definition"]
    obj = (
        await session.execute(
            select(Definition).where(
                Definition.slug == slug, Definition.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Definition not found")
    return DefinitionOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        translation=obj.translation,
        language=getattr(obj.language, "isocode", None),
        created=obj.created,
        modified=obj.modified,
    )


async def definition_update_service(
    *,
    session: AsyncSession,
    user_id,
    slug: str,
    payload: DefinitionIn,
    models: dict = VOCAB_MODELS,
) -> DefinitionOut:
    Definition = models["Definition"]
    Language = models["Language"]
    obj = (
        await session.execute(
            select(Definition).where(
                Definition.slug == slug, Definition.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Definition not found")
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
    slug: str,
    models: dict = VOCAB_MODELS,
) -> None:
    Definition = models["Definition"]
    obj = (
        await session.execute(
            select(Definition).where(
                Definition.slug == slug, Definition.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        return
    await session.delete(obj)
    await session.commit()
