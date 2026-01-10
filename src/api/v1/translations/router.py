"""Translations API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user

from .schemas import TranslationIn, TranslationOut, PageOut
from .services import (
    translations_list_service,
    translation_create_service,
    translation_retrieve_service,
    translation_update_service,
    translation_delete_service,
)

router = APIRouter(prefix="/translations", tags=["translations"])


@router.get("", response_model=PageOut)
async def translations_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await translations_list_service(
        session=session,
        user_id=user.id,
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
    )


@router.post("", response_model=TranslationOut)
async def translation_create(
    payload: TranslationIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await translation_create_service(
        session=session, user_id=user.id, payload=payload
    )


@router.get("/{slug}", response_model=TranslationOut)
async def translation_retrieve(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await translation_retrieve_service(
        session=session, user_id=user.id, slug=slug
    )


@router.patch("/{slug}", response_model=TranslationOut)
async def translation_update(
    slug: str,
    payload: TranslationIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await translation_update_service(
        session=session, user_id=user.id, slug=slug, payload=payload
    )


@router.delete("/{slug}", status_code=204)
async def translation_delete(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await translation_delete_service(session=session, user_id=user.id, slug=slug)
