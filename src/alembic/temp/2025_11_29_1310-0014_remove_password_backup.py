"""remove password field
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0014_remove_password_backup"
down_revision = "0013_password_backup"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("users_user", "password_backup")

def downgrade():
    op.add_column("users_user", sa.Column("password_backup", sa.String(length=1024), nullable=True))