"""Languages app admin panel."""

from django.contrib import admin

from sa_core.admin_i18n import I18nTabbedAdmin

from .models import (
    SaLanguage,
    SaLanguageCoverImage,
    SaUserNativeLanguage,
    SaUserLearningLanguage,
)


@admin.register(SaLanguage)
class SaLanguageAdmin(I18nTabbedAdmin):
    fieldsets = (
        (
            "Translations",
            {
                "fields": (
                    "name_ru",
                    "name_en",
                    "country_ru",
                    "country_en",
                )
            },
        ),
        (
            "Other",
            {
                "fields": (
                    "name_local",
                    "isocode",
                    "sorting",
                    "learning_available",
                    "interface_available",
                    "flag_icon",
                )
            },
        ),
    )

    list_display = (
        "name",
        "isocode",
        "name_local",
        "country",
        "sorting",
        "learning_available",
        "words_count",
    )
    search_fields = (
        "name_local",
        "name_en",
        "name_ru",
        "isocode",
    )
    ordering = ("-sorting", "isocode", "name_en")

    @admin.display(description="Name")
    def name(self, obj: SaLanguage) -> str:
        return obj.name_en or obj.name_ru or ""

    @admin.display(description="Country")
    def country(self, obj: SaLanguage) -> str:
        return obj.country_en or obj.country_ru or ""


@admin.register(SaLanguageCoverImage)
class SaLanguageCoverImageAdmin(admin.ModelAdmin):
    list_display = (
        "language",
        "image_url",
        "default",
        "created",
    )
    search_fields = (
        "language__name_local",
        "language__name_en",
        "language__name_ru",
        "language__country_en",
        "language__country_ru",
        "language__isocode",
    )
    ordering = ("-language__sorting", "language__name_en")
    list_filter = ("default",)


@admin.register(SaUserLearningLanguage)
class SaUserLearningLanguageAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("user", "language")}
    list_display = (
        "language",
        "user",
        "level",
        "is_confirmed",
        "is_taught",
        "created",
    )
    search_fields = (
        "language__name_local",
        "language__name_en",
        "language__name_ru",
        "language__isocode",
    )


@admin.register(SaUserNativeLanguage)
class SaUserNativeLanguageAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("user", "language")}
    pass
