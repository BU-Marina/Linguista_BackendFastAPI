"""Add index on vocabulary_word.language_id for performance

Revision ID: 2026_01_14_1800
Revises: 2026_01_10_1200_add_friend_tables
Create Date: 2026-01-14 18:00:00.000000
"""
from alembic import op

revision = '2026_01_14_1800'
down_revision = '0026_add_friend_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add index on vocabulary_word.language_id for global-languages query performance."""
    op.create_index(
        'ix_vocabulary_word_language_id',
        'vocabulary_word',
        ['language_id'],
        postgresql_concurrently=False,
    )


def downgrade() -> None:
    """Remove index on vocabulary_word.language_id."""
    op.drop_index('ix_vocabulary_word_language_id', table_name='vocabulary_word')
