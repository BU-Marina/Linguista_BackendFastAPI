"""initial notifications models with CHECK for notification_type

Revision ID: 0004_initial_notifications
Revises: 0003_initial_achievements
Create Date: 2025-11-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0004_initial_notifications"
down_revision = "0003_initial_achievements"
branch_labels = None
depends_on = None


def upgrade():
    # --- notifications_notification ---
    op.create_table(
        "notifications_notification",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notification_type", sa.String(length=64), nullable=False),
        sa.Column("from_object", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_seen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        # FK
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_notifications_created", "notifications_notification", ["created"])

    # CHECK constraint for notification_type values
    op.execute(
        "ALTER TABLE notifications_notification ADD CONSTRAINT chk_notifications_notification_type "
        "CHECK (notification_type IN ("
        "'word_activity_status_change','word_activity_status_downgrade_warning','word_activity_status_downgrade_warning_group',"
        "'subscribed_collection_update','new_suggested_words','new_suggested_words_group',"
        "'friend_request','subscribed_author_update'"
        "));"
    )


def downgrade():
    # drop check constraint
    op.execute("ALTER TABLE notifications_notification DROP CONSTRAINT IF EXISTS chk_notifications_notification_type;")
    op.drop_index("ix_notifications_created", table_name="notifications_notification")
    op.drop_table("notifications_notification")