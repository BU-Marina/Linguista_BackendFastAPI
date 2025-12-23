"""make users_user.hashed_password NOT NULL"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_hashed_password_notnull"
down_revision = "0010_add_hashed_password"
branch_labels = None
depends_on = None

def upgrade():
    # Перед выполнением этой миграции УБЕДИСЬ, что в таблице users_user
    # нет NULL в hashed_password — иначе миграция упадёт.
    op.alter_column("users_user", "hashed_password", nullable=False)

def downgrade():
    # Сделать колонку снова nullable
    op.alter_column(
        "users_user",
        "hashed_password",
        existing_type=sa.String(length=1024),
        nullable=True,
    )