"""Add friend and friend request tables (idempotent)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "0026_add_friend_tables"
down_revision = "197789601eab"
branch_labels = None
depends_on = None


def _has_table(conn, name: str) -> bool:
    inspector = inspect(conn)
    return name in inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    if not _has_table(conn, "users_friend"):
        op.create_table(
            "users_friend",
            sa.Column(
                "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
            ),
            sa.Column(
                "created",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users_user.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "friend_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users_user.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.CheckConstraint("user_id <> friend_id", name="friend_not_same_user"),
            sa.UniqueConstraint("user_id", "friend_id", name="unique_friend_pair"),
        )
        op.create_index("ix_users_friend_user_id", "users_friend", ["user_id"])
        op.create_index("ix_users_friend_friend_id", "users_friend", ["friend_id"])

    if not _has_table(conn, "users_friendrequest"):
        op.create_table(
            "users_friendrequest",
            sa.Column(
                "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
            ),
            sa.Column(
                "created",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "requester_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users_user.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "target_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users_user.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "requester_id <> target_id", name="friendrequest_not_same_user"
            ),
            sa.UniqueConstraint(
                "requester_id", "target_id", name="unique_friend_request"
            ),
        )
        op.create_index(
            "ix_users_friendrequest_requester_id",
            "users_friendrequest",
            ["requester_id"],
        )
        op.create_index(
            "ix_users_friendrequest_target_id", "users_friendrequest", ["target_id"]
        )


def downgrade() -> None:
    # keep data safe; only drop if exists
    conn = op.get_bind()
    if _has_table(conn, "users_friendrequest"):
        op.drop_table("users_friendrequest")
    if _has_table(conn, "users_friend"):
        op.drop_table("users_friend")
