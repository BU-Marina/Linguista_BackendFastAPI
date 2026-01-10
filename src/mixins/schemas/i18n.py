"""Pydantic mixins."""

from __future__ import annotations

from typing import Any, ClassVar
from pydantic import BaseModel

from core.utils.i18n import i18n_get


class I18nFromOrmMixin(BaseModel):
    """
    Миксин для output-схем.

    В наследнике объявляем:
        __i18n_fields__ = ("name", "description")

    Тогда from_orm_i18n заполнит поля name/description значениями
    из name_ru/name_en/... в зависимости от lang.
    """

    __i18n_fields__: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def from_orm_i18n(cls, obj: Any, lang: str) -> "I18nFromOrmMixin":
        """..."""
        data: dict[str, Any] = {}

        # 1) Сначала переносим "обычные" поля (id, code, etc.) если они есть в ORM
        for field_name in cls.model_fields.keys():
            if field_name in cls.__i18n_fields__:
                continue
            if hasattr(obj, field_name):
                data[field_name] = getattr(obj, field_name)

        # 2) Заполняем переводимые поля из *_ru/*_en
        for base_field in cls.__i18n_fields__:
            data[base_field] = i18n_get(obj, base_field, lang)

        return cls(**data)

    @classmethod
    def from_orm_i18n_return_data(
        cls, obj: Any, lang: str, data: dict[str, Any]
    ) -> "I18nFromOrmMixin":
        """..."""

        # 2) Заполняем переводимые поля из *_ru/*_en
        for base_field in cls.__i18n_fields__:
            data[base_field] = i18n_get(obj, base_field, lang)

        return data
