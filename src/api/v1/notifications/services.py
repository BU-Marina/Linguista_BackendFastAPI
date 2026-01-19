"""Notifications services."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.utils.pagination import normalize_pagination
from apps.notifications.constants import NotificationTypesEnum
from api.v1.notifications.ws_helpers import group_notifications_if_needed

from .models import NOTIFICATION_MODELS
from .schemas import NotificationsPageOut, NotificationOut


async def notifications_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    page: int,
    limit: int,
) -> NotificationsPageOut:
    Notification = NOTIFICATION_MODELS['Notification']

    await group_notifications_if_needed(session, user_id)

    page, limit, offset = normalize_pagination(page, limit)
    stmt = (
        select(Notification)
        .where(
            Notification.recipient_id == user_id,
            Notification.notification_type.notin_(
                NotificationTypesEnum.system_notification_types
            ),
        )
        .order_by(Notification.created.desc())
    )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    unseen = (
        await session.execute(
            select(func.count())
            .select_from(stmt.subquery())
            .where(Notification.is_seen.is_(False))
        )
    ).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    results = [NotificationOut.model_validate(r) for r in rows]

    return NotificationsPageOut(
        page=page, limit=limit, count=total, unseen_count=unseen, results=results
    )


async def notification_delete_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    notification_id: UUID,
    page: int,
    limit: int,
) -> NotificationsPageOut:
    Notification = NOTIFICATION_MODELS['Notification']
    obj = (
        await session.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.recipient_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Notification not found')

    await session.delete(obj)
    await session.commit()
    return await notifications_list_service(
        session=session, user_id=user_id, page=page, limit=limit
    )


async def notification_mark_seen_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    notification_id: UUID,
    page: int,
    limit: int,
) -> NotificationsPageOut:
    Notification = NOTIFICATION_MODELS['Notification']
    obj = (
        await session.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.recipient_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail='Notification not found')
    if obj.notification_type in NotificationTypesEnum.system_notification_types:
        await session.delete(obj)
    elif not obj.is_seen:
        obj.is_seen = True
    await session.commit()
    return await notifications_list_service(
        session=session, user_id=user_id, page=page, limit=limit
    )


async def notifications_clear_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    page: int,
    limit: int,
) -> NotificationsPageOut:
    Notification = NOTIFICATION_MODELS['Notification']
    await session.execute(
        Notification.__table__.delete().where(Notification.recipient_id == user_id)
    )
    await session.commit()
    return await notifications_list_service(
        session=session, user_id=user_id, page=page, limit=limit
    )
