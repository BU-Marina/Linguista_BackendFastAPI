"""Searching utils."""

from __future__ import annotations


from sqlalchemy import String, cast, or_
from sqlalchemy.orm.attributes import QueryableAttribute


def _is_relationship(attr: QueryableAttribute) -> bool:
    return hasattr(attr, "property") and hasattr(attr.property, "direction")


def _is_column(attr: QueryableAttribute) -> bool:
    return hasattr(attr, "property") and hasattr(attr.property, "columns")


def _build_leaf_predicate(column_attr: QueryableAttribute, pattern: str):
    try:
        if hasattr(column_attr.property, "columns"):
            col_type = column_attr.property.columns[0].type
            if not isinstance(col_type, String):
                return cast(column_attr, String).ilike(pattern)
        return column_attr.ilike(pattern)
    except Exception:
        return cast(column_attr, String).ilike(pattern)


def _resolve_path_to_predicate(
    root_model, path: str, pattern: str, *, splitter: str = "."
):
    parts = [p for p in path.split(splitter) if p]
    if not parts:
        return None

    current_model = root_model
    attrs: list[QueryableAttribute] = []

    for part in parts:
        if not hasattr(current_model, part):
            return None
        attr = getattr(current_model, part)
        attrs.append(attr)
        if _is_relationship(attr):
            current_model = attr.property.mapper.class_

    leaf = attrs[-1]
    if not _is_column(leaf):
        return None

    predicate = _build_leaf_predicate(leaf, pattern)

    for rel_attr in reversed(attrs[:-1]):
        if not _is_relationship(rel_attr):
            return None
        predicate = (
            rel_attr.any(predicate)
            if rel_attr.property.uselist
            else rel_attr.has(predicate)
        )

    return predicate


def apply_search(
    stmt, root_model, term: str | None, search_fields: list[str], *, splitter: str = "."
):
    if not term:
        return stmt
    term = term.strip()
    if not term:
        return stmt

    pattern = f"%{term}%"
    predicates = []
    for path in search_fields:
        pred = _resolve_path_to_predicate(root_model, path, pattern, splitter=splitter)
        if pred is not None:
            predicates.append(pred)

    return stmt.where(or_(*predicates)) if predicates else stmt
