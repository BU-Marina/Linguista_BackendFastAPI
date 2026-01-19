"""Translations API."""

from fastapi import APIRouter, Depends, Query, Body
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user

from .schemas import TranslationIn, TranslationOut, PageOut, TranslationResolveOut
from .services import (
    translations_list_service,
    translation_create_service,
    translation_retrieve_service,
    translation_update_service,
    translation_delete_service,
    translation_add_words_service,
    translation_remove_words_service,
    translation_resolve_slug_service,
)

router = APIRouter(prefix='/translations', tags=['translations'])


@router.get('', response_model=PageOut)
async def translations_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    collections: str | None = Query(
        None,
        description='Comma-separated collection slugs to filter translations by linked words',
    ),
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
        collections=collections,
    )


@router.post('', response_model=TranslationOut)
async def translation_create(
    payload: TranslationIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await translation_create_service(
        session=session, user_id=user.id, payload=payload
    )


@router.get('/slug/{slug}', response_model=TranslationResolveOut)
async def translation_resolve_slug(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await translation_resolve_slug_service(
        session=session, user_id=user.id, slug=slug
    )


@router.patch('/{translation_id}', response_model=TranslationOut)
async def translation_update(
    translation_id: UUID,
    payload: TranslationIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await translation_update_service(
        session=session, user_id=user.id, translation_id=translation_id, payload=payload
    )


@router.get('/{translation_id}', response_model=TranslationOut)
async def translation_retrieve(
    translation_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await translation_retrieve_service(
        session=session, user_id=user.id, translation_id=translation_id
    )


@router.delete('/{translation_id}', status_code=204)
async def translation_delete(
    translation_id: UUID,
    delete_words: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await translation_delete_service(
        session=session,
        user_id=user.id,
        translation_id=translation_id,
        delete_words=delete_words,
    )


@router.post('/{translation_id}/add-words', response_model=TranslationOut)
async def translation_add_words(
    translation_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await translation_add_words_service(
        session=session,
        user_id=user.id,
        translation_id=translation_id,
        word_ids=word_ids,
    )


@router.post('/{translation_id}/remove-words', response_model=TranslationOut)
async def translation_remove_words(
    translation_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await translation_remove_words_service(
        session=session,
        user_id=user.id,
        translation_id=translation_id,
        word_ids=word_ids,
    )
