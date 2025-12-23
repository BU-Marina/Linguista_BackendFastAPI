"""initial chats models (tables, fks, checks)

Revision ID: 0007_initial_chats
Revises: 0006_initial_exercises
Create Date: 2025-11-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0007_initial_chats"
down_revision = "0006_initial_exercises"
branch_labels = None
depends_on = None


def upgrade():
    # --- chats_chat ---
    op.create_table(
        "chats_chat",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=32), nullable=True),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("chat_image", sa.String(length=1024), nullable=True),
        sa.Column("chat_type", sa.String(length=1), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_chats_chat_created_modified", "chats_chat", ["created", "modified"])

    # CHECK constraint for chat_type values
    op.execute(
        "ALTER TABLE chats_chat ADD CONSTRAINT chk_chats_chat_type "
        "CHECK (chat_type IN ('P','G','O'));"
    )

    # --- association tables (tags, languages_used, blocked_users) ---
    op.create_table(
        "chats_chat_tags",
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats_chat.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core_tag.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    op.create_table(
        "chats_chat_languages_used",
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats_chat.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages_language.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    op.create_table(
        "chats_chat_blocked_users",
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats_chat.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # --- chats_chatmember (through model) ---
    op.create_table(
        "chats_chatmember",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats_chat.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("allow_invite_members", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_edit_chat", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_block_users", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_unique_constraint("unique_chat_member", "chats_chatmember", ["chat_id", "user_id"])
    op.create_index("ix_chats_chatmember_created", "chats_chatmember", ["created"])

    # --- chats_message ---
    op.create_table(
        "chats_message",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats_chat.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.String(length=512), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_chats_message_created", "chats_message", ["created"])

    # --- chats_attachment ---
    op.create_table(
        "chats_attachment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats_message.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image", sa.String(length=1024), nullable=True),
        sa.Column("file", sa.String(length=1024), nullable=True),
    )
    op.create_index("ix_chats_attachment_created", "chats_attachment", ["created"])


def downgrade():
    # drop in reverse order
    op.drop_index("ix_chats_attachment_created", table_name="chats_attachment")
    op.drop_table("chats_attachment")

    op.drop_index("ix_chats_message_created", table_name="chats_message")
    op.drop_table("chats_message")

    op.drop_index("ix_chats_chatmember_created", table_name="chats_chatmember")
    op.drop_constraint("unique_chat_member", "chats_chatmember", type_="unique")
    op.drop_table("chats_chatmember")

    op.drop_table("chats_chat_blocked_users")
    op.drop_table("chats_chat_languages_used")
    op.drop_table("chats_chat_tags")

    # drop check constraint
    op.execute("ALTER TABLE chats_chat DROP CONSTRAINT IF EXISTS chk_chats_chat_type;")
    op.drop_index("ix_chats_chat_created_modified", table_name="chats_chat")
    op.drop_table("chats_chat")