"""..."""

from typing import List, Optional
from sqlalchemy import Column, String, select, func, Boolean
from sqlalchemy import event
from sqlalchemy.orm import Mapper
import sqlalchemy as sa

from utils.slugify import slugify_value

from .constants import DEFAULT_MAX_SLUG_LENGTH, AccessLevelsEnum


class SlugMixin:
    """
    Mixin: добавляет колонку slug в модели и автоматически её заполняет.
    Параметры модели:
      __slug_source__ = ["field1", "field2"]  # обязательно указываем
      __slug_max_length__ = 64
      __slug_always_update__ = False  # если True — обновлять slug при изменении source
      __slug_separator__ = '-'  # дефолтный разделитель
    """

    slug = Column(
        String(DEFAULT_MAX_SLUG_LENGTH), nullable=False, unique=True, index=True
    )

    __slug_source__: Optional[List[str]] = None
    __slug_max_length__: int = DEFAULT_MAX_SLUG_LENGTH
    __slug_always_update__: bool = True
    __slug_separator__: str = '-'


def _get_source_value(instance, source_fields: List[str]) -> str:
    """..."""
    parts = []

    for f in source_fields:
        v = getattr(instance, f, None)
        if v is None:
            continue

        # prefer primitive fields
        if isinstance(v, (str, int, float)):
            parts.append(str(v))
        else:
            # если relationship — можно попытаться взять str(v) или пропустить
            try:
                parts.append(str(v))
            except Exception:
                continue

    return ' '.join(p for p in parts if p)


def _fetch_existing_slugs(connection, table, pattern: str, this_id=None):
    """Вернуть множество существующих slug (case-insensitive), начинающихся с pattern."""
    # use bindparam for safety
    stmt = select(table.c.slug).where(
        func.lower(table.c.slug).like(func.lower(sa.bindparam('pattern')))
    )
    params = {'pattern': pattern + '%'}

    if this_id is not None and 'id' in table.c:
        stmt = stmt.where(table.c.id != sa.bindparam('this_id'))
        params['this_id'] = this_id

    res = connection.execute(stmt, params)
    rows = res.fetchall()

    return {r[0] for r in rows if r[0] is not None}


def _make_unique_slug(
    connection, table, base: str, max_len: int, this_id=None, sep='-'
) -> str:
    """..."""
    if not base:
        base = f'{table.name}-'  # fallback

    base = base[:max_len].rstrip(sep)
    existing = _fetch_existing_slugs(connection, table, base, this_id=this_id)

    if base and base not in existing:
        return base

    i = 1
    while True:
        suffix = f'{sep}{i}'
        space = max_len - len(suffix)

        if space <= 0:
            candidate = (base[: max_len - len(suffix)] + suffix)[:max_len]
        else:
            candidate = base[:space].rstrip(sep) + suffix

        if candidate not in existing:
            return candidate

        i += 1


@event.listens_for(Mapper, 'mapper_configured')
def _mapper_configured(mapper, class_):
    """..."""
    # Если нет __slug_source__, пропускаем
    if not getattr(class_, '__slug_source__', None):
        return

    table = getattr(class_, '__table__', None)
    if table is None:
        return

    max_len = getattr(class_, '__slug_max_length__', 64)
    sep = getattr(class_, '__slug_separator__', '-')
    always_update = getattr(class_, '__slug_always_update__', False)

    @event.listens_for(class_, 'before_insert')
    def _before_insert(mapper, connection, target):
        """..."""
        if getattr(target, 'slug', None):
            return

        base_raw = _get_source_value(target, class_.__slug_source__)
        base = slugify_value(base_raw, max_len=max_len, sep=sep)

        if not base:
            base = f"{class_.__name__.lower()}-{getattr(target, 'id', '') or ''}"

        unique = _make_unique_slug(
            connection,
            table,
            base,
            max_len,
            this_id=getattr(target, 'id', None),
            sep=sep,
        )
        target.slug = unique

    @event.listens_for(class_, 'before_update')
    def _before_update(mapper, connection, target):
        """..."""
        # если уже есть slug и мы не хотим перезаписывать — пропускаем
        current_slug = getattr(target, 'slug', None)
        if current_slug and not always_update:
            return

        base_raw = _get_source_value(target, class_.__slug_source__)
        base = slugify_value(base_raw, max_len=max_len, sep=sep)

        if not base:
            base = f"{class_.__name__.lower()}-{getattr(target, 'id', '') or ''}"

        unique = _make_unique_slug(
            connection,
            table,
            base,
            max_len,
            this_id=getattr(target, 'id', None),
            sep=sep,
        )
        target.slug = unique


class PublicAccessMixin:
    """
    SQLAlchemy-аналог Django PublicAccessModel.

    Важно:
    - relationship share_with определяется на конкретной модели через declared_attr
      и использует таблицу <model>_share_with, которую задаём рядом с моделью.
    """

    read_access_level = Column(
        String(AccessLevelsEnum.max_length),
        nullable=False,
        server_default=AccessLevelsEnum.default_level,
        insert_default=AccessLevelsEnum.default_level,
    )

    add_access_level = Column(
        String(AccessLevelsEnum.max_length),
        nullable=False,
        server_default=AccessLevelsEnum.default_level,
        insert_default=AccessLevelsEnum.default_level,
    )

    allow_access_change = Column(
        Boolean,
        nullable=False,
        server_default='true',
        insert_default=True,
    )

    # share_with relationship задаём в конкретных моделях (Word/Collection),
    # потому что secondary таблицы у них разные.
