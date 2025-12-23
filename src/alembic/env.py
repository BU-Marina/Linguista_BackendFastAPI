import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import create_engine
from dotenv import load_dotenv
from alembic import context

load_dotenv()

# добавь путь к проекту, если нужен
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# импортируй metadata из вашего core
# пример: в твоём проекте Base = declarative_base(cls=PreBase, metadata=metadata)
from core.base import Base  # <- либо: from core.db import Base; metadata = Base.metadata

# this is the Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config
fileConfig(config.config_file_name)

# параметр подключения: берем из env var, fallback на alembic.ini
database_url = os.getenv("MIGRATION_DATABASE_URL") or config.get_main_option("sqlalchemy.url")

# target metadata for 'autogenerate'
target_metadata = Base.metadata

def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table":
        # пропустить таблицы djangoAllauth / celery / auth / django_* и т.д.
        if name.startswith("django_") or name.startswith("auth_") or name.startswith("socialaccount_") or name.startswith("account_") or name.startswith("django_celery_beat_"):
            return False
    return True


def run_migrations_offline():
    url = database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # Alembic не работает прямо с async engine для DDL; используем sync engine and run_migrations
    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()