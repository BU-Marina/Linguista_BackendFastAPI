"""Split single-language name/description fields into _ru and _en variants.

Revision ID: 0024_localized_name_fields
Revises: 0023_users_image_url
Create Date: 2025-12-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_localized_name_fields"
down_revision = "0023_users_image_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- languages_language ---
    # op.add_column(
    #     "languages_language",
    #     sa.Column("name_ru", sa.String(length=256), nullable=False, server_default=""),
    # )
    # op.add_column(
    #     "languages_language",
    #     sa.Column("name_en", sa.String(length=256), nullable=False, server_default=""),
    # )
    # op.add_column(
    #     "languages_language",
    #     sa.Column("country_ru", sa.String(length=256), nullable=True, server_default=""),
    # )
    # op.add_column(
    #     "languages_language",
    #     sa.Column("country_en", sa.String(length=256), nullable=True, server_default=""),
    # )

    # copy data from old single-language fields
    # op.execute(
    #     """
    #     UPDATE languages_language
    #     SET
    #         name_ru = COALESCE(name, ''),
    #         name_en = COALESCE(name, ''),
    #         country_ru = COALESCE(country, ''),
    #         country_en = COALESCE(country, '')
    #     """
    # )

    # drop old index and recreate with name_en instead of name
    # op.drop_index(
    #     "ix_languages_language_sorting_name_isocode",
    #     table_name="languages_language",
    # )
    op.create_index(
        "ix_languages_language_sorting_name_isocode",
        "languages_language",
        ["sorting", "name_en", "isocode"],
    )

    # drop old columns
    op.drop_column("languages_language", "name")
    op.drop_column("languages_language", "country")

    # --- exercises_exercise ---
    # op.add_column(
    #     "exercises_exercise",
    #     sa.Column("name_ru", sa.String(length=256), nullable=False, server_default=""),
    # )
    # op.add_column(
    #     "exercises_exercise",
    #     sa.Column("name_en", sa.String(length=256), nullable=False, server_default=""),
    # )
    # op.add_column(
    #     "exercises_exercise",
    #     sa.Column("description_ru", sa.String(length=4096), nullable=False, server_default=""),
    # )
    # op.add_column(
    #     "exercises_exercise",
    #     sa.Column("description_en", sa.String(length=4096), nullable=False, server_default=""),
    # )
    # op.add_column(
    #     "exercises_exercise",
    #     sa.Column("constraint_description_ru", sa.String(length=512), nullable=True),
    # )
    # op.add_column(
    #     "exercises_exercise",
    #     sa.Column("constraint_description_en", sa.String(length=512), nullable=True),
    # )

    # op.execute(
    #     """
    #     UPDATE exercises_exercise
    #     SET
    #         name_ru = COALESCE(name, ''),
    #         name_en = COALESCE(name, ''),
    #         description_ru = COALESCE(description, ''),
    #         description_en = COALESCE(description, ''),
    #         constraint_description_ru = constraint_description,
    #         constraint_description_en = constraint_description
    #     """
    # )

    op.drop_column("exercises_exercise", "name")
    op.drop_column("exercises_exercise", "description")
    op.drop_column("exercises_exercise", "constraint_description")

    # --- exercises_hint ---
    # op.add_column(
    #     "exercises_hint",
    #     sa.Column("name_ru", sa.String(length=32), nullable=False, server_default=""),
    # )
    # op.add_column(
    #     "exercises_hint",
    #     sa.Column("name_en", sa.String(length=32), nullable=False, server_default=""),
    # )
    # op.add_column(
    #     "exercises_hint",
    #     sa.Column("description_ru", sa.String(length=128), nullable=False, server_default=""),
    # )
    # op.add_column(
    #     "exercises_hint",
    #     sa.Column("description_en", sa.String(length=128), nullable=False, server_default=""),
    # )

    # op.execute(
    #     """
    #     UPDATE exercises_hint
    #     SET
    #         name_ru = COALESCE(name, ''),
    #         name_en = COALESCE(name, ''),
    #         description_ru = COALESCE(description, ''),
    #         description_en = COALESCE(description, '')
    #     """
    # )

    # optional: enforce uniqueness on both localized names
    op.create_unique_constraint(
        "uq_exercises_hint_name_ru",
        "exercises_hint",
        ["name_ru"],
    )
    op.create_unique_constraint(
        "uq_exercises_hint_name_en",
        "exercises_hint",
        ["name_en"],
    )

    op.drop_column("exercises_hint", "name")
    op.drop_column("exercises_hint", "description")

    # --- vocabulary_wordtype ---
    # op.add_column(
    #     "vocabulary_wordtype",
    #     sa.Column("name_ru", sa.String(length=64), nullable=False, server_default=""),
    # )
    # op.add_column(
    #     "vocabulary_wordtype",
    #     sa.Column("name_en", sa.String(length=64), nullable=False, server_default=""),
    # )

    # op.execute(
    #     """
    #     UPDATE vocabulary_wordtype
    #     SET
    #         name_ru = COALESCE(name, ''),
    #         name_en = COALESCE(name, '')
    #     """
    # )

    op.create_unique_constraint(
        "uq_vocabulary_wordtype_name_ru",
        "vocabulary_wordtype",
        ["name_ru"],
    )
    op.create_unique_constraint(
        "uq_vocabulary_wordtype_name_en",
        "vocabulary_wordtype",
        ["name_en"],
    )

    op.drop_column("vocabulary_wordtype", "name")


def downgrade() -> None:
    # --- vocabulary_wordtype ---
    op.add_column(
        "vocabulary_wordtype",
        sa.Column("name", sa.String(length=64), nullable=False, server_default=""),
    )
    op.execute(
        """
        UPDATE vocabulary_wordtype
        SET name = COALESCE(name_ru, name_en, '')
        """
    )
    op.drop_constraint(
        "uq_vocabulary_wordtype_name_ru", "vocabulary_wordtype", type_="unique"
    )
    op.drop_constraint(
        "uq_vocabulary_wordtype_name_en", "vocabulary_wordtype", type_="unique"
    )
    # op.drop_column("vocabulary_wordtype", "name_ru")
    # op.drop_column("vocabulary_wordtype", "name_en")

    # --- exercises_hint ---
    op.add_column(
        "exercises_hint",
        sa.Column("name", sa.String(length=32), nullable=False, server_default=""),
    )
    op.add_column(
        "exercises_hint",
        sa.Column(
            "description", sa.String(length=128), nullable=False, server_default=""
        ),
    )
    op.execute(
        """
        UPDATE exercises_hint
        SET
            name = COALESCE(name_ru, name_en, ''),
            description = COALESCE(description_ru, description_en, '')
        """
    )
    op.drop_constraint("uq_exercises_hint_name_ru", "exercises_hint", type_="unique")
    op.drop_constraint("uq_exercises_hint_name_en", "exercises_hint", type_="unique")
    # op.drop_column("exercises_hint", "name_ru")
    # op.drop_column("exercises_hint", "name_en")
    # op.drop_column("exercises_hint", "description_ru")
    # op.drop_column("exercises_hint", "description_en")

    # --- exercises_exercise ---
    op.add_column(
        "exercises_exercise",
        sa.Column("name", sa.String(length=256), nullable=False, server_default=""),
    )
    op.add_column(
        "exercises_exercise",
        sa.Column(
            "description", sa.String(length=4096), nullable=False, server_default=""
        ),
    )
    op.add_column(
        "exercises_exercise",
        sa.Column("constraint_description", sa.String(length=512), nullable=True),
    )
    op.execute(
        """
        UPDATE exercises_exercise
        SET
            name = COALESCE(name_ru, name_en, ''),
            description = COALESCE(description_ru, description_en, ''),
            constraint_description = COALESCE(constraint_description_ru, constraint_description_en)
        """
    )
    # op.drop_column("exercises_exercise", "name_ru")
    # op.drop_column("exercises_exercise", "name_en")
    # op.drop_column("exercises_exercise", "description_ru")
    # op.drop_column("exercises_exercise", "description_en")
    # op.drop_column("exercises_exercise", "constraint_description_ru")
    # op.drop_column("exercises_exercise", "constraint_description_en")

    # --- languages_language ---
    op.add_column(
        "languages_language",
        sa.Column("name", sa.String(length=256), nullable=False, server_default=""),
    )
    op.add_column(
        "languages_language",
        sa.Column("country", sa.String(length=256), nullable=True, server_default=""),
    )

    op.execute(
        """
        UPDATE languages_language
        SET
            name = COALESCE(name_ru, name_en, ''),
            country = COALESCE(country_ru, country_en, '')
        """
    )

    op.drop_index(
        "ix_languages_language_sorting_name_isocode",
        table_name="languages_language",
    )
    # op.create_index(
    #     "ix_languages_language_sorting_name_isocode",
    #     "languages_language",
    #     ["sorting", "name", "isocode"],
    # )

    # op.drop_column("languages_language", "name_ru")
    # op.drop_column("languages_language", "name_en")
    # op.drop_column("languages_language", "country_ru")
    # op.drop_column("languages_language", "country_en")
