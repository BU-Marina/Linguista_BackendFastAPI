"""initial core models: tag and platformreview

Revision ID: 0009_initial_core
Revises: 0008_add_users_checks
Create Date: 2025-11-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0008_initial_core"
down_revision = "0007_initial_chats"
branch_labels = None
depends_on = None


def upgrade():
    # --- core_tag ---
    op.create_table(
        "core_tag",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_core_tag_created_modified", "core_tag", ["created", "modified"])
    # NOTE: functional unique index on lower(name)+author intentionally omitted per request

    # --- core_platformreview ---
    op.create_table(
        "core_platformreview",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text", sa.String(length=256), nullable=False),
        sa.Column("stars", sa.SmallInteger(), nullable=True),
        sa.Column("is_shown", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_core_platformreview_created", "core_platformreview", ["created"])
    # CHECK constraint: stars <= 5 (allow NULL)
    op.create_check_constraint(
        "chk_core_platformreview_stars_max",
        "core_platformreview",
        "stars IS NULL OR stars <= 5"
    )


def downgrade():
    # drop in reverse order
    op.drop_constraint("chk_core_platformreview_stars_max", "core_platformreview", type_="check")
    op.drop_index("ix_core_platformreview_created", table_name="core_platformreview")
    op.drop_table("core_platformreview")

    op.drop_index("ix_core_tag_created_modified", table_name="core_tag")
    op.drop_table("core_tag")