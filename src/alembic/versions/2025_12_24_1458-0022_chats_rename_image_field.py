"""
Rename Chat.chat_image -> chat_image_url and copy values.

Revision ID: xxxx_chat_image_to_image_url
Revises: yyyy_previous_revision
Create Date: 2025-12-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_chats_image_url"
down_revision = "0021_achievements_image_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add new column (nullable на время миграции)
    op.add_column(
        "chats_chat",
        sa.Column("chat_image_url", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "chats_attachment",
        sa.Column("image_url", sa.String(length=1024), nullable=True),
    )

    # 2) Copy data
    op.execute(
        """
        UPDATE chats_chat
        SET chat_image_url = chat_image
        WHERE chat_image_url IS NULL AND chat_image IS NOT NULL
        """
    )

    # 4) Drop old column
    op.drop_column("chats_chat", "chat_image")
    op.drop_column("chats_attachment", "image")


def downgrade() -> None:
    # 1) Restore old column
    op.add_column(
        "chats_chat",
        sa.Column("chat_image", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "chats_attachment",
        sa.Column("image", sa.String(length=1024), nullable=True),
    )

    # 2) Copy back
    op.execute(
        """
        UPDATE chats_chat
        SET chat_image = chat_image_url
        WHERE chat_image IS NULL AND chat_image_url IS NOT NULL
        """
    )

    # 3) Drop new column
    op.drop_column("chats_chat", "chat_image_url")
    op.drop_column("chats_attachment", "image_url")
