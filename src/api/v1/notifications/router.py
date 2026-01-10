"""Notifications endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user
from .schemas import NotificationsPageOut
from .services import notifications_list_service, notification_delete_service

router = APIRouter(prefix='/notifications', tags=['notifications'])


@router.get('', response_model=NotificationsPageOut)
async def notifications_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await notifications_list_service(
        session=session, user_id=user.id, page=page, limit=limit
    )


@router.delete('/{notification_id}', response_model=NotificationsPageOut)
async def notification_delete(
    notification_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await notification_delete_service(
        session=session,
        user_id=user.id,
        notification_id=notification_id,
        page=page,
        limit=limit,
    )
