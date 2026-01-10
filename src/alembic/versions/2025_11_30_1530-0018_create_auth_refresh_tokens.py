"""create auth_refresh_tokens table

Revision ID: 0019_create_auth_refresh_tokens
Revises: 0018_create_users_user_interests
Create Date: 2025-12-XX 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_create_auth_refresh_tokens"
down_revision = "0017_update_slug_max_length"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(
        op.f("authtoken_token_key_10f0b77e_like"),
        table_name="authtoken_token",
        postgresql_ops={"key": "varchar_pattern_ops"},
    )
    op.drop_table("authtoken_token")

    op.create_table(
        "auth_refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users_user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("device_info", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
    )


def downgrade():
    op.drop_table("auth_refresh_tokens")

    op.create_table(
        "authtoken_token",
        sa.Column("key", sa.VARCHAR(length=40), autoincrement=False, nullable=False),
        sa.Column(
            "created",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users_user.id"],
            name=op.f("authtoken_token_user_id_35299eff_fk_users_user_id"),
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("authtoken_token_pkey")),
        sa.UniqueConstraint(
            "user_id",
            name=op.f("authtoken_token_user_id_key"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
