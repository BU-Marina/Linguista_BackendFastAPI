"""Achievements app admin panel."""

from django.contrib import admin

from .models import (
    SaAchievement,
    SaAchievementGroup,
    SaAchievementProgress,
)


@admin.register(SaAchievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "author",
        "open_access",
        "achievement_group",
        "achievement_type",
        "achievement_task_amount",
        "achievement_secondary_task_amount",
        "achievement_task_percent",
        "created",
    )
    list_display_links = ("name",)
    search_fields = ("name",)


@admin.register(SaAchievementGroup)
class AchievementGroupMemberAdmin(admin.ModelAdmin):
    list_display = ("title", "created")
    list_display_links = ("title",)


@admin.register(SaAchievementProgress)
class AchievementProgressAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "achievement",
        "progress_amount",
        "progress_secondary_amount",
        "progress_percent",
        "is_accomplished",
        "created",
    )
    list_display_links = ("id",)
    search_fields = ("user__username", "achievement__name")
