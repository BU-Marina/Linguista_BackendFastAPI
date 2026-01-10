"""empty message

Revision ID: 8dbf4507cd02
Revises: 0019_create_auth_refresh_tokens
Create Date: 2025-12-23 16:28:26.578313

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0019_vocabulary_remove_image"
down_revision: Union[str, Sequence[str], None] = "0018_create_auth_refresh_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "vocabulary_imageassociation",
        "image_url",
        existing_type=sa.VARCHAR(length=512),
        type_=sa.String(length=1024),
        existing_nullable=True,
        nullable=True,
    )

    # 2) Copy data
    op.execute(
        """
        UPDATE vocabulary_imageassociation
        SET image_url = image
        WHERE image_url IS NULL AND image IS NOT NULL
        """
    )

    # 3) Запретить NULL после переноса:
    op.alter_column(
        "vocabulary_imageassociation",
        "image_url",
        existing_type=sa.String(length=1024),
        existing_nullable=False,
        nullable=False,
    )

    # 4) Drop irrelevant column
    op.drop_column("vocabulary_imageassociation", "image")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "vocabulary_imageassociation",
        sa.Column("image", sa.String(length=1024), nullable=True),
    )

    # 2) Copy back
    op.execute(
        """
        UPDATE vocabulary_imageassociation
        SET image = image_url
        WHERE image IS NULL AND image_url IS NOT NULL
        """
    )

    op.alter_column(
        "vocabulary_imageassociation",
        "image_url",
        existing_type=sa.String(length=1024),
        type_=sa.VARCHAR(length=512),
        existing_nullable=True,
    )
