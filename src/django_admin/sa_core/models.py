from __future__ import annotations

from django.db import models

from .mixins import SaStampedModel


class SaTag(SaStampedModel):
    name = models.CharField(
        max_length=128,  # TODO: CoreLengthLimits.TAG_MAX_LENGTH
    )

    author = models.ForeignKey(
        "sa_users.SaUser",
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="author_id",
        related_name="tags",
    )

    class Meta:
        managed = False
        db_table = "core_tag"

    def __str__(self) -> str:
        return self.name
