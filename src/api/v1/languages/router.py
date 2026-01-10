"""Languages api endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user, optional_current_user

from .schemas import (
    CoverDeleteIn,
    CoverSetIn,
    LanguagesListOut,
    LearningLanguageCreateIn,
    LearningLanguageOut,
    LearningLanguagesListOut,
    CollectionsByLanguageOut,
    LanguageCoverOut,
)
from .params import build_languages_list_params
from .services import (
    all_languages_service,
    collections_by_language_service,
    cover_choices_service,
    delete_cover_service,
    global_languages_list_service,
    interface_languages_list_service,
    learning_available_service,
    learning_language_delete_service,
    learning_language_detail_service,
    learning_languages_create_service,
    learning_languages_list_service,
    native_languages_service,
    set_cover_service,
)

router = APIRouter(prefix="/languages", tags=["languages"])


@router.get("", response_model=LearningLanguagesListOut)
async def learning_languages_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    params = build_languages_list_params(
        page=page, limit=limit, ordering=ordering, search=search
    )
    return await learning_languages_list_service(
        session=session,
        user_id=request_user.id,
        params=params,
    )


@router.post("", response_model=LearningLanguagesListOut)
async def learning_languages_create(
    payload: list[LearningLanguageCreateIn],
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    params = build_languages_list_params(
        page=page, limit=limit, ordering=ordering, search=search
    )
    return await learning_languages_create_service(
        session=session,
        user_id=request_user.id,
        payload=payload,
        params=params,
    )


@router.get("/all", response_model=LanguagesListOut)
async def all_languages(
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    return await all_languages_service(
        session=session,
        user_id=request_user.id,
    )


@router.get("/native", response_model=LanguagesListOut)
async def native_languages(
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    return await native_languages_service(
        session=session,
        user_id=request_user.id,
    )


@router.get(
    "/learning-available", response_model=LanguagesListOut, tags=["global_languages"]
)
async def learning_available_languages(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(optional_current_user),
):
    params = build_languages_list_params(
        page=page, limit=limit, ordering=ordering, search=search
    )
    request_user_id = getattr(request_user, "id", None)
    return await learning_available_service(
        session=session,
        user_id=request_user_id,
        params=params,
    )


@router.get(
    "/global-languages", response_model=LanguagesListOut, tags=["global_languages"]
)
async def global_languages(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_languages_list_params(
        page=page, limit=limit, ordering=ordering, search=search
    )
    return await global_languages_list_service(
        session=session,
        params=params,
    )


@router.get(
    "/global-languages/interface",
    response_model=LanguagesListOut,
    tags=["global_languages"],
)
async def interface_languages(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_languages_list_params(
        page=page, limit=limit, ordering=ordering, search=search
    )
    return await interface_languages_list_service(
        session=session,
        params=params,
    )


@router.get("/{isocode}", response_model=LearningLanguageOut)
async def learning_language_detail(
    isocode: str,
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    return await learning_language_detail_service(
        session=session,
        user_id=request_user.id,
        isocode=isocode,
    )


@router.delete("/{isocode}", response_model=LearningLanguagesListOut)
async def learning_language_delete(
    isocode: str,
    delete_words: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    params = build_languages_list_params(
        page=page, limit=limit, ordering=ordering, search=search
    )
    return await learning_language_delete_service(
        session=session,
        user_id=request_user.id,
        isocode=isocode,
        delete_words=delete_words,
        params=params,
    )


@router.get("/{isocode}/collections", response_model=CollectionsByLanguageOut)
async def learning_language_collections(
    isocode: str,
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    return await collections_by_language_service(
        session=session,
        user_id=request_user.id,
        isocode=isocode,
    )


@router.get("/{isocode}/cover-choices", response_model=list[LanguageCoverOut])
async def cover_choices(
    isocode: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    params = build_languages_list_params(
        page=page, limit=limit, ordering=ordering, search=search
    )
    return await cover_choices_service(
        session=session,
        user_id=request_user.id,
        isocode=isocode,
        params=params,
    )


@router.post("/{isocode}/set-cover", response_model=LearningLanguageOut)
async def set_cover(
    isocode: str,
    payload: CoverSetIn,
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    return await set_cover_service(
        session=session,
        user_id=request_user.id,
        isocode=isocode,
        cover_id=payload.cover_id,
        image_url=payload.image_url,
    )


@router.post("/{isocode}/delete-cover", response_model=LearningLanguageOut)
async def delete_cover(
    isocode: str,
    payload: CoverDeleteIn,
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    return await delete_cover_service(
        session=session,
        user_id=request_user.id,
        isocode=isocode,
        cover_id=payload.cover_id,
    )
