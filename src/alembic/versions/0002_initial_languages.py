"""initial languages models (with case-insensitive slug indexes)

Revision ID: 0002_initial_languages
Revises: 0001_initial_users
Create Date: 2025-11-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0002_initial_languages"
down_revision = "0001_initial_users"
branch_labels = None
depends_on = None


def upgrade():
    # --- languages_language ---
    op.create_table(
        "languages_language",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("name_local", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("isocode", sa.String(length=8), nullable=False),
        sa.Column("country", sa.String(length=256), nullable=True, server_default=""),
        sa.Column("sorting", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("learning_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("interface_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("flag_icon", sa.String(length=1024), nullable=True),
    )
    op.create_index("ix_languages_language_sorting_name_isocode", "languages_language", ["sorting", "name", "isocode"])
    op.create_unique_constraint("uq_languages_language_isocode", "languages_language", ["isocode"])

    # --- languages_languagecoverimage ---
    op.create_table(
        "languages_languagecoverimage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages_language.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image", sa.String(length=1024), nullable=False),
        sa.Column("default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_languages_languagecoverimage_created", "languages_languagecoverimage", ["created"])

    # --- languages_userlearninglanguage ---
    op.create_table(
        "languages_userlearninglanguage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages_language.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cover_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages_languagecoverimage.id", ondelete="SET NULL"), nullable=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=True, server_default=""),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_taught", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_unique_constraint("unique_user_learning_language", "languages_userlearninglanguage", ["language_id", "user_id"])
    op.create_index("ix_languages_userlearninglanguage_created", "languages_userlearninglanguage", ["created"])
    # case-insensitive unique index on slug
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_languages_userlearninglanguage_lower_slug ON languages_userlearninglanguage ((lower(slug)));")

    # --- languages_usernativelanguage ---
    op.create_table(
        "languages_usernativelanguage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages_language.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
    )
    op.create_unique_constraint("unique_user_native_language", "languages_usernativelanguage", ["language_id", "user_id"])
    op.create_index("ix_languages_usernativelanguage_created", "languages_usernativelanguage", ["created"])
    # case-insensitive unique index on slug
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_languages_usernativelanguage_lower_slug ON languages_usernativelanguage ((lower(slug)));")


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_languages_usernativelanguage_lower_slug;")
    op.drop_index("ix_languages_usernativelanguage_created", table_name="languages_usernativelanguage")
    op.drop_constraint("unique_user_native_language", "languages_usernativelanguage", type_="unique")
    op.drop_table("languages_usernativelanguage")

    op.execute("DROP INDEX IF EXISTS uq_languages_userlearninglanguage_lower_slug;")
    op.drop_index("ix_languages_userlearninglanguage_created", table_name="languages_userlearninglanguage")
    op.drop_constraint("unique_user_learning_language", "languages_userlearninglanguage", type_="unique")
    op.drop_table("languages_userlearninglanguage")

    op.drop_index("ix_languages_languagecoverimage_created", table_name="languages_languagecoverimage")
    op.drop_table("languages_languagecoverimage")

    op.drop_constraint("uq_languages_language_isocode", "languages_language", type_="unique")
    op.drop_index("ix_languages_language_sorting_name_isocode", table_name="languages_language")
    op.drop_table("languages_language")