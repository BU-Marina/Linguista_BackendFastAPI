from django.db import models


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
    image = models.CharField(max_length=1024, null=True, blank=True)
    profile_description = models.CharField(
        max_length=1024, null=True, blank=True
    )  # UsersLengthLimits.PROFILE_DESCRIPTION_MAX_LENGTH
    profile_header_image = models.CharField(max_length=1024, null=True, blank=True)

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

    show_interests = models.BooleanField(default=True)
    date_joined = models.DateTimeField(null=True, blank=True)

    # slug из вашего SlugMixin
    slug = models.CharField(max_length=255, unique=True, db_index=True)

    # hashed_password из SQLAlchemyBaseUserTable
    hashed_password = models.CharField(max_length=1024)

    # FK на study_plan (если хочешь отобразить как FK; можно и как просто UUIDField)
    study_plan_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "users_user"   # ВАЖНО: имя существующей таблицы
        managed = False           # Django НЕ создаёт/НЕ меняет эту таблицу
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return f"{self.username} ({self.email})"
