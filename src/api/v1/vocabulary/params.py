"""Vocabulary request params."""

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
class WordsListParams:
    page: int = 1
    limit: int = 32
    offset: int = 0
    ordering: Optional[str] = None
    search: Optional[str] = None
    languages: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    types: Optional[list[str]] = None
    favorite_only: bool = False


def build_words_list_params(**kwargs) -> WordsListParams:
    return build_list_params(
        WordsListParams,
        [
            "languages",
            "tags",
            "types",
        ],
        **kwargs,
    )


@dataclass
class CollectionsListParams:
    page: int = 1
    limit: int = 32
    offset: int = 0
    ordering: Optional[str] = None
    search: Optional[str] = None
    tags: Optional[list[str]] = None
    favorite_only: bool = False


def build_collections_list_params(**kwargs) -> CollectionsListParams:
    return build_list_params(
        CollectionsListParams,
        [
            "tags",
        ],
        **kwargs,
    )
