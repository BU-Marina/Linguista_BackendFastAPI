"""Users api request params."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

from api.v1.utils.pagination import normalize_pagination
from api.v1.utils.parsing import parse_csv


def build_list_params(paramscls, filters_fields_list: list[str], **kwargs) -> Any:
    page, limit, offset = normalize_pagination(kwargs["page"], kwargs["limit"])
    return paramscls(
        page=page,
        limit=limit,
        offset=offset,
        ordering=kwargs.get("ordering"),
        search=kwargs.get("search"),
        **{field: parse_csv(kwargs.get(field)) for field in filters_fields_list},
    )


@dataclass
class UsersListParams:
    page: int = 1
    limit: int = 32
    offset: int = 0
    ordering: Optional[str] = None
    search: Optional[str] = None

    learning_languages: Optional[list[str]] = None
    native_languages: Optional[list[str]] = None
    taught_languages: Optional[list[str]] = None

    levels: Optional[list[str]] = None
    levels_exclude: Optional[list[str]] = None
    is_confirmed: Optional[bool] = None

    interests: Optional[list[str]] = None
    interests_exclude: Optional[list[str]] = None
    cities: Optional[list[str]] = None


def build_users_list_params(**kwargs) -> UsersListParams:
    return build_list_params(
        UsersListParams,
        [
            "learning_languages",
            "native_languages",
            "taught_languages",
            "levels",
            "levels_exclude",
            "is_confirmed",
            "interests",
            "interests_exclude",
            "cities",
        ],
        **kwargs,
    )
