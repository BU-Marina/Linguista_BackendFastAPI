"""add_server_defaults_and_trigger_for_created_modified

Revision ID: 0016_add_default_created_modified
Revises: e2369e26e104
Create Date: 2025-11-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_update_created_modified"
down_revision = "35726386f14e"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Backfill существующих NULL created значением now()
    op.execute("UPDATE users_user SET created = now() WHERE created IS NULL;")

    # 2) Установить server_default и nullable=False для created
    op.alter_column(
        "users_user",
        "created",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
    op.alter_column(
        "users_user",
        "modified",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )

    # 3) Создать функцию и триггер для автоматического обновления modified при UPDATE
    op.execute(
        r"""
CREATE OR REPLACE FUNCTION public.touch_users_user_modified()
RETURNS trigger AS $$
BEGIN
  NEW.modified = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
    )

    op.execute(
        r"""
DROP TRIGGER IF EXISTS trg_users_user_modified ON public.users_user;
CREATE TRIGGER trg_users_user_modified
BEFORE UPDATE ON public.users_user
FOR EACH ROW
EXECUTE FUNCTION public.touch_users_user_modified();
"""
    )


def downgrade():
    # отмена: удалить триггер/функцию и убрать server_default (оставить nullable как было)
    op.execute("DROP TRIGGER IF EXISTS trg_users_user_modified ON public.users_user;")
    op.execute("DROP FUNCTION IF EXISTS public.touch_users_user_modified();")

    # убрать server_default (оставляем nullable=False/True в зависимости от желаемого отката)
    op.alter_column(
        "users_user",
        "created",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        # В downgrade можно вернуть nullable=True если нужно, но осторожно:
        # nullable=True,
    )
