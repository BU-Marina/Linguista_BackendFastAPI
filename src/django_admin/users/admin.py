from django.contrib import admin
from .models import SaUser


@admin.register(SaUser)
class SaUserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "email",
        "username",
        "is_active",
        "is_superuser",
        "is_teacher",
        "subscription_plan",
        "date_joined",
    )
    list_filter = ("is_active", "is_superuser", "is_teacher", "subscription_plan")
    search_fields = ("email", "username", "first_name")
    readonly_fields = ("id", "date_joined", "last_login", "last_activity_date")
