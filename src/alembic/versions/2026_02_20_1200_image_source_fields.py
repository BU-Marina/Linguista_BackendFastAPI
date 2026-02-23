"""add source fields to image_association

Revision ID: 2026_02_20_1200_image_source_fields
Revises: 2026_02_19_1400_dominant_color
Create Date: 2026-02-20 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_02_20_1200_image_source'
down_revision = '2026_02_19_1400_dominant_color'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'vocabulary_imageassociation',
        sa.Column('source', sa.String(length=8), nullable=True),
    )
    op.add_column(
        'vocabulary_imageassociation',
        sa.Column('source_url', sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('vocabulary_imageassociation', 'source_url')
    op.drop_column('vocabulary_imageassociation', 'source')
