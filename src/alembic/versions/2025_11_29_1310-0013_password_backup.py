"""rename password field and make it nullable to safe test
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0013_password_backup"
down_revision = "0012_add_fastapi_users_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE users_user RENAME COLUMN password TO password_backup;")
    op.alter_column("users_user", "password_backup", nullable=True)

def downgrade():
    op.execute("ALTER TABLE users_user RENAME COLUMN password_backup TO password;")