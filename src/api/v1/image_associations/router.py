"""Image associations API."""

from fastapi import APIRouter, Depends, Query, Body
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user

from .schemas import ImageIn, ImageOut, PageOut, ImageResolveOut
from .services import (
    images_list_service,
    image_create_service,
    image_retrieve_service,
    image_update_service,
    image_delete_service,
    image_add_words_service,
    image_remove_words_service,
    image_resolve_slug_service,
)

router = APIRouter(prefix='/images', tags=['image_associations'])


@router.get('', response_model=PageOut)
async def images_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    collections: str | None = Query(
        None,
        description='Comma-separated collection ids to filter images by linked words',
    ),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await images_list_service(
        session=session,
        user_id=user.id,
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        collections=collections,
    )


@router.post('', response_model=ImageOut)
async def image_create(
    payload: ImageIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await image_create_service(session=session, user_id=user.id, payload=payload)


@router.get('/slug/{slug}', response_model=ImageResolveOut)
async def image_resolve_slug(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await image_resolve_slug_service(session=session, user_id=user.id, slug=slug)


@router.get('/{image_id}', response_model=ImageOut)
async def image_retrieve(
    image_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await image_retrieve_service(
        session=session, user_id=user.id, image_id=image_id
    )


@router.patch('/{image_id}', response_model=ImageOut)
async def image_update(
    image_id: UUID,
    payload: ImageIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await image_update_service(
        session=session, user_id=user.id, image_id=image_id, payload=payload
    )


@router.delete('/{image_id}', status_code=204)
async def image_delete(
    image_id: UUID,
    delete_words: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await image_delete_service(
        session=session, user_id=user.id, image_id=image_id, delete_words=delete_words
    )


@router.post('/{image_id}/add-words', response_model=ImageOut)
async def image_add_words(
    image_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await image_add_words_service(
        session=session, user_id=user.id, image_id=image_id, word_ids=word_ids
    )


@router.post('/{image_id}/remove-words', response_model=ImageOut)
async def image_remove_words(
    image_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await image_remove_words_service(
        session=session, user_id=user.id, image_id=image_id, word_ids=word_ids
    )
