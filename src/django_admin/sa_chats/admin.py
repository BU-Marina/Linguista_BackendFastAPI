"""Chats app admin panel."""

from django.contrib import admin

from .models import (
    SaChat,
    SaChatMember,
    SaMessage,
    SaAttachment,
)


@admin.register(SaChat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "chat_type", "created")
    list_display_links = ("id",)


@admin.register(SaChatMember)
class ChatMemberAdmin(admin.ModelAdmin):
    pass


@admin.register(SaMessage)
class MessageAdmin(admin.ModelAdmin):
    pass


@admin.register(SaAttachment)
class AttachmentAdmin(admin.ModelAdmin):
    pass
