"""..."""

from __future__ import annotations

from django.db import models

from sa_core.mixins import SaStampedModel
from sa_core.models import SaTag
from sa_languages.models import SaLanguage
from sa_users.models import SaUser


# ----- Through tables for Chat M2M -----


class SaChatsChatTags(models.Model):
    chat = models.ForeignKey(
        "SaChat", on_delete=models.DO_NOTHING, db_column="chat_id", related_name="+"
    )
    tag = models.ForeignKey(
        SaTag, on_delete=models.DO_NOTHING, db_column="tag_id", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "chats_chat_tags"
        constraints = [
            models.UniqueConstraint(fields=["chat", "tag"], name="uniq_chat_tag"),
        ]


class SaChatsChatLanguagesUsed(models.Model):
    chat = models.ForeignKey(
        "SaChat", on_delete=models.DO_NOTHING, db_column="chat_id", related_name="+"
    )
    language = models.ForeignKey(
        SaLanguage,
        on_delete=models.DO_NOTHING,
        db_column="language_id",
        related_name="+",
    )

    class Meta:
        managed = False
        db_table = "chats_chat_languages_used"
        constraints = [
            models.UniqueConstraint(fields=["chat", "language"], name="uniq_chat_lang"),
        ]


class SaChatsChatBlockedUsers(models.Model):
    chat = models.ForeignKey(
        "SaChat", on_delete=models.DO_NOTHING, db_column="chat_id", related_name="+"
    )
    user = models.ForeignKey(
        SaUser, on_delete=models.DO_NOTHING, db_column="user_id", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "chats_chat_blocked_users"
        constraints = [
            models.UniqueConstraint(fields=["chat", "user"], name="uniq_chat_blocked"),
        ]


# ----- Main chat models -----


class SaChat(SaStampedModel):
    name = models.CharField(
        max_length=256,  # TODO: ChatsLengthLimits.CHAT_NAME_MAX_LENGTH
        null=True,
        blank=True,
    )
    description = models.CharField(
        max_length=2048,  # TODO: ChatsLengthLimits.CHAT_DESCRIPTION_MAX_LENGTH
        null=True,
        blank=True,
    )
    chat_image_url = models.CharField(max_length=1024, null=True, blank=True)

    chat_type = models.CharField(
        max_length=32,  # TODO: ChatTypesEnum.max_length
    )

    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="author_id",
        related_name="chats_authored",
    )

    tags = models.ManyToManyField(
        SaTag,
        through=SaChatsChatTags,
        related_name="chats",
        blank=True,
    )
    languages_used = models.ManyToManyField(
        SaLanguage,
        through=SaChatsChatLanguagesUsed,
        related_name="chats",
        blank=True,
    )
    blocked_users = models.ManyToManyField(
        SaUser,
        through=SaChatsChatBlockedUsers,
        related_name="blocked_in_chats",
        blank=True,
    )

    # members via ChatMember table (явная таблица chats_chatmember)
    members = models.ManyToManyField(
        SaUser,
        through="SaChatMember",
        related_name="chats_member",
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "chats_chat"

    def __str__(self) -> str:
        return self.name or str(self.id)


class SaChatMember(SaStampedModel):
    chat = models.ForeignKey(
        SaChat,
        on_delete=models.DO_NOTHING,  # CASCADE в БД
        db_column="chat_id",
        related_name="members_detail",
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # CASCADE в БД
        db_column="user_id",
        related_name="chats_member_detail",
    )

    allow_invite_members = models.BooleanField(default=False)
    allow_edit_chat = models.BooleanField(default=False)
    allow_block_users = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "chats_chatmember"
        constraints = [
            models.UniqueConstraint(fields=["chat", "user"], name="unique_chat_member"),
        ]

    def __str__(self) -> str:
        return f"{self.chat_id} / {self.user_id}"


class SaMessage(SaStampedModel):
    text = models.CharField(
        max_length=4096,  # TODO: ChatsLengthLimits.MESSaGE_TEXT_MAX_LENGTH
        null=True,
        blank=True,
    )
    is_pinned = models.BooleanField(default=False)

    chat = models.ForeignKey(
        SaChat,
        on_delete=models.DO_NOTHING,
        db_column="chat_id",
        related_name="messages",
    )
    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column="author_id",
        related_name="messages",
    )

    class Meta:
        managed = False
        db_table = "chats_message"

    def __str__(self) -> str:
        return f"{self.chat_id}: {self.id}"


class SaAttachment(SaStampedModel):
    media_url = models.CharField(max_length=1024, null=True, blank=True)

    message = models.ForeignKey(
        SaMessage,
        on_delete=models.DO_NOTHING,
        db_column="message_id",
        related_name="attachments",
    )

    class Meta:
        managed = False
        db_table = "chats_attachment"

    def __str__(self) -> str:
        return str(self.id)
