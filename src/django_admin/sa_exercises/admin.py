"""..."""

from django.contrib import admin

from sa_core.admin_i18n import I18nTabbedAdmin

from .models import (
    SaExercise,
    SaFavoriteExercise,
    SaHint,
    SaWordsSet,
    SaExerciseSessionHistory,
    SaExerciseSessionTasksHistory,
    SaExerciseConfiguration,
    SaCustomExerciseConfiguration,
    SaCustomGap,
    SaExercisesSet,
    SaExerciseSchedule,
)


@admin.register(SaExercise)
class ExerciseAdmin(I18nTabbedAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "description", "constraint_description", "available")
    list_display_links = ("name",)
    search_fields = ("name",)


@admin.register(SaFavoriteExercise)
class FavoriteExerciseAdmin(admin.ModelAdmin):
    pass


@admin.register(SaHint)
class HintAdmin(I18nTabbedAdmin):
    fieldsets = (
        (
            "Translations",
            {
                "fields": (
                    "name_ru",
                    "name_en",
                    "description_ru",
                    "description_en",
                )
            },
        ),
        ("Other", {"fields": ("id",)}),
    )

    list_display = ("id", "name", "description")
    list_display_links = ("id",)


@admin.register(SaWordsSet)
class WordsSetAdmin(admin.ModelAdmin):
    pass


@admin.register(SaExerciseSessionHistory)
class ExerciseSessionHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "exercise", "tasks_amount", "complete_time")
    list_display_links = ("id",)
    list_filter = ("exercise",)
    search_fields = ("exercise", "user")


@admin.register(SaExerciseSessionTasksHistory)
class ExerciseSessionTasksHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task",
        "task_type",
        "answer",
        "verdict",
        "session",
        "input_mode",
    )
    list_display_links = ("id",)
    list_filter = ("session",)
    search_fields = ("task", "answers_list")
    ordering = ("-created",)


@admin.register(SaExerciseConfiguration)
class ExercisesConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "exercise",
        "input_mode",
        "answer_time_limit",
        "time_limit_mode",
        "repetitions_amount",
        "translations_mode",
        "is_default",
    )
    list_display_links = ("id",)
    list_filter = ("author", "exercise")


@admin.register(SaCustomExerciseConfiguration)
class CustomExerciseConfigurationAdmin(admin.ModelAdmin):
    pass


@admin.register(SaCustomGap)
class CustomGapAdmin(admin.ModelAdmin):
    pass


@admin.register(SaExercisesSet)
class ExercisesSetAdmin(admin.ModelAdmin):
    pass


@admin.register(SaExerciseSchedule)
class ExerciseScheduleAdmin(admin.ModelAdmin):
    pass
