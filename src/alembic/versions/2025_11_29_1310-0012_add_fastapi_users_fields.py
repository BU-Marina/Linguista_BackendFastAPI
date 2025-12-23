"""add fastapi-users fields to users_user

Revision ID: 000X_add_fastapi_users_fields
Revises: 0011_hashed_password_notnull
Create Date: 2025-11-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0012_add_fastapi_users_fields"
down_revision = "0011_hashed_password_notnull"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Булевы флаги fastapi-users (ставим server_default, чтобы существующие строки получили значение)
    op.add_column(
        "users_user",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    # Убираем добавленные колонки в обратном порядке
    op.drop_column("users_user", "is_verified")
