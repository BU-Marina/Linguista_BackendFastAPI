"""Notifications schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: UUID
    recipient_id: UUID
    notification_type: str
    from_object: Optional[UUID] = None
    extra_data: dict[str, Any] = Field(default_factory=dict)
    is_seen: bool = False
    created: Optional[datetime] = None

    model_config = {'from_attributes': True}


class NotificationsPageOut(BaseModel):
    page: int
    limit: int
    count: int
    unseen_count: int
    results: List[NotificationOut]
