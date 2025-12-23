"""Notifications app db models."""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship

from core.base import Base

from .constants import NotificationsLengthLimits


class Notification(Base):
    """Уведомление."""

    # Fields
    notification_type = Column(
        String(NotificationsLengthLimits.NOTIFICATION_TYPE_MAX_LENGTH),
        nullable=False,
    )
    from_object = Column(PG_UUID(as_uuid=True), nullable=True)
    extra_data = Column(JSONB, nullable=False, server_default='{}')
    is_seen = Column(Boolean, nullable=False, server_default="false")

    # FK
    recipient_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    recipient = relationship("User", backref="notifications", lazy="selectin")

    __table_args__ = (
        Index("ix_notifications_created", "created"),  # created есть в PreBase
    )

    def __repr__(self):
        return f"<Notification(id={self.id}, recipient_id={self.recipient_id}, type={self.notification_type})>"
    