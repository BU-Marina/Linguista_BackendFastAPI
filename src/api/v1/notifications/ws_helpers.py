"""Helpers for notifications websocket and aggregation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from apps.notifications.constants import NotificationTypesEnum
from .models import NOTIFICATION_MODELS


def get_notifications_channel(user_id: UUID) -> str:
    return f'notifications:{user_id}'


async def group_notifications_if_needed(session: AsyncSession, user_id: UUID) -> None:
    """
    Replicates DRF grouping logic:
    - NEW_SUGGESTED_WORDS -> NEW_SUGGESTED_WORDS_GROUP (merge users/suggested_words_count)
    - WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING -> WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING_GROUP (merge words info)
    """
    Notification = NOTIFICATION_MODELS['Notification']
    types_to_process = NotificationTypesEnum.types_to_create_groups
    group_map: dict[str, dict[Any, list]] = defaultdict(lambda: defaultdict(list))

    rows = (
        (
            await session.execute(
                select(Notification).where(
                    Notification.recipient_id == user_id,
                    Notification.notification_type.in_(
                        list(types_to_process)
                        + [
                            NotificationTypesEnum.NEW_SUGGESTED_WORDS_GROUP,
                            NotificationTypesEnum.WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING_GROUP,
                        ]
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return

    for n in rows:
        if n.notification_type in (
            NotificationTypesEnum.NEW_SUGGESTED_WORDS,
            NotificationTypesEnum.NEW_SUGGESTED_WORDS_GROUP,
        ):
            key = (
                'NEW_SUGGESTED_WORDS',
                n.from_object,
                n.is_seen,
            )
        elif n.notification_type in (
            NotificationTypesEnum.WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING,
            NotificationTypesEnum.WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING_GROUP,
        ):
            extra = n.extra_data or {}
            key = (
                'WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING',
                extra.get('days_left'),
                extra.get('word_activity_status'),
                extra.get('word_activity_progress'),
                n.is_seen,
            )
        else:
            continue
        group_map[key]['items'].append(n)

    new_notifications = []
    ids_to_delete: list[UUID] = []

    for key, bucket in group_map.items():
        items = bucket['items']
        if len(items) <= 1:
            continue
        ids_to_delete.extend([i.id for i in items])
        tag = key[0]
        if tag == 'NEW_SUGGESTED_WORDS':
            users_extra = []
            suggested_words_count = 0
            collection = None
            for n in items:
                extra = n.extra_data or {}
                if 'users' in extra:
                    users_extra.extend(extra['users'])
                elif 'user' in extra:
                    users_extra.append(extra['user'])
                suggested_words_count += extra.get('suggested_words_count', 0)
                collection = collection or extra.get('collection')
            new_notifications.append(
                Notification(
                    notification_type=NotificationTypesEnum.NEW_SUGGESTED_WORDS_GROUP,
                    recipient_id=user_id,
                    from_object=items[0].from_object,
                    extra_data={
                        'users': users_extra,
                        'collection': collection,
                        'suggested_words_count': suggested_words_count,
                    },
                    is_seen=key[-1],
                )
            )
        elif tag == 'WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING':
            words_texts = set()
            words_ids = set()
            extra_sample = items[0].extra_data or {}
            for n in items:
                extra = n.extra_data or {}
                if 'word_text' in extra:
                    words_texts.add(extra['word_text'])
                    if n.from_object:
                        words_ids.add(str(n.from_object))
                else:
                    words_texts.update(extra.get('words_texts', []))
                    words_ids.update(extra.get('words_ids', []))
            new_notifications.append(
                Notification(
                    notification_type=NotificationTypesEnum.WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING_GROUP,
                    recipient_id=user_id,
                    from_object=items[0].from_object,
                    extra_data={
                        'words_count': len(words_texts),
                        'words_texts': list(words_texts)[:4],
                        'words_ids': list(words_ids),
                        'word_activity_status': extra_sample.get(
                            'word_activity_status'
                        ),
                        'word_activity_progress': extra_sample.get(
                            'word_activity_progress'
                        ),
                        'days_left': extra_sample.get('days_left'),
                    },
                    is_seen=key[-1],
                )
            )

    if new_notifications:
        await session.execute(
            delete(Notification).where(Notification.id.in_(ids_to_delete))
        )
        session.add_all(new_notifications)
        await session.commit()
