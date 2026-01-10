"""Translations services."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.searching import apply_search
from api.v1.utils.ordering import apply_ordering

from api.v1.vocabulary.models import VOCAB_MODELS
from .schemas import TranslationIn, TranslationOut, PageOut


def _make_params(page: int, limit: int, ordering: str | None, search: str | None):
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


async def translations_list_service(
    *,
    session: AsyncSession,
    user_id,
    page: int,
    limit: int,
    ordering: str | None,
    search: str | None,
    models: dict = VOCAB_MODELS,
) -> PageOut:
    Translation = models["WordTranslation"]

    params = _make_params(page, limit, ordering, search)
    stmt = (
        select(Translation)
        .where(Translation.author_id == user_id)
        .options(selectinload(Translation.language))
    )
    stmt = apply_search(stmt, Translation, params.search, ["text"])
    ordering_map = {
        "text": Translation.text,
        "-text": Translation.text.desc(),
        "created": Translation.created,
        "-created": Translation.created.desc(),
        "modified": Translation.modified,
        "-modified": Translation.modified.desc(),
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
        TranslationOut(
            id=row.id,
            slug=row.slug,
            text=row.text,
            language=getattr(row.language, "isocode", None),
            created=row.created,
            modified=row.modified,
        )
        for row in rows
    ]
    return PageOut(page=page, limit=limit, count=total, results=results)


async def translation_create_service(
    *,
    session: AsyncSession,
    user_id,
    payload: TranslationIn,
    models: dict = VOCAB_MODELS,
) -> TranslationOut:
    Translation = models["WordTranslation"]
    Language = models["Language"]

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
    slug: str,
    models: dict = VOCAB_MODELS,
) -> TranslationOut:
    Translation = models["WordTranslation"]
    obj = (
        await session.execute(
            select(Translation).where(
                Translation.slug == slug, Translation.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Translation not found")
    return TranslationOut(
        id=obj.id,
        slug=obj.slug,
        text=obj.text,
        language=getattr(obj.language, "isocode", None),
        created=obj.created,
        modified=obj.modified,
    )


async def translation_update_service(
    *,
    session: AsyncSession,
    user_id,
    slug: str,
    payload: TranslationIn,
    models: dict = VOCAB_MODELS,
) -> TranslationOut:
    Translation = models["WordTranslation"]
    Language = models["Language"]
    obj = (
        await session.execute(
            select(Translation).where(
                Translation.slug == slug, Translation.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Translation not found")
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
    slug: str,
    models: dict = VOCAB_MODELS,
) -> None:
    Translation = models["WordTranslation"]
    obj = (
        await session.execute(
            select(Translation).where(
                Translation.slug == slug, Translation.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        return
    await session.delete(obj)
    await session.commit()
