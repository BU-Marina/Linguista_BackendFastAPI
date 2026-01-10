"""
Rename LanguageCoverImage.image -> image_url and copy values.

Revision ID: xxxx_language_cover_image_image_to_image_url
Revises: yyyy_previous_revision
Create Date: 2025-12-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_languages_image_url"
down_revision = "0019_vocabulary_remove_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add new column (nullable на время миграции)
    op.add_column(
        "languages_languagecoverimage",
        sa.Column("image_url", sa.String(length=1024), nullable=True),
    )

    # 2) Copy data
    op.execute(
        """
        UPDATE languages_languagecoverimage
        SET image_url = image
        WHERE image_url IS NULL AND image IS NOT NULL
        """
    )

    # 3) Запретить NULL после переноса:
    op.alter_column(
        "languages_languagecoverimage",
        "image_url",
        existing_type=sa.String(length=1024),
        nullable=False,
    )

    # 4) Drop old column
    op.drop_column("languages_languagecoverimage", "image")


def downgrade() -> None:
    # 1) Restore old column
    op.add_column(
        "languages_languagecoverimage",
        sa.Column("image", sa.String(length=1024), nullable=True),
    )

    # 2) Copy back
    op.execute(
        """
        UPDATE languages_languagecoverimage
        SET image = image_url
        WHERE image IS NULL AND image_url IS NOT NULL
        """
    )

    # 3) Drop new column
    op.drop_column("languages_languagecoverimage", "image_url")
