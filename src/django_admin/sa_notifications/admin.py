"""Notifications app admin panel."""

from django.contrib import admin

from .models import (
    SaNotification,
)


@admin.register(SaNotification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "recipient",
        "notification_type",
        "from_object",
        "is_seen",
        "created",
    )
    search_fields = ("recipient__username",)
    list_filter = (
        "notification_type",
        "is_seen",
    )
    ordering = ("-created",)
