"""Notifications schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


def format_timestamp_related(d1: datetime, d2: datetime) -> str:
    """
    Format timestamp difference as 'months:days:hours:minutes'.
    Same format as utils_drf/datetime.py, but using months (30-day approximation).
    """
    difference = d1 - d2
    days = difference.days
    months = days // 30
    rem_days = days % 30

    # Get hours and minutes from the remaining seconds
    total_seconds = int(difference.total_seconds())
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    return f'{months}:{rem_days}:{hours}:{minutes}'


class NotificationOut(BaseModel):
    id: UUID
    recipient_id: UUID
    notification_type: str
    from_object: Optional[UUID] = None
    extra_data: dict[str, Any] = Field(default_factory=dict)
    is_seen: bool = False
    created: Optional[datetime] = None

    @computed_field
    @property
    def created_relative(self) -> str:
        if self.created is None:
            return '0:0:0:0'
        now = datetime.now(timezone.utc)
        created = self.created
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return format_timestamp_related(now, created)

    model_config = {'from_attributes': True}


class NotificationsPageOut(BaseModel):
    page: int
    limit: int
    count: int
    unseen_count: int
    results: List[NotificationOut]
