"""initial vocabulary models (tables, fks, functional unique indexes, checks)

Revision ID: 0005_initial_vocabulary
Revises: 0004_initial_notifications
Create Date: 2025-11-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_initial_vocabulary"
down_revision = "0004_initial_notifications"
branch_labels = None
depends_on = None


def upgrade():
    # --- vocabulary_word ---
    op.create_table(
        "vocabulary_word",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text", sa.String(length=256), nullable=False),
        sa.Column("activity_status", sa.String(length=1), nullable=False, server_default=sa.text("'I'")),
        sa.Column("activity_progress", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("is_problematic", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_trophie", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("note", sa.String(length=2048), nullable=True),
        sa.Column("last_exercise_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_word_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_comments", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages_language.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_vocabulary_word_created_modified", "vocabulary_word", ["created", "modified"])
    # UniqueConstraint('text','author','language') as in Django:
    op.create_unique_constraint("uq_vocabulary_word_text_author_language", "vocabulary_word", ["text", "author_id", "language_id"])
    # CHECK for activity_status (ActivityStatusEnum)
    op.execute(
        "ALTER TABLE vocabulary_word ADD CONSTRAINT chk_vocabulary_word_activity_status "
        "CHECK (activity_status IN ('I','A','M'));"
    )

    # --- vocabulary_wordtype (word types) ---
    op.create_table(
        "vocabulary_wordtype",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False, unique=True),
    )
    op.create_index("ix_vocabulary_wordtype_created", "vocabulary_wordtype", ["created"])

    # --- vocabulary_formgroup ---
    op.create_table(
        "vocabulary_formgroup",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages_language.id", ondelete="SET NULL"), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("translation", sa.String(length=64), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_vocabulary_formgroup_created_modified", "vocabulary_formgroup", ["created", "modified"])
    # functional unique for lower(name)+author
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_formgroup_lower_name_author "
        "ON vocabulary_formgroup ((lower(name)), author_id);"
    )

    # --- vocabulary_wordtranslation ---
    op.create_table(
        "vocabulary_wordtranslation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text", sa.String(length=256), nullable=False),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages_language.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_vocabulary_wordtranslation_created_modified", "vocabulary_wordtranslation", ["created", "modified"])
    # functional unique lower(text),author,language
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_wordtranslation_lower_text_author_language "
        "ON vocabulary_wordtranslation ((lower(text)), author_id, language_id);"
    )

    # --- vocabulary_definition ---
    op.create_table(
        "vocabulary_definition",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text", sa.String(length=512), nullable=False),
        sa.Column("translation", sa.String(length=512), nullable=True),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages_language.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_vocabulary_definition_created_modified", "vocabulary_definition", ["created", "modified"])
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_definition_lower_text_author "
        "ON vocabulary_definition ((lower(text)), author_id);"
    )

    # --- vocabulary_usageexample ---
    op.create_table(
        "vocabulary_usageexample",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text", sa.String(length=512), nullable=False),
        sa.Column("translation", sa.String(length=512), nullable=True),
        sa.Column("source", sa.String(length=3), nullable=False, server_default=sa.text("'OTH'")),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages_language.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_vocabulary_usageexample_created_modified", "vocabulary_usageexample", ["created", "modified"])
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_usageexample_lower_text_author "
        "ON vocabulary_usageexample ((lower(text)), author_id);"
    )

    # --- vocabulary_imageassociation ---
    op.create_table(
        "vocabulary_imageassociation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("image", sa.String(length=1024), nullable=True),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("width", sa.SmallInteger(), nullable=True),
        sa.Column("height", sa.SmallInteger(), nullable=True),
        sa.Column("num", sa.SmallInteger(), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_vocabulary_imageassociation_created_modified", "vocabulary_imageassociation", ["created", "modified"])

    # --- vocabulary_quoteassociation ---
    op.create_table(
        "vocabulary_quoteassociation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text", sa.String(length=256), nullable=False),
        sa.Column("quote_author", sa.String(length=64), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_vocabulary_quoteassociation_created_modified", "vocabulary_quoteassociation", ["created", "modified"])

    # --- vocabulary_collection ---
    op.create_table(
        "vocabulary_collection",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("allow_comments", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_suggestions", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_suggestions_notifications", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("source_collection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_vocabulary_collection_created_modified", "vocabulary_collection", ["created", "modified"])
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_collection_lower_title_author "
        "ON vocabulary_collection ((lower(title)), author_id);"
    )

    # --- vocabulary_collectionsubscription ---
    op.create_table(
        "vocabulary_collectionsubscription",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subscriber_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_collection.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enable_notifications", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("new_words", sa.Text(), nullable=True),
        sa.Column("updated_words", sa.Text(), nullable=True),
    )
    op.create_unique_constraint("unique_collection_subscription", "vocabulary_collectionsubscription", ["subscriber_id", "collection_id"])
    op.create_index("ix_vocabulary_collectionsubscription_created", "vocabulary_collectionsubscription", ["created"])

    # --- through/intermediary tables ---
    # words_form_groups
    op.create_table(
        "vocabulary_wordsformgroups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("forms_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_formgroup.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_unique_constraint("unique_word_forms_group", "vocabulary_wordsformgroups", ["word_id", "forms_group_id"])

    # word_translations intermediary
    op.create_table(
        "vocabulary_wordtranslations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("translation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_wordtranslation.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_word_translation", "vocabulary_wordtranslations", ["word_id", "translation_id"])

    # word_definitions
    op.create_table(
        "vocabulary_worddefinitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_definition.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_word_definition", "vocabulary_worddefinitions", ["word_id", "definition_id"])

    # word_usage_examples
    op.create_table(
        "vocabulary_wordusageexamples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("example_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_usageexample.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_word_example", "vocabulary_wordusageexamples", ["word_id", "example_id"])

    # word_image_associations
    op.create_table(
        "vocabulary_wordimageassociations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_imageassociation.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_word_image", "vocabulary_wordimageassociations", ["word_id", "image_id"])

    # word_quote_associations
    op.create_table(
        "vocabulary_wordquoteassociations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_quoteassociation.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_word_quote", "vocabulary_wordquoteassociations", ["word_id", "quote_id"])

    # words_in_collections
    op.create_table(
        "vocabulary_wordsincollections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_collection.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_word_in_collection", "vocabulary_wordsincollections", ["word_id", "collection_id"])

    # words_suggested_to_collections
    op.create_table(
        "vocabulary_wordssuggestedtocollections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_collection.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=1), nullable=False, server_default=sa.text("'P'")),
    )
    op.create_unique_constraint("unique_suggested_word", "vocabulary_wordssuggestedtocollections", ["word_id", "collection_id", "user_id"])
    # CHECK on status (RequestStatusEnum)
    op.execute(
        "ALTER TABLE vocabulary_wordssuggestedtocollections ADD CONSTRAINT chk_vocabulary_suggested_status "
        "CHECK (status IN ('A','R','P'));"
    )

    # --- comments and comment association tables ---
    # likes/dislikes for collection comments
    op.create_table(
        "vocabulary_collectioncomment_likes",
        sa.Column("collectioncomment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_collectioncomment.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    op.create_table(
        "vocabulary_collectioncomment_dislikes",
        sa.Column("collectioncomment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_collectioncomment.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    # likes/dislikes for word comments
    op.create_table(
        "vocabulary_wordcomment_likes",
        sa.Column("wordcomment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_wordcomment.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    op.create_table(
        "vocabulary_wordcomment_dislikes",
        sa.Column("wordcomment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_wordcomment.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # collectioncomment & wordcomment tables (simplified: inherit CommentModel fields)
    op.create_table(
        "vocabulary_collectioncomment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("author_liked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("text_modified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_collection.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_vocabulary_collectioncomment_created", "vocabulary_collectioncomment", ["created"])

    op.create_table(
        "vocabulary_wordcomment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("author_liked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("text_modified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_vocabulary_wordcomment_created", "vocabulary_wordcomment", ["created"])

    # answers relationship tables
    op.create_table(
        "vocabulary_collectioncomment_answers",
        sa.Column("collectioncomment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_collectioncomment.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("answer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_collectioncomment.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    op.create_table(
        "vocabulary_wordcomment_answers",
        sa.Column("wordcomment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_wordcomment.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("answer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_wordcomment.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # --- favorites / views / approvals / premiumrequest ---
    op.create_table(
        "vocabulary_favoriteword",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_user_favorite_word", "vocabulary_favoriteword", ["word_id", "user_id"])

    op.create_table(
        "vocabulary_favoritecollection",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_collection.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_user_favorite_collection", "vocabulary_favoritecollection", ["collection_id", "user_id"])

    op.create_table(
        "vocabulary_viewword",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("view_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_word_view", "vocabulary_viewword", ["word_id", "user_id"])
    op.create_index("ix_vocabulary_viewword_viewdatetime", "vocabulary_viewword", ["view_datetime"])

    op.create_table(
        "vocabulary_viewcollection",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("view_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_collection.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_collection_view", "vocabulary_viewcollection", ["collection_id", "user_id"])
    op.create_index("ix_vocabulary_viewcollection_viewdatetime", "vocabulary_viewcollection", ["view_datetime"])

    op.create_table(
        "vocabulary_wordapprove",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_word_approve", "vocabulary_wordapprove", ["word_id", "user_id"])

    op.create_table(
        "vocabulary_premiumrequest",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=True, unique=True),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_collection.id", ondelete="CASCADE"), nullable=True, unique=True),
        sa.Column("request_status", sa.String(length=1), nullable=False, server_default=sa.text("'P'")),
        sa.Column("review", sa.String(length=256), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    # CHECK on request_status
    op.execute(
        "ALTER TABLE vocabulary_premiumrequest ADD CONSTRAINT chk_vocabulary_premiumrequest_status "
        "CHECK (request_status IN ('A','R','P'));"
    )

def downgrade():
    # drop in reverse order -- be careful with dependencies
    op.drop_constraint("chk_vocabulary_premiumrequest_status", "vocabulary_premiumrequest", type_="check")
    op.drop_table("vocabulary_premiumrequest")
    op.drop_constraint("unique_word_approve", "vocabulary_wordapprove", type_="unique")
    op.drop_table("vocabulary_wordapprove")
    op.drop_index("ix_vocabulary_viewcollection_viewdatetime", table_name="vocabulary_viewcollection")
    op.drop_constraint("unique_collection_view", "vocabulary_viewcollection", type_="unique")
    op.drop_table("vocabulary_viewcollection")
    op.drop_index("ix_vocabulary_viewword_viewdatetime", table_name="vocabulary_viewword")
    op.drop_constraint("unique_word_view", "vocabulary_viewword", type_="unique")
    op.drop_table("vocabulary_viewword")
    op.drop_constraint("unique_user_favorite_collection", "vocabulary_favoritecollection", type_="unique")
    op.drop_table("vocabulary_favoritecollection")
    op.drop_constraint("unique_user_favorite_word", "vocabulary_favoriteword", type_="unique")
    op.drop_table("vocabulary_favoriteword")
    op.drop_table("vocabulary_wordcomment_answers")
    op.drop_table("vocabulary_collectioncomment_answers")
    op.drop_table("vocabulary_wordcomment")
    op.drop_table("vocabulary_collectioncomment")
    op.drop_table("vocabulary_wordcomment_dislikes")
    op.drop_table("vocabulary_wordcomment_likes")
    op.drop_table("vocabulary_collectioncomment_dislikes")
    op.drop_table("vocabulary_collectioncomment_likes")
    op.drop_table("vocabulary_wordsincollections")
    op.drop_table("vocabulary_wordquoteassociations")
    op.drop_table("vocabulary_wordimageassociations")
    op.drop_table("vocabulary_wordusageexamples")
    op.drop_table("vocabulary_worddefinitions")
    op.drop_table("vocabulary_wordtranslations")
    op.drop_table("vocabulary_wordsformgroups")
    op.execute("DROP INDEX IF EXISTS uq_vocabulary_collection_lower_title_author;")
    op.drop_table("vocabulary_collection")
    op.drop_index("ix_vocabulary_quoteassociation_created_modified", table_name="vocabulary_quoteassociation")
    op.drop_table("vocabulary_quoteassociation")
    op.drop_index("ix_vocabulary_imageassociation_created_modified", table_name="vocabulary_imageassociation")
    op.drop_table("vocabulary_imageassociation")
    op.execute("DROP INDEX IF EXISTS uq_vocabulary_usageexample_lower_text_author;")
    op.drop_index("ix_vocabulary_usageexample_created_modified", table_name="vocabulary_usageexample")
    op.drop_table("vocabulary_usageexample")
    op.execute("DROP INDEX IF EXISTS uq_vocabulary_definition_lower_text_author;")
    op.drop_index("ix_vocabulary_definition_created_modified", table_name="vocabulary_definition")
    op.drop_table("vocabulary_definition")
    op.execute("DROP INDEX IF EXISTS uq_vocabulary_wordtranslation_lower_text_author_language;")
    op.drop_index("ix_vocabulary_wordtranslation_created_modified", table_name="vocabulary_wordtranslation")
    op.drop_table("vocabulary_wordtranslation")
    op.execute("DROP INDEX IF EXISTS uq_vocabulary_formgroup_lower_name_author;")
    op.drop_index("ix_vocabulary_formgroup_created_modified", table_name="vocabulary_formgroup")
    op.drop_table("vocabulary_formgroup")
    op.drop_table("vocabulary_wordtype")
    op.execute("ALTER TABLE vocabulary_word DROP CONSTRAINT IF EXISTS chk_vocabulary_word_activity_status;")
    op.drop_constraint("uq_vocabulary_word_text_author_language", "vocabulary_word", type_="unique")
    op.drop_index("ix_vocabulary_word_created_modified", table_name="vocabulary_word")
    op.drop_table("vocabulary_word")