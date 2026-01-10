"""..."""

from __future__ import annotations

from django.db import models

from sa_core.mixins import SaStampedModel, SaSlugModel, WordsCountMixin
from sa_users.models import SaUser


class SaLanguage(SaStampedModel, WordsCountMixin):
    """
    Таблица: languages_language
    """

    name_ru = models.CharField(max_length=256)
    name_en = models.CharField(max_length=256)
    name_local = models.CharField(max_length=256, default="", blank=True)
    isocode = models.CharField(max_length=8, unique=True, db_index=True)

    country_ru = models.CharField(max_length=256, null=True, blank=True, default="")
    country_en = models.CharField(max_length=256, null=True, blank=True, default="")

    sorting = models.IntegerField(default=0)
    learning_available = models.BooleanField(default=False)
    interface_available = models.BooleanField(default=False)

    flag_icon = models.CharField(max_length=1024, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "languages_language"

    def __str__(self) -> str:
        return f"{self.isocode} — {self.name_en}"


class SaLanguageCoverImage(SaStampedModel):
    """
    Таблица: languages_languagecoverimage
    """

    image_url = models.CharField(max_length=1024)
    default = models.BooleanField(default=False)

    language = models.ForeignKey(
        SaLanguage,
        on_delete=models.DO_NOTHING,  # реальный ondelete в БД: CASCADE
        db_column="language_id",
        related_name="images",
    )

    class Meta:
        managed = False
        db_table = "languages_languagecoverimage"

    def __str__(self) -> str:
        return f"CoverImage {self.id} lang={self.language_id} default={self.default}"


class SaUserLearningLanguage(SaStampedModel, SaSlugModel):
    """
    Таблица: languages_userlearninglanguage
    """

    level = models.CharField(max_length=32, null=True, blank=True, default="")
    is_confirmed = models.BooleanField(default=False)
    is_taught = models.BooleanField(default=False)

    language = models.ForeignKey(
        SaLanguage,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="language_id",
        related_name="learning_by_detail",
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="user_id",
        related_name="learning_languages_detail",
    )

    cover = models.ForeignKey(
        SaLanguageCoverImage,
        on_delete=models.DO_NOTHING,  # в БД SET NULL
        db_column="cover_id",
        null=True,
        blank=True,
        related_name="covers",
    )

    class Meta:
        managed = False
        db_table = "languages_userlearninglanguage"
        constraints = [
            # соответствует: UniqueConstraint("language_id", "user_id", name="unique_user_learning_language")
            models.UniqueConstraint(
                fields=["language", "user"],
                name="unique_user_learning_language",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} learns {self.language_id}"


class SaUserNativeLanguage(SaStampedModel, SaSlugModel):
    """
    Таблица: languages_usernativelanguage
    """

    language = models.ForeignKey(
        SaLanguage,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="language_id",
        related_name="native_for_detail",
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="user_id",
        related_name="native_languages_detail",
    )

    class Meta:
        managed = False
        db_table = "languages_usernativelanguage"
        constraints = [
            # соответствует: UniqueConstraint("language_id", "user_id", name="unique_user_native_language")
            models.UniqueConstraint(
                fields=["language", "user"],
                name="unique_user_native_language",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} native {self.language_id}"
