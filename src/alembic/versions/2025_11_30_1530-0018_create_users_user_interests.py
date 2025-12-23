"""create users_user_interests association table

Revision ID: 00xx_create_users_user_interests
Revises: <CURRENT_DOWN_REVISION>
Create Date: 2025-11-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_create_users_user_interests"
down_revision = "0017_update_slug_max_length"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "users_user_interests",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("interest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_interest.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "users_user_cities",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("city_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_city.id", ondelete="CASCADE"), primary_key=True),
    )

def downgrade():
    op.drop_table("users_user_interests")
    op.drop_table("users_user_cities")
