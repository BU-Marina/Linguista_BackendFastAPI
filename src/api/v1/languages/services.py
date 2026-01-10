"""Languages app services."""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from core.constants import AmountLimits

from .models import LANGUAGE_MODELS
from .schemas import (
    CollectionsByLanguageOut,
    LanguagesListOut,
    LearningLanguageCreateIn,
    LearningLanguageOut,
    LearningLanguagesListOut,
    LanguageCoverOut,
)
from .queries import (
    build_all_languages_stmt,
    build_collections_by_language_stmt,
    build_cover_choices_stmt,
    build_global_languages_stmt,
    build_learning_available_stmt,
    build_learning_languages_base_stmt,
    build_native_languages_stmt,
)
from .mapping import (
    map_collection_row,
    map_cover_row,
    map_language_row,
    map_learning_language_row,
)
from .params import LanguagesListParams


async def learning_languages_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    params: LanguagesListParams,
    models: dict = LANGUAGE_MODELS,
) -> LearningLanguagesListOut:
    base = build_learning_languages_base_stmt(
        user_id=user_id, models=models, ordering=params.ordering
    )
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        (await session.execute(base.offset(params.offset).limit(params.limit)))
        .mappings()
        .all()
    )
    results = [map_learning_language_row(dict(r)) for r in rows]
    return LearningLanguagesListOut(count=total, results=results)


async def learning_language_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    isocode: str,
    models: dict = LANGUAGE_MODELS,
) -> LearningLanguageOut:
    stmt = build_learning_languages_base_stmt(
        user_id=user_id,
        models=models,
        ordering=None,
        isocode=isocode,
    )
    row = (await session.execute(stmt)).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Learning language not found")
    return map_learning_language_row(dict(row))


async def learning_languages_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    payload: Iterable[LearningLanguageCreateIn],
    params: LanguagesListParams,
    models: dict = LANGUAGE_MODELS,
) -> LearningLanguagesListOut:
    Language = models["Language"]
    UserLearningLanguage = models["UserLearningLanguage"]
    LanguageCoverImage = models["LanguageCoverImage"]

    requested_isocodes = {item.language_isocode for item in payload}
    if not requested_isocodes:
        raise HTTPException(status_code=400, detail="No languages provided")

    languages = (
        (
            await session.execute(
                select(Language).where(Language.isocode.in_(requested_isocodes))
            )
        )
        .scalars()
        .all()
    )
    found_isocodes = {lang.isocode for lang in languages}
    missing = requested_isocodes - found_isocodes
    if missing:
        raise HTTPException(
            status_code=404, detail=f"Languages not found: {', '.join(sorted(missing))}"
        )

    for lang in languages:
        if not lang.learning_available:
            raise HTTPException(
                status_code=400,
                detail=f"Language {lang.isocode} is not available for learning",
            )

    current_count = (
        await session.execute(
            select(func.count())
            .select_from(UserLearningLanguage)
            .where(UserLearningLanguage.user_id == user_id)
        )
    ).scalar_one()

    existing_isocodes = set(
        (
            await session.execute(
                select(Language.isocode)
                .select_from(UserLearningLanguage)
                .join(Language, Language.id == UserLearningLanguage.language_id)
                .where(UserLearningLanguage.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )

    to_create = [lang for lang in languages if lang.isocode not in existing_isocodes]

    if (
        current_count + len(to_create)
        > AmountLimits.Languages.MAX_LEARNING_LANGUAGES_AMOUNT
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Learning languages amount limit exceeded ({AmountLimits.Languages.MAX_LEARNING_LANGUAGES_AMOUNT})",
        )
    for lang in to_create:
        ull = UserLearningLanguage(user_id=user_id, language_id=lang.id)
        default_cover = (
            await session.execute(
                select(LanguageCoverImage.id)
                .where(
                    LanguageCoverImage.language_id == lang.id,
                    LanguageCoverImage.default.is_(True),
                )
                .order_by(LanguageCoverImage.created.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if default_cover:
            ull.cover_id = default_cover
        session.add(ull)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Some languages are already added")

    return await learning_languages_list_service(
        session=session,
        user_id=user_id,
        params=params,
        models=models,
    )


async def learning_language_delete_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    isocode: str,
    delete_words: bool,
    params: LanguagesListParams,
    models: dict = LANGUAGE_MODELS,
) -> LearningLanguagesListOut:
    Language = models["Language"]
    UserLearningLanguage = models["UserLearningLanguage"]
    Word = models["Word"]

    ull_row = (
        await session.execute(
            select(UserLearningLanguage, Language)
            .join(Language, Language.id == UserLearningLanguage.language_id)
            .where(UserLearningLanguage.user_id == user_id, Language.isocode == isocode)
        )
    ).first()
    if not ull_row:
        raise HTTPException(status_code=404, detail="Learning language not found")

    ull = ull_row[0]
    language = ull_row[1]

    if delete_words:
        await session.execute(
            delete(Word).where(
                Word.author_id == user_id, Word.language_id == language.id
            )
        )

    await session.delete(ull)
    await session.commit()

    return await learning_languages_list_service(
        session=session,
        user_id=user_id,
        params=params,
        models=models,
    )


async def collections_by_language_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    isocode: str,
    models: dict = LANGUAGE_MODELS,
) -> CollectionsByLanguageOut:
    stmt = build_collections_by_language_stmt(
        user_id=user_id, isocode=isocode, models=models
    )
    rows = (await session.execute(stmt)).mappings().all()
    results = [map_collection_row(dict(r)) for r in rows]
    return CollectionsByLanguageOut(count=len(results), results=results)


async def all_languages_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    models: dict = LANGUAGE_MODELS,
) -> LanguagesListOut:
    stmt = build_all_languages_stmt(user_id=user_id, models=models)
    rows = (await session.execute(stmt)).mappings().all()
    results = [map_language_row(dict(r)) for r in rows]
    return LanguagesListOut(count=len(results), results=results)


async def native_languages_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    models: dict = LANGUAGE_MODELS,
) -> LanguagesListOut:
    stmt = build_native_languages_stmt(user_id=user_id, models=models)
    rows = (await session.execute(stmt)).mappings().all()
    results = [
        map_language_row(
            {
                "id": r["language_id"],
                "isocode": r["isocode"],
                "name_local": r["name_local"],
                "name_en": r["name_en"],
                "name_ru": r["name_ru"],
                "flag_icon": r["flag_icon"],
                "is_native": True,
                "learning_available": True,
                "interface_available": False,
            }
        )
        for r in rows
    ]
    return LanguagesListOut(count=len(results), results=results)


async def learning_available_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    params: LanguagesListParams,
    models: dict = LANGUAGE_MODELS,
) -> LanguagesListOut:
    stmt = build_learning_available_stmt(
        user_id=user_id,
        models=models,
        ordering=params.ordering,
        search=params.search,
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (await session.execute(stmt.offset(params.offset).limit(params.limit)))
        .mappings()
        .all()
    )
    results = [map_language_row(dict(r)) for r in rows]
    return LanguagesListOut(count=total, results=results)


async def cover_choices_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    isocode: str,
    params: LanguagesListParams,
    models: dict = LANGUAGE_MODELS,
) -> list[LanguageCoverOut]:
    stmt = build_cover_choices_stmt(user_id=user_id, isocode=isocode, models=models)
    rows = (
        (await session.execute(stmt.offset(params.offset).limit(params.limit)))
        .mappings()
        .all()
    )
    return [map_cover_row(dict(r)) for r in rows]


async def set_cover_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    isocode: str,
    cover_id: str | None,
    image_url: str | None,
    models: dict = LANGUAGE_MODELS,
) -> LearningLanguageOut:
    Language = models["Language"]
    LanguageCoverImage = models["LanguageCoverImage"]
    UserLearningLanguage = models["UserLearningLanguage"]

    ull_row = (
        await session.execute(
            select(UserLearningLanguage, Language)
            .join(Language, Language.id == UserLearningLanguage.language_id)
            .where(UserLearningLanguage.user_id == user_id, Language.isocode == isocode)
        )
    ).first()
    if not ull_row:
        raise HTTPException(status_code=404, detail="Learning language not found")
    ull = ull_row[0]
    language = ull_row[1]

    cover_obj_id = None
    if cover_id:
        cover_obj_id = (
            await session.execute(
                select(LanguageCoverImage.id).where(
                    LanguageCoverImage.id == cover_id,
                    LanguageCoverImage.language_id == language.id,
                )
            )
        ).scalar_one_or_none()
        if not cover_obj_id:
            raise HTTPException(status_code=404, detail="Cover image not found")
    elif image_url:
        new_cover = LanguageCoverImage(
            language_id=language.id, image_url=image_url, default=False
        )
        session.add(new_cover)
        await session.flush()
        cover_obj_id = new_cover.id
    else:
        raise HTTPException(status_code=400, detail="cover_id or image_url required")

    ull.cover_id = cover_obj_id
    await session.commit()

    return await learning_language_detail_service(
        session=session,
        user_id=user_id,
        isocode=isocode,
        models=models,
    )


async def delete_cover_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    isocode: str,
    cover_id: str,
    models: dict = LANGUAGE_MODELS,
) -> LearningLanguageOut:
    Language = models["Language"]
    LanguageCoverImage = models["LanguageCoverImage"]
    UserLearningLanguage = models["UserLearningLanguage"]

    ull_row = (
        await session.execute(
            select(UserLearningLanguage, Language)
            .join(Language, Language.id == UserLearningLanguage.language_id)
            .where(UserLearningLanguage.user_id == user_id, Language.isocode == isocode)
        )
    ).first()
    if not ull_row:
        raise HTTPException(status_code=404, detail="Learning language not found")
    ull = ull_row[0]
    language = ull_row[1]

    cover_obj = (
        await session.execute(
            select(LanguageCoverImage).where(
                LanguageCoverImage.id == cover_id,
                LanguageCoverImage.language_id == language.id,
            )
        )
    ).scalar_one_or_none()
    if not cover_obj:
        raise HTTPException(status_code=404, detail="Cover image not found")

    if ull.cover_id == cover_obj.id:
        ull.cover_id = None
    await session.delete(cover_obj)
    await session.commit()

    return await learning_language_detail_service(
        session=session,
        user_id=user_id,
        isocode=isocode,
        models=models,
    )


async def global_languages_list_service(
    *,
    session: AsyncSession,
    params: LanguagesListParams,
    models: dict = LANGUAGE_MODELS,
) -> LanguagesListOut:
    stmt = build_global_languages_stmt(
        interface_only=False,
        search=params.search,
        ordering=params.ordering,
        models=models,
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (await session.execute(stmt.offset(params.offset).limit(params.limit)))
        .mappings()
        .all()
    )
    results = [map_language_row(dict(r)) for r in rows]
    return LanguagesListOut(count=total, results=results)


async def interface_languages_list_service(
    *,
    session: AsyncSession,
    params: LanguagesListParams,
    models: dict = LANGUAGE_MODELS,
) -> LanguagesListOut:
    stmt = build_global_languages_stmt(
        interface_only=True,
        search=params.search,
        ordering=params.ordering,
        models=models,
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (await session.execute(stmt.offset(params.offset).limit(params.limit)))
        .mappings()
        .all()
    )
    results = [map_language_row(dict(r)) for r in rows]
    return LanguagesListOut(count=total, results=results)
