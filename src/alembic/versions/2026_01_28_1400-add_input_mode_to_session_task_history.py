"""Add input_mode column to exercises_exercisesessiontaskshistory

Revision ID: 2026_01_28_1400_add_input_mode_to_session_task_history
Revises: 2026_01_14_1800-add_word_language_id_index
Create Date: 2026-01-28 14:00:00.000000
"""

from alembic import op


revision = '2026_01_28_1400_add_input_mode'
down_revision = '2026_01_14_1800'
branch_labels = None
depends_on = None


def upgrade():
    # Add NOT NULL input_mode with default 'FI' (matches ExercisesInputModeEnum.FREE_INPUT)
    # Use IF NOT EXISTS to avoid duplicate-column errors on already migrated DBs.
    op.execute(
        """
       ALTER TABLE exercises_exercisesessiontaskshistory
       ADD COLUMN IF NOT EXISTS input_mode VARCHAR(3) NOT NULL DEFAULT 'FI';
       """
    )


def downgrade():
    op.drop_column('exercises_exercisesessiontaskshistory', 'input_mode')
