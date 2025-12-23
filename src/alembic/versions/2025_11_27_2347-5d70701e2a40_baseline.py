"""baseline

Revision ID: 5d70701e2a40
Revises: 0008_initial_core
Create Date: 2025-11-27 23:47:31.387119

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d70701e2a40'
down_revision: Union[str, Sequence[str], None] = '0008_initial_core'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
