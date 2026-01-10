"""..."""

from __future__ import annotations

from django.db import models

from sa_core.mixins import SaStampedModel
from sa_users.models import SaUser


class SaNotification(SaStampedModel):
    notification_type = models.CharField(
        max_length=64,  # TODO: NotificationsLengthLimits.NOTIFICATION_TYPE_MAX_LENGTH
    )
    from_object = models.UUIDField(null=True, blank=True)

    # JSONB
    extra_data = models.JSONField(default=dict)
    is_seen = models.BooleanField(default=False)

    recipient = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="recipient_id",
        related_name="notifications",
    )

    class Meta:
        managed = False
        db_table = "notifications_notification"

    def __str__(self) -> str:
        return f"{self.id} -> {self.recipient_id} ({self.notification_type})"
