"""Users app db models."""

import uuid

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    Text,
    SmallInteger,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Time,
    DateTime,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable

from core.base import Base
from core.mixins import SlugMixin
from core.constants import (
    AccessLevelsEnum,
)

from .constants import (
    BASE_PLAN,
    UsersLengthLimits,
    ComplaintReasonEnum,
    FriendsRequestPermissionsEnum,
    FriendsNotificationsPermissionsEnum,
    ChatUsageAnalysPermissionEnum,
    CommonPermissionsEnum,
)

# -------------------------
# Association tables (for plain M2M without through)
# -------------------------

# User.interests
users_user_interests = Table(
    "users_user_interests",
    Base.metadata,
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "interest_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_interest.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# User.cities
users_user_cities = Table(
    "users_user_cities",
    Base.metadata,
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "city_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_city.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# ----------------------
# Пользователь и связанные модели (SQLAlchemy)
# ----------------------


class User(SQLAlchemyBaseUserTable[uuid.UUID], Base, SlugMixin):
    """Пользователь."""

    __tablename__ = "users_user"

    # Essentials
    username = Column(String(150), nullable=False, unique=True, index=True)
    email = Column(String(254), nullable=False)

    # Personal info
    first_name = Column(String(UsersLengthLimits.FIRST_NAME_MAX_LENGTH), nullable=True)
    gender = Column(String(1), nullable=True)
    profile_description = Column(
        String(UsersLengthLimits.PROFILE_DESCRIPTION_MAX_LENGTH), nullable=True
    )
    profile_image_url = Column(String(1024), nullable=True)
    profile_header_image_url = Column(String(1024), nullable=True)

    # Teacher info
    is_teacher = Column(Boolean, nullable=False, default=False)
    teaching_goal = Column(
        String(UsersLengthLimits.TEACHING_GOAL_MAX_LENGTH), nullable=True
    )

    # Service info
    subscription_plan = Column(String(1), nullable=False, default=BASE_PLAN)
    last_activity_date = Column(DateTime(timezone=True), nullable=True)
    login_allowed = Column(Boolean, nullable=False, default=True)
    onboarding_passed = Column(Boolean, nullable=False, default=False)
    is_official = Column(Boolean, nullable=False, default=False)
    strike_status = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    is_blocked = Column(Boolean, nullable=False, default=False)

    # Standart marks/dates from AbstractUser (Django)
    is_active = Column(Boolean, nullable=False, default=True)  # доступ к логину
    is_staff = Column(Boolean, nullable=False, default=False)  # доступ к админке
    is_superuser = Column(Boolean, nullable=False, default=False)  # суперпользователь
    last_login = Column(DateTime(timezone=True), nullable=True)  # последнее логин-время

    # TODO
    show_interests = Column(Boolean, nullable=False, default=True)  # move to settings
    date_joined = Column(DateTime(timezone=True), nullable=True)  # remove

    # FK
    study_plan_id = Column(PG_UUID(as_uuid=True), nullable=True)

    # Relationships (FK)
    study_plan = relationship(
        "StudyPlan",
        foreign_keys=[study_plan_id],
        back_populates="users",
        lazy="selectin",
    )
    interests = relationship(
        "Interest",
        secondary=users_user_interests,
        back_populates="users",
        lazy="selectin",
    )
    cities = relationship(
        "City",
        secondary=users_user_cities,
        back_populates="users",
        lazy="selectin",
    )
    native_languages = relationship(
        "Language",
        secondary="languages_usernativelanguage",
        viewonly=True,
        back_populates="native_for",
        lazy="selectin",
    )
    learning_languages = relationship(
        "Language",
        secondary="languages_userlearninglanguage",
        viewonly=True,
        lazy="selectin",
    )

    __slug_source__ = ["username"]

    __table_args__ = (
        ForeignKeyConstraint(
            ["study_plan_id"],
            ["users_studyplan.id"],
            name="fk_users_user_study_plan_id_users_studyplan",
            ondelete="SET NULL",
            use_alter=True,
        ),
        Index("ix_users_user_date_joined", "date_joined"),
    )

    def __repr__(self):
        return f"<User(username={self.username})>"


class UserSettings(Base):
    """Настройки аккаунта пользователя."""

    # Localization
    interface_language = Column(String(8), nullable=False, default="en")

    # Custom permissions
    allow_buddy_search = Column(Boolean, default=True)
    allow_subscriptions = Column(Boolean, default=True)
    allow_friends_requests_from = Column(
        String(FriendsRequestPermissionsEnum.max_length),
        nullable=False,
        default=FriendsRequestPermissionsEnum.ALL,
    )
    allow_notifications_from = Column(
        String(FriendsNotificationsPermissionsEnum.max_length),
        nullable=False,
        default=FriendsNotificationsPermissionsEnum.ALL_FRIENDS,
    )
    allow_send_notifications_to = Column(
        String(FriendsNotificationsPermissionsEnum.max_length),
        nullable=False,
        default=FriendsNotificationsPermissionsEnum.ALL_FRIENDS,
    )
    allow_start_private_chat_for = Column(
        String(CommonPermissionsEnum.max_length),
        nullable=False,
        default=CommonPermissionsEnum.ALL,
    )
    allow_invite_to_group_chat_for = Column(
        String(CommonPermissionsEnum.max_length),
        nullable=False,
        default=CommonPermissionsEnum.ALL,
    )
    allow_collecting_stats_from = Column(
        String(ChatUsageAnalysPermissionEnum.max_length),
        nullable=False,
        default=ChatUsageAnalysPermissionEnum.ALL_CHATS,
    )
    words_allow_comments = Column(Boolean, default=True)
    collections_allow_comments = Column(Boolean, default=True)
    collections_allow_suggestions = Column(Boolean, default=True)
    collections_allow_suggestions_notifications = Column(Boolean, default=True)

    # Visibility
    show_achievements_for = Column(
        String(CommonPermissionsEnum.max_length),
        nullable=False,
        default=CommonPermissionsEnum.FRIENDS,
    )
    show_certificates_for = Column(
        String(CommonPermissionsEnum.max_length),
        nullable=False,
        default=CommonPermissionsEnum.FRIENDS,
    )
    show_online_status_for = Column(
        String(CommonPermissionsEnum.max_length),
        nullable=False,
        default=CommonPermissionsEnum.FRIENDS,
    )
    show_strike_status_for = Column(
        String(CommonPermissionsEnum.max_length),
        nullable=False,
        default=CommonPermissionsEnum.FRIENDS,
    )
    private_account = Column(Boolean, default=False)

    # Functional
    auto_problematic_words = Column(Boolean, default=True)
    hide_suggested_content = Column(Boolean, default=False)
    only_premium_content = Column(Boolean, default=False)

    # Defaults
    words_default_cards_type = Column(String(8), nullable=False, default="STD")
    words_default_access_level = Column(
        String(8), nullable=True, default=AccessLevelsEnum.PUBLIC
    )
    collections_default_access_level = Column(
        String(8), nullable=True, default=AccessLevelsEnum.PUBLIC
    )

    # FK
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Relationships (FK)
    user = relationship("User", back_populates="settings", lazy="selectin")


User.settings = relationship(
    "UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan"
)


class Subscription(Base):
    """
    Промежуточная модель подписки пользователя на обновления другого пользователя.
    """

    enable_notifications = Column(Boolean, default=True)
    new_words = Column(Text, nullable=True)
    updated_words = Column(Text, nullable=True)
    new_collections = Column(Text, nullable=True)

    # FK
    subscriber_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    subscriber = relationship(
        "User",
        foreign_keys=[subscriber_id],
        backref="subscriptions_detail",
        lazy="selectin",
    )
    user = relationship(
        "User", foreign_keys=[user_id], backref="subscribers_detail", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("subscriber_id <> user_id", name="subscriber_not_same_user"),
        UniqueConstraint("subscriber_id", "user_id", name="unique_subscription"),
        Index("ix_users_subscription_created", "created"),
    )


class Friend(Base):
    """Связь дружбы между двумя пользователями (симметрично)."""

    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    friend_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    friend = relationship(
        "User", foreign_keys=[friend_id], lazy="selectin", overlaps="user"
    )

    __table_args__ = (
        CheckConstraint("user_id <> friend_id", name="friend_not_same_user"),
        UniqueConstraint("user_id", "friend_id", name="unique_friend_pair"),
        Index("ix_users_friend_user_id", "user_id"),
        Index("ix_users_friend_friend_id", "friend_id"),
    )


class FriendRequest(Base):
    """Запрос в друзья: requester -> target."""

    requester_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    requester = relationship("User", foreign_keys=[requester_id], lazy="selectin")
    target = relationship(
        "User", foreign_keys=[target_id], lazy="selectin", overlaps="requester"
    )

    __table_args__ = (
        CheckConstraint(
            "requester_id <> target_id", name="friendrequest_not_same_user"
        ),
        UniqueConstraint("requester_id", "target_id", name="unique_friend_request"),
        Index("ix_users_friendrequest_requester_id", "requester_id"),
        Index("ix_users_friendrequest_target_id", "target_id"),
    )


class SocialLink(Base):
    """Ссылка на соц сети пользователя."""

    name = Column(String(UsersLengthLimits.SOCIAL_LINK_NAME_MAX_LENGTH), nullable=False)
    link = Column(String(UsersLengthLimits.SOCIAL_LINK_MAX_LENGTH), nullable=False)

    # FK
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    user = relationship("User", backref="socials", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("name", "user_id", name="unique_user_social"),
        Index("ix_users_sociallink_created", "created"),
    )


class City(Base):
    """Город."""

    name = Column(String(UsersLengthLimits.CITY_NAME_MAX_LENGTH), nullable=False)

    # Relationships (FK)
    users = relationship(
        "User", secondary=users_user_cities, back_populates="cities", lazy="selectin"
    )

    def __repr__(self):
        return f"<City(name={self.name})>"


class Interest(Base):
    """Категория интересов пользователя, предпочтения."""

    name = Column(
        String(UsersLengthLimits.INTEREST_NAME_MAX_LENGTH), nullable=False, unique=True
    )
    cover = Column(String(1024), nullable=True)

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Relationships (FK)
    author = relationship("User", backref="custom_interests", lazy="selectin")
    users = relationship(
        "User",
        secondary=users_user_interests,
        back_populates="interests",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("name", "author_id", name="unique_interest"),
        Index("ix_users_interest_created", "created"),
    )


class Goal(Base):
    """Цель пользователя."""

    name = Column(String(UsersLengthLimits.GOAL_NAME_MAX_LENGTH), nullable=False)
    description = Column(
        String(UsersLengthLimits.GOAL_DESCRIPTION_MAX_LENGTH), nullable=True
    )
    open_access = Column(Boolean, default=False)
    date_start = Column(DateTime(timezone=True), nullable=True)
    date_end = Column(DateTime(timezone=True), nullable=True)

    # FK
    achievement_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("achievements_achievement.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship("User", backref="goals", lazy="selectin")
    achievement = relationship(
        "apps.achievements.models.Achievement",
        foreign_keys=[achievement_id],
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_users_goal_created_modified", "created", "modified"),
        # UniqueConstraint on lower(name), author -> сделать functional unique index в Alembic
    )


class Task(Base):
    """Задача в цели."""

    name = Column(String(UsersLengthLimits.TASK_NAME_MAX_LENGTH), nullable=False)

    new_words_task = Column(SmallInteger, nullable=True)

    words_usage_task = Column(SmallInteger, nullable=True)
    usage_type = Column(String(8), nullable=False, default="ANY")

    strike_days_task = Column(SmallInteger, nullable=True)

    exercises_passed_task = Column(SmallInteger, nullable=True)
    mistakes_allowed = Column(SmallInteger, nullable=True)

    lessons_passed_task = Column(SmallInteger, nullable=True)

    words_with_status_task = Column(SmallInteger, nullable=True)
    words_status = Column(String(16), nullable=False, default="inactive")

    subscribers_amount_task = Column(SmallInteger, nullable=True)

    # FK
    goal_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_goal.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    goal = relationship("Goal", backref="tasks", lazy="selectin")

    __table_args__ = (Index("ix_users_task_created_modified", "created", "modified"),)


class TaskProgress(Base):
    """..."""

    task_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_task.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    progress_amount = Column(SmallInteger, nullable=True)
    is_finished = Column(Boolean, default=False)

    task = relationship("Task", backref="users_progress", lazy="selectin")
    user = relationship("User", backref="tasks_progress", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("user_id", "task_id", name="unique_user_task_progress"),
        Index("ix_users_taskprogress_created", "created"),
    )


class GoalMember(Base):
    """Участник цели - приглашенный принять участие пользователь."""

    goal_status = Column(String(16), nullable=False, default="active")
    date_finished = Column(DateTime(timezone=True), nullable=True)
    send_notifications_from_others = Column(Boolean, default=True)

    # FK
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    goal_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_goal.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    user = relationship("User", backref="member_in_goals", lazy="selectin")
    goal = relationship("Goal", backref="members", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("user_id", "goal_id", name="unique_goal_member"),
    )


class StudyPlan(Base):
    """План обучения."""

    name = Column(String(UsersLengthLimits.STUDY_PLAN_NAME_MAX_LENGTH), nullable=False)
    description = Column(
        String(UsersLengthLimits.STUDY_PLAN_DESCRIPTION_MAX_LENGTH), nullable=True
    )
    new_words_task = Column(SmallInteger, nullable=True)
    words_usage_amount_task = Column(SmallInteger, nullable=True)
    every = Column(Integer, nullable=True)
    period = Column(String(24), nullable=False, default="days")
    new_words_task_weekly = Column(Text, nullable=True)
    words_usage_amount_task_weekly = Column(Text, nullable=True)
    break_days = Column(SmallInteger, nullable=True)
    study_week_days = Column(Text, nullable=True)
    notification_time = Column(Time, nullable=True)

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship(
        "User", foreign_keys=[author_id], backref="study_plans", lazy="selectin"
    )
    users = relationship(
        "User",
        foreign_keys=[User.study_plan_id],
        back_populates="study_plan",
        lazy="selectin",
    )

    __table_args__ = (
        # UniqueConstraint on lower(name), author -> сделать functional unique index в Alembic
    )


class StrikeSeriaHistory(Base):
    """История серий удара."""

    strike_start_date = Column(DateTime(timezone=True), nullable=False)
    strike_end_date = Column(DateTime(timezone=True), nullable=True)

    # FK
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    user = relationship("User", backref="strike_history", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("user_id", "strike_start_date", name="unique_strike_seria"),
    )


class Certificate(Base):
    """Сертификат пользователя."""

    title = Column(
        String(UsersLengthLimits.CERTIFICATE_TITLE_MAX_LENGTH), nullable=False
    )
    file = Column(String(1024), nullable=False)

    # FK
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    user = relationship("User", backref="certificates", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("title", "user_id", name="unique_certificate"),
        Index("ix_users_certificate_created_modified", "created", "modified"),
    )


class ConfirmationRequest(Base):
    """ "Запрос на подтверждение сертификата."""

    request_status = Column(String(32), nullable=False, default="pending")
    review = Column(String(UsersLengthLimits.REVIEW_TEXT_MAX_LENGTH), nullable=True)

    # FK
    certificate_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_certificate.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    learning_language_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("languages_userlearninglanguage.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    certificate = relationship(
        "Certificate", backref="level_confirm_requests", lazy="selectin"
    )


class TeacherReview(Base):
    """..."""

    teacher_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    text = Column(String(1024), nullable=False)
    stars = Column(SmallInteger, nullable=True)
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    teacher = relationship(
        "User", foreign_keys=[teacher_id], backref="reviews", lazy="selectin"
    )
    author = relationship("User", foreign_keys=[author_id], lazy="selectin")

    __table_args__ = (
        UniqueConstraint("teacher_id", "author_id", name="unique_review"),
    )


class MaterialGroup(Base):
    """Группа материалов."""

    title = Column(
        String(UsersLengthLimits.MATERIAL_GROUP_TITLE_MAX_LENGTH), nullable=False
    )

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship("User", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("title", "author_id", name="unique_material_group"),
    )


class Material(Base):
    """Материал."""

    title = Column(String(UsersLengthLimits.MATERIAL_TITLE_MAX_LENGTH), nullable=True)
    text = Column(String(UsersLengthLimits.MATERIAL_TEXT_MAX_LENGTH), nullable=True)
    file = Column(String(1024), nullable=True)

    # FK
    material_group_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_materialgroup.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    material_group = relationship("MaterialGroup", backref="materials", lazy="selectin")
    author = relationship("User", lazy="selectin")

    __table_args__ = (UniqueConstraint("title", "author_id", name="unique_material"),)


class Grammar(Base, SlugMixin):
    """Грамматическая конструкция."""

    # fields
    name = Column(String(UsersLengthLimits.GRAMMAR_NAME_MAX_LENGTH), nullable=True)
    construction_text = Column(
        String(UsersLengthLimits.GRAMMAR_TEXT_MAX_LENGTH), nullable=False
    )
    read_access_level = Column(String(8), nullable=False, default="public")
    add_access_level = Column(String(8), nullable=False, default="public")
    usage = Column(Integer, default=0, nullable=False)
    views_amount = Column(Integer, default=0, nullable=False)
    share_link = Column(PG_UUID(as_uuid=True), nullable=True)

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship("User", lazy="selectin")

    __slug_source__ = ["name", "author__username"]

    __table_args__ = (
        # UniqueConstraint on lower(name), author -> functional unique index in Alembic
    )


class GrammarGap(Base):
    """Пропуск в грамматической конструкции."""

    pre_position = Column(SmallInteger, nullable=False)
    # allowed_* fields are many-to-many -> implement association tables / models as needed


class FavoriteGrammar(Base):
    """Избранная грамматическая конструкция."""

    # FK
    grammar_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_grammar.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    grammar = relationship("Grammar", backref="favorite_for", lazy="selectin")
    user = relationship("User", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("grammar_id", "user_id", name="unique_user_favorite_grammar"),
    )


class Lesson(Base):
    """Урок."""

    name = Column(String(UsersLengthLimits.LESSON_NAME_MAX_LENGTH), nullable=False)
    description = Column(
        String(UsersLengthLimits.LESSON_DESCRIPTION_MAX_LENGTH), nullable=True
    )
    cover = Column(String(1024), nullable=True)
    read_access_level = Column(String(8), nullable=False, default="public")

    # FK
    exercises_set_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesset.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship("User", lazy="selectin")

    __table_args__ = (
        # UniqueConstraint on lower(name), author -> create functional index in Alembic
    )


class LessonBlock(Base):
    """Блок урока."""

    title = Column(
        String(UsersLengthLimits.LESSON_BLOCK_TITLE_MAX_LENGTH), nullable=True
    )
    content = Column(
        String(UsersLengthLimits.LESSON_BLOCK_CONTENT_MAX_LENGTH), nullable=False
    )
    image_url = Column(String(1024), nullable=True)
    file = Column(String(1024), nullable=True)

    # FK
    lesson_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_lesson.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    lesson = relationship("Lesson", backref="lesson_blocks", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("title", "lesson_id", name="unique_lesson_block"),
    )


class StudyGroup(Base):
    """Учебная группа."""

    name = Column(String(UsersLengthLimits.STUDY_GROUP_NAME_MAX_LENGTH), nullable=False)

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    chat_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("chats_chat.id", ondelete="SET NULL"),
        nullable=True,
    )
    vocabulary_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships (FK)
    author = relationship("User", backref="study_groups", lazy="selectin")

    __table_args__ = (
        # UniqueConstraint on lower(name), author -> functional index in Alembic
    )


class Complaint(Base):
    """Жалоба на пользователя."""

    reason = Column(String(ComplaintReasonEnum.max_length), nullable=False)
    comment = Column(String(UsersLengthLimits.COMMENT_TEXT_MAX_LENGTH), nullable=True)

    # FK
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    user = relationship("User", backref="recieved_complaints", lazy="selectin")


class UserIssue(Base):
    """Тема на форуме."""

    title = Column(String(UsersLengthLimits.ISSUE_TITLE_MAX_LENGTH), nullable=True)
    text = Column(String(UsersLengthLimits.ISSUE_TEXT_MAX_LENGTH), nullable=False)
    level_requested = Column(String(8), nullable=True, default="")

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="SET NULL"),
        nullable=True,
    )
    goal_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_goal.id", ondelete="SET NULL"),
        nullable=True,
    )
    collection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="SET NULL"),
        nullable=True,
    )
    language_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("languages_language.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_users_userissue_created_modified", "created", "modified"),
    )
