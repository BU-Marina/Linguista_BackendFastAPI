"""
Rename Achievement.image -> image_url and copy values.

Revision ID: xxxx_achievement_image_to_image_url
Revises: yyyy_previous_revision
Create Date: 2025-12-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_achievements_image_url"
down_revision = "0020_languages_image_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add new column (nullable на время миграции)
    op.add_column(
        "achievements_achievement",
        sa.Column("image_url", sa.String(length=1024), nullable=True),
    )

    # 2) Copy data
    op.execute(
        """
        UPDATE achievements_achievement
        SET image_url = image
        WHERE image_url IS NULL AND image IS NOT NULL
        """
    )

    # 4) Drop old column
    op.drop_column("achievements_achievement", "image")


def downgrade() -> None:
    # 1) Restore old column
    op.add_column(
        "achievements_achievement",
        sa.Column("image", sa.String(length=1024), nullable=True),
    )

    # 2) Copy back
    op.execute(
        """
        UPDATE achievements_achievement
        SET image = image_url
        WHERE image IS NULL AND image_url IS NOT NULL
        """
    )

    # 3) Drop new column
    op.drop_column("achievements_achievement", "image_url")
