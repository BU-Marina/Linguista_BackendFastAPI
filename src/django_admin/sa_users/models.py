"""..."""

from django.db import models

from sa_core.mixins import SaStampedModel
from sa_achievements.models import SaAchievement


class SaUser(models.Model):
    """
    Обёртка над существующей таблицей users_user.
    Django НЕ управляет схемой (managed=False) — таблицу создаёт/меняет Alembic/SQLAlchemy.
    """

    id = models.UUIDField(primary_key=True, db_column="id")

    # поля 1:1 с SQLAlchemy‑моделью
    username = models.CharField(max_length=150, unique=True, db_index=True)
    email = models.EmailField(max_length=254)

    first_name = models.CharField(max_length=150, null=True, blank=True)
    gender = models.CharField(max_length=1, null=True, blank=True)
    profile_description = models.CharField(
        max_length=1024, null=True, blank=True
    )  # UsersLengthLimits.PROFILE_DESCRIPTION_MAX_LENGTH
    profile_image_url = models.CharField(max_length=1024, null=True, blank=True)
    profile_header_image_url = models.CharField(max_length=1024, null=True, blank=True)

    is_teacher = models.BooleanField(default=False)
    teaching_goal = models.CharField(
        max_length=255, null=True, blank=True
    )  # UsersLengthLimits.TEACHING_GOAL_MAX_LENGTH

    subscription_plan = models.CharField(max_length=1, default="B")  # BASE_PLAN
    last_activity_date = models.DateTimeField(null=True, blank=True)
    login_allowed = models.BooleanField(default=True)
    onboarding_passed = models.BooleanField(default=False)
    is_official = models.BooleanField(default=False)
    strike_status = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)

    show_interests = models.BooleanField(default=True)
    date_joined = models.DateTimeField(null=True, blank=True)

    # slug из вашего SlugMixin
    slug = models.CharField(max_length=255, unique=True, db_index=True)

    # hashed_password из SQLAlchemyBaseUserTable
    hashed_password = models.CharField(max_length=1024)

    # FK на study_plan (если хочешь отобразить как FK; можно и как просто UUIDField)
    study_plan_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "users_user"  # ВАЖНО: имя существующей таблицы
        managed = False  # Django НЕ создаёт/НЕ меняет эту таблицу
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return f"{self.username} ({self.email})"


class SaUserSettings(SaStampedModel):
    """
    users_usersettings
    """

    interface_language = models.CharField(max_length=8, default="en")

    allow_buddy_search = models.BooleanField(default=True)
    allow_subscriptions = models.BooleanField(default=True)

    allow_friends_requests_from = models.CharField(max_length=64, default="ALL")
    allow_notifications_from = models.CharField(max_length=64, default="ALL_FRIENDS")
    allow_send_notifications_to = models.CharField(max_length=64, default="ALL_FRIENDS")
    allow_start_private_chat_for = models.CharField(max_length=64, default="ALL")
    allow_invite_to_group_chat_for = models.CharField(max_length=64, default="ALL")
    allow_collecting_stats_from = models.CharField(max_length=64, default="ALL_CHATS")

    words_allow_comments = models.BooleanField(default=True)
    collections_allow_comments = models.BooleanField(default=True)
    collections_allow_suggestions = models.BooleanField(default=True)
    collections_allow_suggestions_notifications = models.BooleanField(default=True)

    show_achievements_for = models.CharField(max_length=64, default="FRIENDS")
    show_certificates_for = models.CharField(max_length=64, default="FRIENDS")
    show_online_status_for = models.CharField(max_length=64, default="FRIENDS")
    show_strike_status_for = models.CharField(max_length=64, default="FRIENDS")
    private_account = models.BooleanField(default=False)

    auto_problematic_words = models.BooleanField(default=True)
    hide_suggested_content = models.BooleanField(default=False)
    only_premium_content = models.BooleanField(default=False)

    words_default_cards_type = models.CharField(max_length=8, default="STD")
    words_default_access_level = models.CharField(
        max_length=8, null=True, blank=True, default="PUBLIC"
    )
    collections_default_access_level = models.CharField(
        max_length=8, null=True, blank=True, default="PUBLIC"
    )

    user = models.OneToOneField(
        SaUser,
        on_delete=models.CASCADE,  # фактически в БД CASCADE
        db_column="user_id",
        related_name="settings",
    )

    class Meta:
        managed = False
        db_table = "users_usersettings"

    def __str__(self) -> str:
        return f"Settings({self.user_id})"


class SaSubscription(SaStampedModel):
    """
    users_subscription
    """

    enable_notifications = models.BooleanField(default=True)
    new_words = models.TextField(null=True, blank=True)
    updated_words = models.TextField(null=True, blank=True)
    new_collections = models.TextField(null=True, blank=True)

    subscriber = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="subscriber_id",
        related_name="subscriptions_detail",
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="user_id",
        related_name="subscribers_detail",
    )

    class Meta:
        managed = False
        db_table = "users_subscription"
        constraints = [
            models.UniqueConstraint(
                fields=["subscriber", "user"], name="unique_subscription"
            ),
            models.CheckConstraint(
                check=~models.Q(subscriber=models.F("user")),
                name="subscriber_not_same_user",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.subscriber_id} -> {self.user_id}"


class SaFriend(SaStampedModel):
    """
    users_friend
    """

    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="user_id",
        related_name="friends_as_user",
    )
    friend = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="friend_id",
        related_name="friends_as_friend",
    )

    class Meta:
        managed = False
        db_table = "users_friend"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "friend"], name="unique_friend_pair"
            ),
            models.CheckConstraint(
                check=~models.Q(user=models.F("friend")), name="friend_not_same_user"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} <-> {self.friend_id}"


class SaFriendRequest(SaStampedModel):
    """
    users_friendrequest
    """

    requester = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="requester_id",
        related_name="friend_requests_sent",
    )
    target = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="target_id",
        related_name="friend_requests_received",
    )

    class Meta:
        managed = False
        db_table = "users_friendrequest"
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "target"], name="unique_friend_request"
            ),
            models.CheckConstraint(
                check=~models.Q(requester=models.F("target")),
                name="friendrequest_not_same_user",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.requester_id} -> {self.target_id}"


class SaSocialLink(SaStampedModel):
    """
    users_sociallink
    """

    name = models.CharField(max_length=128)
    link = models.CharField(max_length=1024)

    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="user_id",
        related_name="socials",
    )

    class Meta:
        managed = False
        db_table = "users_sociallink"
        constraints = [
            models.UniqueConstraint(fields=["name", "user"], name="unique_user_social"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}: {self.name}"


class SaCity(SaStampedModel):
    """
    users_city
    M2M к users_user через таблицу users_user_cities (имя нужно уточнить!)
    """

    name = models.CharField(max_length=128)

    class Meta:
        managed = False
        db_table = "users_city"

    def __str__(self) -> str:
        return self.name


class SaInterest(SaStampedModel):
    """
    users_interest
    M2M к users_user через users_user_interests (имя нужно уточнить!)
    """

    name = models.CharField(max_length=128)
    cover = models.CharField(max_length=1024, null=True, blank=True)

    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="author_id",
        null=True,
        blank=True,
        related_name="custom_interests",
    )

    class Meta:
        managed = False
        db_table = "users_interest"
        constraints = [
            models.UniqueConstraint(fields=["name", "author"], name="unique_interest"),
        ]

    def __str__(self) -> str:
        return self.name


class SaGoal(SaStampedModel):
    """
    users_goal
    """

    name = models.CharField(max_length=128)
    description = models.CharField(max_length=512, null=True, blank=True)
    open_access = models.BooleanField(default=False)

    date_start = models.DateTimeField(null=True, blank=True)
    date_end = models.DateTimeField(null=True, blank=True)

    achievement = models.ForeignKey(
        SaAchievement,
        on_delete=models.DO_NOTHING,  # фактически SET NULL
        db_column="achievement_id",
        null=True,
        blank=True,
        related_name="user_goals",
    )
    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="author_id",
        related_name="goals",
    )

    class Meta:
        managed = False
        db_table = "users_goal"

    def __str__(self) -> str:
        return f"{self.author_id}: {self.name}"


class SaGoalMember(SaStampedModel):
    """
    users_goalmember
    """

    goal_status = models.CharField(max_length=16, default="active")
    date_finished = models.DateTimeField(null=True, blank=True)
    send_notifications_from_others = models.BooleanField(default=True)

    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="user_id",
        related_name="member_in_goals",
    )
    goal = models.ForeignKey(
        SaGoal,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="goal_id",
        related_name="members",
    )

    class Meta:
        managed = False
        db_table = "users_goalmember"
        constraints = [
            models.UniqueConstraint(fields=["user", "goal"], name="unique_goal_member"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.goal_id}"


class SaStudyPlan(SaStampedModel):
    """
    users_studyplan
    """

    name = models.CharField(max_length=128)
    description = models.CharField(max_length=512, null=True, blank=True)

    new_words_task = models.SmallIntegerField(null=True, blank=True)
    words_usage_amount_task = models.SmallIntegerField(null=True, blank=True)

    every = models.IntegerField(null=True, blank=True)
    period = models.CharField(max_length=24, default="days")

    new_words_task_weekly = models.TextField(null=True, blank=True)
    words_usage_amount_task_weekly = models.TextField(null=True, blank=True)
    break_days = models.SmallIntegerField(null=True, blank=True)
    study_week_days = models.TextField(null=True, blank=True)

    notification_time = models.TimeField(null=True, blank=True)

    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="author_id",
        related_name="study_plans",
    )

    class Meta:
        managed = False
        db_table = "users_studyplan"

    def __str__(self) -> str:
        return f"{self.author_id}: {self.name}"


class SaStrikeSeriaHistory(SaStampedModel):
    """
    users_strikeseriahistory
    """

    strike_start_date = models.DateTimeField()
    strike_end_date = models.DateTimeField(null=True, blank=True)

    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # фактически CASCADE
        db_column="user_id",
        related_name="strike_history",
    )

    class Meta:
        managed = False
        db_table = "users_strikeseriahistory"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "strike_start_date"], name="unique_strike_seria"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}: {self.strike_start_date}"
