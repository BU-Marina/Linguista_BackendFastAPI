"""..."""

import uuid
import importlib
from functools import lru_cache
from datetime import datetime, timezone

from sqlalchemy import MetaData, Column, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, declared_attr
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from config.settings import settings


naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=naming_convention)


@lru_cache(maxsize=256)
def _resolve_app_label(module_path: str) -> str | None:
    """
    Попытаться найти APP_LABEL, начиная с верхних пакетов модуля.
    Ищем пакеты вида "<...>.apps.<appname>" или пытаемся импортировать
    "<package>.constants" и взять APP_LABEL из него.
    """
    if not module_path:
        return None
    parts = module_path.split(".")

    # 1) если есть 'apps' в пути, возьмём следующий сегмент как app_label
    if "apps" in parts:
        idx = parts.index("apps")
        if idx + 1 < len(parts):
            return parts[idx + 1]

    # 2) пробуем подняться по иерархии и импортировать module.constants
    for i in range(len(parts) - 1, 0, -1):
        candidate = ".".join(parts[: i + 1])

        try:
            const_mod = importlib.import_module(candidate + ".constants")
        except Exception:
            continue

        app_label = getattr(const_mod, "APP_LABEL", None)
        if app_label:
            return app_label

    # 3) fallback — взять второй с конца пакет (обычно имя app)
    if len(parts) >= 2:
        return parts[-2]

    return None


class PreBase:
    """
    Базовый класс для declarative_base:
    - вычисляет __tablename__ из APP_LABEL (если объявлен в app.constants) или по модулю;
    - добавляет default UUID primary key `id`;
    - добавляет created/modified поля.
    """

    @declared_attr
    def __tablename__(cls) -> str:
        module = getattr(cls, "__module__", "") or ""
        app_label = _resolve_app_label(module)
        if app_label:
            return f"{app_label}_{cls.__name__.lower()}"
        return cls.__name__.lower()

    # UUID PK по умолчанию — можно переопределить в конкретной модели
    id = Column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )

    # таймстампы по умолчанию
    created = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=datetime.now(timezone.utc),
        index=True,
    )
    modified = Column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )


Base = declarative_base(cls=PreBase, metadata=metadata)

engine = create_async_engine(
    settings.DATABASE_URL,
    future=True,
    echo=False,
)
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Dependency
async def get_async_session():
    async with AsyncSessionLocal() as async_session:
        yield async_session
