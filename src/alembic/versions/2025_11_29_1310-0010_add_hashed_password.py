"""add hashed_password to users_user (safe)"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_add_hashed_password"
down_revision = "5d70701e2a40"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "users_user",
        sa.Column("hashed_password", sa.String(length=1024), nullable=True)
    )

    op.execute("UPDATE users_user SET hashed_password = password WHERE password IS NOT NULL")

def downgrade():
    op.drop_column("users_user", "hashed_password")