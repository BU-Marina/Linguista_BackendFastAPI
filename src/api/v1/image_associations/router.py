"""Image associations API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from core.db import get_async_session
from auth.setup import current_user

from .schemas import ImageIn, ImageOut, PageOut
from .services import (
    images_list_service,
    image_create_service,
    image_retrieve_service,
    image_update_service,
    image_delete_service,
)

router = APIRouter(prefix="/images", tags=["image_associations"])


@router.get("", response_model=PageOut)
async def images_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
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
    )


@router.post("", response_model=ImageOut)
async def image_create(
    payload: ImageIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await image_create_service(session=session, user_id=user.id, payload=payload)


@router.get("/{image_id}", response_model=ImageOut)
async def image_retrieve(
    image_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await image_retrieve_service(
        session=session, user_id=user.id, image_id=image_id
    )


@router.patch("/{image_id}", response_model=ImageOut)
async def image_update(
    image_id: UUID,
    payload: ImageIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await image_update_service(
        session=session, user_id=user.id, image_id=image_id, payload=payload
    )


@router.delete("/{image_id}", status_code=204)
async def image_delete(
    image_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await image_delete_service(session=session, user_id=user.id, image_id=image_id)
