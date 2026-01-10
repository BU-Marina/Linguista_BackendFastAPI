"""Languages request params builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from api.v1.utils.pagination import normalize_pagination


@dataclass
class LanguagesListParams:
    page: int = 1
    limit: int = 50
    offset: int = 0
    ordering: Optional[str] = None
    search: Optional[str] = None


def build_languages_list_params(
    *, page: int, limit: int, ordering: Optional[str], search: Optional[str]
) -> LanguagesListParams:
    page_norm, limit_norm, offset = normalize_pagination(page, limit)
    return LanguagesListParams(
        page=page_norm,
        limit=limit_norm,
        offset=offset,
        ordering=ordering,
        search=search,
    )
