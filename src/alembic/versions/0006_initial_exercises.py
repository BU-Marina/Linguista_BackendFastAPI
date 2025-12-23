"""initial exercises models (tables, fks, functional unique indexes, checks)

Revision ID: 0006_initial_exercises
Revises: 0005_initial_vocabulary
Create Date: 2025-11-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_initial_exercises"
down_revision = "0005_initial_vocabulary"
branch_labels = None
depends_on = None


def upgrade():
    # --- exercises_exercise ---
    op.create_table(
        "exercises_exercise",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.String(length=4096), nullable=False),
        sa.Column("constraint_description", sa.String(length=512), nullable=True),
        sa.Column("icon", sa.String(length=1024), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("slug", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_exercises_exercise_created", "exercises_exercise", ["created"])
    # case-insensitive unique on slug
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_exercises_exercise_lower_slug ON exercises_exercise ((lower(slug)));")

    # --- exercises_hint ---
    op.create_table(
        "exercises_hint",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=32), nullable=False, unique=True),
        sa.Column("description", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("variants_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("free_input_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("word_customization_content_needed", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_exercises_hint_created", "exercises_hint", ["created"])

    # --- association: exercises_exercise_hints_available ---
    op.create_table(
        "exercises_exercise_hints_available",
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercise.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("hint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_hint.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # --- exercises_exercisesessionhistory ---
    op.create_table(
        "exercises_exercisesessionhistory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercise.id", ondelete="CASCADE"), nullable=False),
        sa.Column("words_amount", sa.SmallInteger(), nullable=False),
        sa.Column("tasks_amount", sa.SmallInteger(), nullable=False),
        sa.Column("corrects_amount", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("incorrects_amount", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("semi_corrects_amount", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("complete_time", sa.Float(), nullable=True),
    )
    op.create_index("ix_exercises_exercisesessionhistory_created", "exercises_exercisesessionhistory", ["created"])

    # --- exercises_exercisesessiontaskshistory ---
    op.create_table(
        "exercises_exercisesessiontaskshistory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercisesessionhistory.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_translation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_wordtranslation.id", ondelete="CASCADE"), nullable=True),
        sa.Column("task", sa.String(length=2048), nullable=False),
        sa.Column("task_type", sa.String(length=1), nullable=False, server_default=sa.text("'T'")),
        sa.Column("task_language", sa.String(length=8), nullable=True),
        sa.Column("task_index", sa.SmallInteger(), nullable=False),
        sa.Column("answer", sa.String(length=1024), nullable=False),
        sa.Column("verdict", sa.String(length=2), nullable=False),
        sa.Column("answers_list", sa.Text(), nullable=True),
        sa.Column("verdicts_list", sa.Text(), nullable=True),
        sa.Column("answer_time", sa.Float(), nullable=True),
        sa.Column("answer_time_limit", sa.SmallInteger(), nullable=True),
        sa.Column("image_width", sa.SmallInteger(), nullable=True),
        sa.Column("image_height", sa.SmallInteger(), nullable=True),
    )
    op.create_index("ix_exercises_exercisesessiontaskshistory_created_taskindex", "exercises_exercisesessiontaskshistory", ["created", "task_index"])
    # CHECK task_type in ('T','I')
    op.execute("ALTER TABLE exercises_exercisesessiontaskshistory ADD CONSTRAINT chk_ex_session_task_type CHECK (task_type IN ('T','I'));")
    # CHECK verdict in ('C','I','SC')
    op.execute("ALTER TABLE exercises_exercisesessiontaskshistory ADD CONSTRAINT chk_ex_session_verdict CHECK (verdict IN ('C','I','SC'));")

    # Association tables for exercises_exercisesessiontaskshistory right answers and hints
    op.create_table(
        "exercises_exercisesessiontaskshistory_right_answers_words",
        sa.Column("taskhistory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercisesessiontaskshistory.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    op.create_table(
        "exercises_exercisesessiontaskshistory_right_answers_translations",
        sa.Column("taskhistory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercisesessiontaskshistory.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("translation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_wordtranslation.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    op.create_table(
        "exercises_exercisesessiontaskshistory_right_answers_definitions",
        sa.Column("taskhistory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercisesessiontaskshistory.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_definition.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    op.create_table(
        "exercises_exercisesessiontaskshistory_hints_available",
        sa.Column("taskhistory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercisesessiontaskshistory.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("hint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_hint.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    op.create_table(
        "exercises_exercisesessiontaskshistory_hints_used",
        sa.Column("taskhistory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercisesessiontaskshistory.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("hint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_hint.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # --- exercises_exerciseconfiguration ---
    op.create_table(
        "exercises_exerciseconfiguration",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_mode", sa.String(length=3), nullable=False, server_default=sa.text("'FI'")),
        sa.Column("answer_time_limit", sa.SmallInteger(), nullable=True),
        sa.Column("time_limit_mode", sa.String(length=1), nullable=False, server_default=sa.text("'A'")),
        sa.Column("repetitions_amount", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("translations_mode", sa.String(length=3), nullable=True, server_default=sa.text("'LTN'")),
        sa.Column("definitions_mode", sa.String(length=3), nullable=True, server_default=sa.text("'DBW'")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("hints_use_amount", sa.SmallInteger(), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercise.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_exercises_exerciseconfiguration_created", "exercises_exerciseconfiguration", ["created"])
    # CHECKs for enums
    op.execute("ALTER TABLE exercises_exerciseconfiguration ADD CONSTRAINT chk_ex_cfg_input_mode CHECK (input_mode IN ('FI','FIM','V','VM','A','AM'));")
    op.execute("ALTER TABLE exercises_exerciseconfiguration ADD CONSTRAINT chk_ex_cfg_time_limit_mode CHECK (time_limit_mode IN ('A','R'));")
    op.execute("ALTER TABLE exercises_exerciseconfiguration ADD CONSTRAINT chk_ex_cfg_translations_mode CHECK (translations_mode IN ('LTN','NTL','LTL','A'));")
    op.execute("ALTER TABLE exercises_exerciseconfiguration ADD CONSTRAINT chk_ex_cfg_definitions_mode CHECK (definitions_mode IN ('DBW','WBD','A'));")

    # association tables for ExerciseConfiguration
    op.create_table(
        "exercises_exerciseconfiguration_words_set",
        sa.Column("exerciseconfiguration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exerciseconfiguration.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("wordsset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_wordsset.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    op.create_table(
        "exercises_exerciseconfiguration_words",
        sa.Column("exerciseconfiguration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exerciseconfiguration.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    op.create_table(
        "exercises_exerciseconfiguration_hints_available",
        sa.Column("exerciseconfiguration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exerciseconfiguration.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("hint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_hint.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # --- exercises_favoriteexercise ---
    op.create_table(
        "exercises_favoriteexercise",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercise.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_favorite_exercise", "exercises_favoriteexercise", ["exercise_id", "user_id"])
    op.create_index("ix_exercises_favoriteexercise_created", "exercises_favoriteexercise", ["created"])

    # --- exercises_wordsset ---
    op.create_table(
        "exercises_wordsset",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercise.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("last_exercise_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_exercises_wordsset_lastexercise_created", "exercises_wordsset", ["last_exercise_date", "created"])
    # create functional unique index lower(name), exercise_id, author_id
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_exercises_wordsset_lower_name_exercise_author "
        "ON exercises_wordsset ((lower(name)), exercise_id, author_id);"
    )
    # case-insensitive slug unique
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_exercises_wordsset_lower_slug ON exercises_wordsset ((lower(slug)));")

    # association: exercises_wordsset_words
    op.create_table(
        "exercises_wordsset_words",
        sa.Column("wordsset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_wordsset.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # --- exercises_customexerciseconfiguration ---
    op.create_table(
        "exercises_customexerciseconfiguration",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("task", sa.String(length=64), nullable=False),
        sa.Column("content_text", sa.String(length=256), nullable=True),
        sa.Column("content_image", sa.String(length=1024), nullable=True),
        sa.Column("correct_answers", sa.Text(), nullable=True),
        sa.Column("answer_time_limit", sa.SmallInteger(), nullable=True),
        sa.Column("variants", sa.Text(), nullable=True),
        sa.Column("several_answers_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_exercises_customexerciseconfiguration_created", "exercises_customexerciseconfiguration", ["created"])

    # association: customexerciseconfiguration_gaps
    op.create_table(
        "exercises_customexerciseconfiguration_gaps",
        sa.Column("customexerciseconfiguration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_customexerciseconfiguration.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("customgap_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_customgap.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # --- exercises_customgap ---
    op.create_table(
        "exercises_customgap",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("pre_position", sa.Integer(), nullable=False),
        sa.Column("order_position", sa.Integer(), nullable=False),
        sa.Column("correct_answers", sa.Text(), nullable=True),
    )
    op.create_index("ix_exercises_customgap_created", "exercises_customgap", ["created"])

    # association: customgap_allowed_words
    op.create_table(
        "exercises_customgap_allowed_words",
        sa.Column("customgap_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_customgap.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # --- exercises_exercisesset ---
    op.create_table(
        "exercises_exercisesset",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(length=64), nullable=False),
        sa.Column("run_access_level", sa.String(length=8), nullable=False, server_default=sa.text("'PUB'")),
        sa.Column("add_access_level", sa.String(length=8), nullable=False, server_default=sa.text("'PUB'")),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("views_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("slug", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_exercises_exercisesset_created_modified", "exercises_exercisesset", ["created", "modified"])
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_exercises_exercisesset_lower_title_author ON exercises_exercisesset ((lower(title)), author_id);")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_exercises_exercisesset_lower_slug ON exercises_exercisesset ((lower(slug)));")

    # associations for exerciseset
    op.create_table(
        "exercises_exercisesset_words",
        sa.Column("exerciseset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercisesset.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("word_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocabulary_word.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    op.create_table(
        "exercises_exercisesset_exercises",
        sa.Column("exerciseset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercisesset.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("exerciseconfiguration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exerciseconfiguration.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    op.create_table(
        "exercises_exercisesset_custom_exercises",
        sa.Column("exerciseset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercisesset.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("customexerciseconfiguration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_customexerciseconfiguration.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # --- exercises_favoriteexerciseset ---
    op.create_table(
        "exercises_favoriteexerciseset",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("exercises_set_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercisesset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_unique_constraint("unique_favorite_exercises_set", "exercises_favoriteexerciseset", ["exercises_set_id", "user_id"])
    op.create_index("ix_exercises_favoriteexerciseset_created", "exercises_favoriteexerciseset", ["created"])

    # --- exercises_exerciseschedule ---
    op.create_table(
        "exercises_exerciseschedule",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("send_notification", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercise.id", ondelete="CASCADE"), nullable=True),
        sa.Column("exercise_configuration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exerciseconfiguration.id", ondelete="CASCADE"), nullable=True),
        sa.Column("exercises_set_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises_exercisesset.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_exercises_schedule_scheduled_created_modified", "exercises_exerciseschedule", ["scheduled_datetime", "created", "modified"])

    # --- Misc: create functional index for slug of ExercisesSet/WordsSet/Exercise already created above ---
    # (WordsSet and ExercisesSet created; Exercise slug index created.)

    # Additional: create unique lower slug for wordsset (already created above)
    # already done earlier for wordsset and exerciseset and exercise.

def downgrade():
    # Drop in reverse order
    op.drop_index("ix_exercises_schedule_scheduled_created_modified", table_name="exercises_exerciseschedule")
    op.drop_table("exercises_exerciseschedule")

    op.drop_index("ix_exercises_favoriteexerciseset_created", table_name="exercises_favoriteexerciseset")
    op.drop_constraint("unique_favorite_exercises_set", "exercises_favoriteexerciseset", type_="unique")
    op.drop_table("exercises_favoriteexerciseset")

    op.drop_table("exercises_exercisesset_custom_exercises")
    op.drop_table("exercises_exercisesset_exercises")
    op.drop_table("exercises_exercisesset_words")

    op.execute("DROP INDEX IF EXISTS uq_exercises_exercisesset_lower_slug;")
    op.execute("DROP INDEX IF EXISTS uq_exercises_exercisesset_lower_title_author;")
    op.drop_index("ix_exercises_exercisesset_created_modified", table_name="exercises_exercisesset")
    op.drop_table("exercises_exercisesset")

    op.drop_table("exercises_customgap_allowed_words")
    op.drop_index("ix_exercises_customgap_created", table_name="exercises_customgap")
    op.drop_table("exercises_customgap")

    op.drop_table("exercises_customexerciseconfiguration_gaps")
    op.drop_index("ix_exercises_customexerciseconfiguration_created", table_name="exercises_customexerciseconfiguration")
    op.drop_table("exercises_customexerciseconfiguration")

    op.drop_table("exercises_wordsset_words")
    op.execute("DROP INDEX IF EXISTS uq_exercises_wordsset_lower_slug;")
    op.execute("DROP INDEX IF EXISTS uq_exercises_wordsset_lower_name_exercise_author;")
    op.drop_index("ix_exercises_wordsset_lastexercise_created", table_name="exercises_wordsset")
    op.drop_table("exercises_wordsset")

    op.drop_index("ix_exercises_favoriteexercise_created", table_name="exercises_favoriteexercise")
    op.drop_constraint("unique_favorite_exercise", "exercises_favoriteexercise", type_="unique")
    op.drop_table("exercises_favoriteexercise")

    op.drop_table("exercises_exerciseconfiguration_hints_available")
    op.drop_table("exercises_exerciseconfiguration_words")
    op.drop_table("exercises_exerciseconfiguration_words_set")
    # drop CHECKs for exerciseconfiguration
    op.execute("ALTER TABLE exercises_exerciseconfiguration DROP CONSTRAINT IF EXISTS chk_ex_cfg_definitions_mode;")
    op.execute("ALTER TABLE exercises_exerciseconfiguration DROP CONSTRAINT IF EXISTS chk_ex_cfg_translations_mode;")
    op.execute("ALTER TABLE exercises_exerciseconfiguration DROP CONSTRAINT IF EXISTS chk_ex_cfg_time_limit_mode;")
    op.execute("ALTER TABLE exercises_exerciseconfiguration DROP CONSTRAINT IF EXISTS chk_ex_cfg_input_mode;")
    op.drop_index("ix_exercises_exerciseconfiguration_created", table_name="exercises_exerciseconfiguration")
    op.drop_table("exercises_exerciseconfiguration")

    # drop session task history associations
    op.drop_table("exercises_exercisesessiontaskshistory_hints_used")
    op.drop_table("exercises_exercisesessiontaskshistory_hints_available")
    op.drop_table("exercises_exercisesessiontaskshistory_right_answers_definitions")
    op.drop_table("exercises_exercisesessiontaskshistory_right_answers_translations")
    op.drop_table("exercises_exercisesessiontaskshistory_right_answers_words")
    # drop CHECKs for taskshistory
    op.execute("ALTER TABLE exercises_exercisesessiontaskshistory DROP CONSTRAINT IF EXISTS chk_ex_session_verdict;")
    op.execute("ALTER TABLE exercises_exercisesessiontaskshistory DROP CONSTRAINT IF EXISTS chk_ex_session_task_type;")
    op.drop_index("ix_exercises_exercisesessiontaskshistory_created_taskindex", table_name="exercises_exercisesessiontaskshistory")
    op.drop_table("exercises_exercisesessiontaskshistory")

    op.drop_index("ix_exercises_exercisesessionhistory_created", table_name="exercises_exercisesessionhistory")
    op.drop_table("exercises_exercisesessionhistory")

    op.drop_table("exercises_exercise_hints_available")
    op.drop_table("exercises_hint")
    op.execute("DROP INDEX IF EXISTS uq_exercises_exercise_lower_slug;")
    op.drop_index("ix_exercises_exercise_created", table_name="exercises_exercise")
    op.drop_table("exercises_exercise")