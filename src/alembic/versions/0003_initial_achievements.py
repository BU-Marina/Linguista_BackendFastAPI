"""initial achievements models with CHECK for achievement_type

Revision ID: 0003_initial_achievements
Revises: 0002_initial_languages
Create Date: 2025-11-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_initial_achievements"
down_revision = "0002_initial_languages"
branch_labels = None
depends_on = None


def upgrade():
    # --- achievements_achievementgroup ---
    op.create_table(
        "achievements_achievementgroup",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(length=64), nullable=False, unique=True),
    )
    op.create_index("ix_achievements_achievementgroup_created", "achievements_achievementgroup", ["created"])

    # --- achievements_achievement ---
    op.create_table(
        "achievements_achievement",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("image", sa.String(length=1024), nullable=True),
        sa.Column("open_access", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("achievement_type", sa.String(length=32), nullable=True),
        sa.Column("achievement_task_amount", sa.SmallInteger(), nullable=True),
        sa.Column("achievement_secondary_task_amount", sa.SmallInteger(), nullable=True),
        sa.Column("achievement_task_percent", sa.SmallInteger(), nullable=True),
        sa.Column("achievement_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("achievements_achievementgroup.id", ondelete="CASCADE"), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_achievements_achievement_created_modified", "achievements_achievement", ["created", "modified"])

    # functional unique index for case-insensitive name+author
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_achievements_achievement_lower_name_author "
        "ON achievements_achievement ((lower(name)), author_id);"
    )

    # --- achievements_achievement_users_access (association table) ---
    op.create_table(
        "achievements_achievement_users_access",
        sa.Column("achievement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("achievements_achievement.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # --- achievements_achievementprogress ---
    op.create_table(
        "achievements_achievementprogress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_amount", sa.SmallInteger(), nullable=True),
        sa.Column("progress_secondary_amount", sa.SmallInteger(), nullable=True),
        sa.Column("progress_percent", sa.SmallInteger(), nullable=True),
        sa.Column("is_accomplished", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("achievement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("achievements_achievement.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_user_achievement_progress", "achievements_achievementprogress", ["achievement_id", "user_id"])
    op.create_index("ix_achievements_achievementprogress_created_modified", "achievements_achievementprogress", ["created", "modified"])

    # --- CHECK constraint for achievement_type (case: allow NULL or only allowed values) ---
    # Values taken from AchievementTypeEnum.achievement_types
    op.execute(
        "ALTER TABLE achievements_achievement ADD CONSTRAINT chk_achievements_achievement_type "
        "CHECK (achievement_type IS NULL OR achievement_type IN ("
        "'words_save','collections_save','activity_status_amount','languages_add',"
        "'words_by_languages_amount','run_mistakes_correction','run_exercise','collection_activity',"
        "'study_groups','strike_seria','goals_accomplish','achievement_amount','materials_amount',"
        "'chats_words_usage','exercises_words_usage','chats_amount','friends_amount','favorite_author',"
        "'words_borrowings','collections_borrowings','grammars_borrowing','goal_members','collection_coauthors',"
        "'subscribers','settings'"
        "));"
    )


def downgrade():
    op.drop_index("ix_achievements_achievementprogress_created_modified", table_name="achievements_achievementprogress")
    op.drop_constraint("unique_user_achievement_progress", "achievements_achievementprogress", type_="unique")
    op.drop_table("achievements_achievementprogress")

    op.drop_table("achievements_achievement_users_access")

    # drop functional index for name+author
    op.execute("DROP INDEX IF EXISTS uq_achievements_achievement_lower_name_author;")
    op.drop_index("ix_achievements_achievement_created_modified", table_name="achievements_achievement")

    # drop check constraint
    op.execute("ALTER TABLE achievements_achievement DROP CONSTRAINT IF EXISTS chk_achievements_achievement_type;")

    op.drop_table("achievements_achievement")

    op.drop_index("ix_achievements_achievementgroup_created", table_name="achievements_achievementgroup")
    op.drop_table("achievements_achievementgroup")