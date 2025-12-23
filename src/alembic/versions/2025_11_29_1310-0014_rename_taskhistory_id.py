"""rename taskhistory_id -> exercisesessiontaskshistory_id

Revision ID: 000X_rename_taskhistory_id
Revises: <CURRENT_DOWN_REVISION>
Create Date: 2025-11-29 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0014_rename_taskhistory_id"
down_revision = "0013_password_backup"
branch_labels = None
depends_on = None


def _rename_if_exists(table_name: str, old_col: str, new_col: str) -> None:
    """
    Выполняет безопасное переименование колонки в PostgreSQL только если колонка old_col существует.
    Использует DO $$ BEGIN ... END $$; чтобы не падать при отсутствии колонки.
    """
    op.execute(
        f"""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = '{table_name}'
          AND column_name = '{old_col}'
    ) THEN
        EXECUTE format('ALTER TABLE public.{table_name} RENAME COLUMN {old_col} TO {new_col};');
    END IF;
END$$;
"""
    )


def _rename_back_if_exists(table_name: str, old_col: str, new_col: str) -> None:
    """
    Обратная операция: переименовать new_col -> old_col, если new_col существует.
    """
    op.execute(
        f"""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = '{table_name}'
          AND column_name = '{new_col}'
    ) THEN
        EXECUTE format('ALTER TABLE public.{table_name} RENAME COLUMN {new_col} TO {old_col};');
    END IF;
END$$;
"""
    )


def upgrade() -> None:
    tables = [
        "exercises_exercisesessiontaskshistory_hints_available",
        "exercises_exercisesessiontaskshistory_hints_used",
        "exercises_exercisesessiontaskshistory_right_answers_definitions",
        "exercises_exercisesessiontaskshistory_right_answers_words",
        "exercises_exercisesessiontaskshistory_right_answers_translations",
    ]
    for tbl in tables:
        _rename_if_exists(tbl, "taskhistory_id", "exercisesessiontaskshistory_id")


def downgrade() -> None:
    tables = [
        "exercises_exercisesessiontaskshistory_hints_available",
        "exercises_exercisesessiontaskshistory_hints_used",
        "exercises_exercisesessiontaskshistory_right_answers_definitions",
        "exercises_exercisesessiontaskshistory_right_answers_words",
        "exercises_exercisesessiontaskshistory_right_answers_translations",
    ]
    for tbl in tables:
        _rename_back_if_exists(tbl, "taskhistory_id", "exercisesessiontaskshistory_id")