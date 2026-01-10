"""Chats app db models."""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Table,
    Index,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from core.base import Base
from .constants import ChatsLengthLimits, ChatTypesEnum

# Association tables (M2M without explicit through)
chats_chat_tags = Table(
    "chats_chat_tags",
    Base.metadata,
    Column(
        "chat_id",
        PG_UUID(as_uuid=True),
        ForeignKey("chats_chat.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        PG_UUID(as_uuid=True),
        ForeignKey("core_tag.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

chats_chat_languages_used = Table(
    "chats_chat_languages_used",
    Base.metadata,
    Column(
        "chat_id",
        PG_UUID(as_uuid=True),
        ForeignKey("chats_chat.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "language_id",
        PG_UUID(as_uuid=True),
        ForeignKey("languages_language.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

chats_chat_blocked_users = Table(
    "chats_chat_blocked_users",
    Base.metadata,
    Column(
        "chat_id",
        PG_UUID(as_uuid=True),
        ForeignKey("chats_chat.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Chat(Base):
    """Чат."""

    # fields
    name = Column(String(ChatsLengthLimits.CHAT_NAME_MAX_LENGTH), nullable=True)
    description = Column(
        String(ChatsLengthLimits.CHAT_DESCRIPTION_MAX_LENGTH), nullable=True
    )
    chat_image_url = Column(String(1024), nullable=True)
    chat_type = Column(String(ChatTypesEnum.max_length), nullable=False)

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship("User", backref="chats_authored", lazy="selectin")

    # many-to-many relationships (tags, languages_used, blocked_users)
    tags = relationship(
        "Tag", secondary=chats_chat_tags, backref="chats", lazy="selectin"
    )
    languages_used = relationship(
        "Language",
        secondary=chats_chat_languages_used,
        backref="chats",
        lazy="selectin",
    )
    blocked_users = relationship(
        "User",
        secondary=chats_chat_blocked_users,
        backref="blocked_in_chats",
        lazy="selectin",
    )

    # members via ChatMember (through model)
    members = relationship(
        "User",
        secondary="chats_chatmember",  # ChatMember is an explicit model (table name -> chats_chatmember)
        backref="chats_member",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_chats_chat_created_modified", "created", "modified"),)

    def __repr__(self):
        return f"<Chat(id={self.id}, name={self.name})>"


class ChatMember(Base):
    """Участник чата."""

    # fields (none extra beyond booleans)

    # FK
    chat_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("chats_chat.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # fields
    allow_invite_members = Column(Boolean, nullable=False, server_default="false")
    allow_edit_chat = Column(Boolean, nullable=False, server_default="false")
    allow_block_users = Column(Boolean, nullable=False, server_default="false")

    # Relationships (FK)
    chat = relationship("Chat", backref="members_detail", lazy="selectin")
    user = relationship("User", backref="chats_member_detail", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="unique_chat_member"),
        Index("ix_chats_chatmember_created", "created"),
    )

    def __repr__(self):
        return f"<ChatMember(chat_id={self.chat_id}, user_id={self.user_id})>"


class Message(Base):
    """Сообщение."""

    # fields
    text = Column(String(ChatsLengthLimits.MESSAGE_TEXT_MAX_LENGTH), nullable=True)
    is_pinned = Column(Boolean, nullable=False, server_default="false")

    # FK
    chat_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("chats_chat.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    chat = relationship("Chat", backref="messages", lazy="selectin")
    author = relationship("User", backref="messages", lazy="selectin")

    __table_args__ = (Index("ix_chats_message_created", "created"),)

    def __repr__(self):
        return f"<Message(id={self.id}, chat_id={self.chat_id})>"


class Attachment(Base):
    """Приложение."""

    # fields
    media_url = Column(String(1024), nullable=True)

    # FK
    message_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("chats_message.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    message = relationship("Message", backref="attachments", lazy="selectin")

    __table_args__ = (Index("ix_chats_attachment_created", "created"),)

    def __repr__(self):
        return f"<Attachment(id={self.id}, message_id={self.message_id})>"
