"""change slug max length for many tables

Revision ID: <NEW_REVISION_ID>
Revises: <CURRENT_DOWN_REVISION>
Create Date: 2025-11-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_update_slug_max_length"
down_revision = "0016_update_created_modified"

# Новая длина для slug:
NEW_LEN = 1024
OLD_LEN = 255  # желаемая rollback длина

# Если вы хотите, чтобы миграция ПРЕРЫВАЛАСЬ при наличии длинных slug,
# установите TRUNCATE_LONG_VALUES = False — тогда миграция бросит исключение.
# Если True — длинные значения будут автоматически обрезаны (left(..., NEW_LEN)).
TRUNCATE_LONG_VALUES = True

# Список таблиц и имён столбца slug (если у какой-то таблицы slug называется иначе — поправьте)
TABLES = [
    "exercises_exercise",
    "exercises_wordsset",
    "exercises_exerciseset",
    "languages_usernativelanguage",
    "languages_userlearninglanguage",
    "users_user",
    "users_grammar",
    "vocabulary_word",
    "vocabulary_wordtype",
    "vocabulary_formgroup",
    "vocabulary_wordtranslation",
    "vocabulary_definition",
    "vocabulary_usageexample",
    "vocabulary_collection"
]

def _ensure_truncate_or_abort(table_name: str):
    """
    Если TRUNCATE_LONG_VALUES=True - обрежет длинные slug (UPDATE ... left(...))
    Иначе - если найдены длинные значения - бросит RuntimeError.
    """
    if TRUNCATE_LONG_VALUES:
        op.execute(
            sa.text(
                f"UPDATE {table_name} SET slug = left(slug, {NEW_LEN}) "
                f"WHERE slug IS NOT NULL AND char_length(slug) > {NEW_LEN}"
            ),
        )
    else:
        # проверить наличие длинных значений и при их наличии прервать миграцию
        res = op.get_bind().execute(
            sa.text(
                "SELECT count(*) FROM " + table_name +
                f" WHERE slug IS NOT NULL AND char_length(slug) > {NEW_LEN}"
            ),
        )
        cnt = res.scalar()
        if cnt and cnt > 0:
            raise RuntimeError(
                f"Table {table_name} has {cnt} slug(s) longer than {NEW_LEN}. "
                "Set TRUNCATE_LONG_VALUES=True to auto-truncate or fix values manually."
            )

def upgrade():
    bind = op.get_bind()
    # проверка и (опционально) обрезка длинных значений
    for tbl in TABLES:
        # убедимся, что таблица существует — чтобы не падать, если какая-то таблица отсутствует
        exists = bind.execute(
            sa.text(
                f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{tbl}')"
            ),
        ).scalar()
        if not exists:
            # пропустить несуществующие таблицы
            # если вы хотите падать — замените на raise
            continue

        _ensure_truncate_or_abort(tbl)

    # теперь безопасно изменить тип столбца slug для всех таблиц
    for tbl in TABLES:
        # пропускаем несуществующие таблицы
        exists = bind.execute(
            sa.text(
                f"SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '{tbl}' AND column_name = 'slug')"
            ),
        ).scalar()
        if not exists:
            continue

        # ALTER COLUMN TYPE с явной трансформацией не требуется, т.к. мы уже обрезали значения;
        # используем op.alter_column, указывая новый тип
        op.alter_column(
            tbl,
            "slug",
            existing_type=sa.String(length=None),
            type_=sa.String(length=NEW_LEN),
            existing_nullable=True,
        )


def downgrade():
    # В downgrade нужно вернуть старую длину.
    bind = op.get_bind()
    for tbl in TABLES:
        # только если столбец slug существует
        exists = bind.execute(
            sa.text(
                f"SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '{tbl}' AND column_name = 'slug')"
            ),
        ).scalar()
        if not exists:
            continue

        # Перед уменьшением длины лучше обрезать значения до OLD_LEN чтобы ALTER не упал
        # Здесь используем автоматическое обрезание (без предупреждения)
        bind.execute(
            sa.text(
                "UPDATE " + tbl + f" SET slug = left(slug, {OLD_LEN}) WHERE slug IS NOT NULL AND char_length(slug) > {OLD_LEN}"
            ),
        )

        op.alter_column(
            tbl,
            "slug",
            existing_type=sa.String(length=None),
            type_=sa.String(length=OLD_LEN),
            existing_nullable=True,
        )