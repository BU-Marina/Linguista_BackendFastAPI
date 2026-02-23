"""add dominant_color to image_association

Revision ID: 0007_add_dominant_color_to_image_association
Revises: 0006_initial_exercises
Create Date: 2026-02-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_02_19_1400_dominant_color'
down_revision = '2026_01_28_1400_add_input_mode'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add dominant_color column to vocabulary_imageassociation
    op.add_column(
        'vocabulary_imageassociation',
        sa.Column('dominant_color', sa.String(length=7), nullable=True),
    )


def downgrade() -> None:
    # Remove dominant_color column
    op.drop_column('vocabulary_imageassociation', 'dominant_color')
