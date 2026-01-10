"""..."""

from __future__ import annotations

from django.db import models

from sa_core.mixins import SaStampedModel


# ===== secondary M2M таблица achievements_users_access =====


class SaAchievementUsersAccess(models.Model):
    """
    Through table для Achievement.users_access <-> User
    Обычно в таких таблицах есть только 2 FK и составной PK/unique.
    """

    achievement = models.ForeignKey(
        "SaAchievement",
        on_delete=models.DO_NOTHING,
        db_column="achievement_id",
        related_name="+",
    )
    user = models.ForeignKey(
        "sa_users.SaUser",
        on_delete=models.DO_NOTHING,
        db_column="user_id",
        related_name="+",
    )

    class Meta:
        managed = False
        db_table = "achievements_users_access"
        constraints = [
            models.UniqueConstraint(
                fields=["achievement", "user"], name="unique_achievement_user_access"
            ),
        ]


# -----------------------
# AchievementGroup
# -----------------------


class SaAchievementGroup(SaStampedModel):
    title = models.CharField(
        max_length=128,  # TODO: AchievementsLengthLimits.ACHIEVEMENT_GROUP_TITLE_MAX_LENGTH
        unique=True,
    )

    class Meta:
        managed = False
        db_table = "achievements_achievementgroup"

    def __str__(self) -> str:
        return self.title


# -----------------------
# Achievement
# -----------------------


class SaAchievement(SaStampedModel):
    name = models.CharField(
        max_length=128,  # TODO: AchievementsLengthLimits.ACHIEVEMENT_NAME_MAX_LENGTH
    )
    description = models.CharField(
        max_length=512,  # TODO: AchievementsLengthLimits.ACHIEVEMENT_DESCRIPTION_MAX_LENGTH
        null=True,
        blank=True,
    )
    image_url = models.CharField(max_length=1024, null=True, blank=True)

    open_access = models.BooleanField(default=False)

    achievement_type = models.CharField(
        max_length=64,  # TODO: AchievementTypeEnum.max_length
        null=True,
        blank=True,
    )
    achievement_task_amount = models.SmallIntegerField(null=True, blank=True)
    achievement_secondary_task_amount = models.SmallIntegerField(null=True, blank=True)
    achievement_task_percent = models.SmallIntegerField(null=True, blank=True)

    achievement_group = models.ForeignKey(
        SaAchievementGroup,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="achievement_group_id",
        null=True,
        blank=True,
        related_name="achievements",
    )
    author = models.ForeignKey(
        "sa_users.SaUser",
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="author_id",
        related_name="achievements",
    )

    # M2M users_access
    users_access = models.ManyToManyField(
        "sa_users.SaUser",
        through=SaAchievementUsersAccess,
        related_name="achievements_available",
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "achievements_achievement"
        # ВАЖНО: функциональный unique lower(name), author — не описываем тут, это Alembic.

    def __str__(self) -> str:
        return self.name


# -----------------------
# AchievementProgress
# -----------------------


class SaAchievementProgress(SaStampedModel):
    progress_amount = models.SmallIntegerField(null=True, blank=True)
    progress_secondary_amount = models.SmallIntegerField(null=True, blank=True)
    progress_percent = models.SmallIntegerField(null=True, blank=True)

    is_accomplished = models.BooleanField(default=False)

    achievement = models.ForeignKey(
        SaAchievement,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="achievement_id",
        related_name="users_progress",
    )
    user = models.ForeignKey(
        "sa_users.SaUser",
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="user_id",
        related_name="achievements_progress",
    )

    class Meta:
        managed = False
        db_table = "achievements_achievementprogress"
        constraints = [
            models.UniqueConstraint(
                fields=["achievement", "user"],
                name="unique_user_achievement_progress",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.achievement_id}"
