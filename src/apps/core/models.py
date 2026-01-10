"""Core models."""

from sqlalchemy import (
    Column,
    String,
    SmallInteger,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from core.base import Base
from core.constants import CoreLengthLimits


# ---------------------------
# Tag model
# ---------------------------


class Tag(Base):
    """Тег."""

    __tablename__ = "core_tag"

    # fields
    name = Column(String(CoreLengthLimits.TAG_MAX_LENGTH), nullable=False)

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    author = relationship("User", backref="tags", lazy="selectin")

    __table_args__ = (Index("ix_core_tag_created_modified", "created", "modified"),)

    def __repr__(self):
        return f"<Tag(name={self.name}, author_id={self.author_id})>"


# ---------------------------
# PlatformReview model
# ---------------------------


class PlatformReview(Base):
    """Отзыв на платформу."""

    __tablename__ = "core_platformreview"

    # fields
    text = Column(String(CoreLengthLimits.REVIEW_TEXT_MAX_LENGTH), nullable=False)
    stars = Column(SmallInteger, nullable=True)
    is_shown = Column(Boolean, nullable=False, server_default="false")

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    author = relationship("User", backref="platform_reviews", lazy="selectin")

    __table_args__ = (
        Index("ix_core_platformreview_created", "created"),
        CheckConstraint("stars <= 5", name="chk_core_platformreview_stars_max"),
    )

    def __repr__(self):
        return f"<PlatformReview(id={self.id}, stars={self.stars})>"
