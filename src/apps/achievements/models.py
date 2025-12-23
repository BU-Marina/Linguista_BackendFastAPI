"""Achievements app models."""

from sqlalchemy import (
    Column,
    String,
    SmallInteger,
    Boolean,
    ForeignKey,
    Table,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from core.base import Base
from apps.achievements.constants import (
    AchievementsLengthLimits,
    AchievementTypeEnum,
)

# Association table для many-to-many users_access
achievements_users_access = Table(
    "achievements_achievement_users_access",
    Base.metadata,
    Column("achievement_id", PG_UUID(as_uuid=True), ForeignKey("achievements_achievement.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", PG_UUID(as_uuid=True), ForeignKey("users_user.id", ondelete="CASCADE"), primary_key=True),
)

# -----------------------
# Achievement
# -----------------------
class Achievement(Base):
    """Достижение."""

    # fields
    name = Column(String(AchievementsLengthLimits.ACHIEVEMENT_NAME_MAX_LENGTH), nullable=False)  # длину поставь из AchievementsLengthLimits.ACHIEVEMENT_NAME_MAX_LENGTH
    description = Column(String(AchievementsLengthLimits.ACHIEVEMENT_DESCRIPTION_MAX_LENGTH), nullable=True)  # длину из AchievementsLengthLimits.ACHIEVEMENT_DESCRIPTION_MAX_LENGTH
    image = Column(String(1024), nullable=True)
    open_access = Column(Boolean, nullable=False, server_default="false")
    achievement_type = Column(String(AchievementTypeEnum.max_length), nullable=True)
    achievement_task_amount = Column(SmallInteger, nullable=True)
    achievement_secondary_task_amount = Column(SmallInteger, nullable=True)
    achievement_task_percent = Column(SmallInteger, nullable=True)

    # FK
    achievement_group_id = Column(PG_UUID(as_uuid=True), ForeignKey("achievements_achievementgroup.id", ondelete="CASCADE"), nullable=True)
    author_id = Column(PG_UUID(as_uuid=True), ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False)

    # Relationships (FK)
    achievement_group = relationship("AchievementGroup", backref="achievements", lazy="selectin")
    author = relationship("User", backref="achievements", lazy="selectin")
    users_access = relationship("User", secondary=achievements_users_access, backref="achievements_available", lazy="selectin")
    goals = relationship(
        "apps.users.models.Goal",
        back_populates="achievement",
        foreign_keys="[apps.users.models.Goal.achievement_id]"
    )

    __table_args__ = (
        # В Django был UniqueConstraint(Lower('name'), 'author', name='unique_achievement')
        # Мы не создаём функциональный unique constraint здесь (нужна миграция Alembic с lower(name)).
        Index("ix_achievements_achievement_created_modified", "created", "modified"),
    )

    def __repr__(self):
        return f"<Achievement(name={self.name})>"


# -----------------------
# AchievementGroup
# -----------------------
class AchievementGroup(Base):
    """Группа достижений"""

    # fields
    title = Column(String(128), nullable=False, unique=True)  # длину из AchievementsLengthLimits.ACHIEVEMENT_GROUP_TITLE_MAX_LENGTH

    # FK
    # (нет)

    # Relationships (FK)
    # related name в Django для Achievement.achievement_group = 'achievements'
    # relationship на стороне Achievement уже задаёт backref "achievements"

    __table_args__ = (
        Index("ix_achievements_achievementgroup_created", "created"),
    )

    def __repr__(self):
        return f"<AchievementGroup(title={self.title})>"


# -----------------------
# AchievementProgress
# -----------------------
class AchievementProgress(Base):
    # __tablename__ -> "achievements_achievementprogress"

    # fields
    progress_amount = Column(SmallInteger, nullable=True)
    progress_secondary_amount = Column(SmallInteger, nullable=True)
    progress_percent = Column(SmallInteger, nullable=True)
    is_accomplished = Column(Boolean, nullable=False, server_default="false")

    # FK
    achievement_id = Column(PG_UUID(as_uuid=True), ForeignKey("achievements_achievement.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False)

    # Relationships (FK)
    achievement = relationship("Achievement", backref="users_progress", lazy="selectin")
    user = relationship("User", backref="achievements_progress", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("achievement_id", "user_id", name="unique_user_achievement_progress"),
        Index("ix_achievements_achievementprogress_created_modified", "created", "modified"),
    )

    def __repr__(self):
        return f"<AchievementProgress(user_id={self.user_id}, achievement_id={self.achievement_id})>"
