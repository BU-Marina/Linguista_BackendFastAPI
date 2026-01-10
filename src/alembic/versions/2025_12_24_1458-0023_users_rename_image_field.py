"""
Rename User.image -> profile_image_url and copy values.

Revision ID: xxxx_user_image_to_profile_image_url
Revises: yyyy_previous_revision
Create Date: 2025-12-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_users_image_url"
down_revision = "0022_chats_image_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add new columns
    op.add_column(
        "users_user",
        sa.Column("profile_image_url", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "users_user",
        sa.Column("profile_header_image_url", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "users_lessonblock",
        sa.Column("image_url", sa.String(length=1024), nullable=True),
    )

    # 2) Copy data
    op.execute(
        """
        UPDATE users_user
        SET profile_image_url = image
        WHERE profile_image_url IS NULL AND image IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE users_user
        SET profile_header_image_url = profile_header_image
        WHERE profile_header_image_url IS NULL AND profile_header_image IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE users_lessonblock
        SET image_url = image
        WHERE image_url IS NULL AND image IS NOT NULL
        """
    )

    # 4) Drop old columns
    op.drop_column("users_user", "image")
    op.drop_column("users_user", "profile_header_image")
    op.drop_column("users_lessonblock", "image")


def downgrade() -> None:
    # 1) Restore old columns
    op.add_column(
        "users_user",
        sa.Column("image", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "users_user",
        sa.Column("profile_header_image", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "users_lessonblock",
        sa.Column("image", sa.String(length=1024), nullable=True),
    )

    # 2) Copy back
    op.execute(
        """
        UPDATE users_user
        SET image = profile_image_url
        WHERE image IS NULL AND profile_image_url IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE users_user
        SET profile_header_image = profile_header_image_url
        WHERE profile_header_image IS NULL AND profile_header_image_url IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE users_lessonblock
        SET image = image_url
        WHERE image IS NULL AND image_url IS NOT NULL
        """
    )

    # 3) Drop new columns
    op.drop_column("users_user", "profile_image_url")
    op.drop_column("users_user", "profile_header_image_url")
    op.drop_column("users_lessonblock", "image_url")
