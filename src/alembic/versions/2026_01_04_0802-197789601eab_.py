"""empty message

Revision ID: 197789601eab
Revises: 0024_localized_name_fields
Create Date: 2026-01-04 08:02:37.640528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "197789601eab"
down_revision: Union[str, Sequence[str], None] = "0024_localized_name_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "users_user",
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "users_user",
        sa.Column(
            "is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("users_user", "is_blocked")
    op.drop_column("users_user", "is_deleted")

    # ### end Alembic commands ###
