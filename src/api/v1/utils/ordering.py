"""Ordering utils."""

from typing import Any


def apply_ordering(
    stmt, ordering: str | None, ordering_map: dict[str, Any], default: str
):
    ordering = ordering or default
    desc = ordering.startswith("-")
    key = ordering[1:] if desc else ordering

    expr = ordering_map.get(key)
    if expr is None:
        expr = ordering_map[default.lstrip("-")]
        desc = default.startswith("-")

    return stmt.order_by(expr.desc() if desc else expr.asc())
