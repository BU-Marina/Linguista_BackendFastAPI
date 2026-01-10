"""Parsing utils."""

from __future__ import annotations


def parse_csv(value: str | None) -> list[str] | None:
    if not value:
        return None

    items = [x.strip() for x in value.split(",")]
    items = [x for x in items if x]

    return items or None


def parse_separated_values(value: str | None) -> list[str]:
    """
    Эмуляция SeparatedValuesSerializerField на чтение.
    Предположим: храним CSV (через запятую) или пусто.
    """
    if not value:
        return []

    # иногда могут прилетать пробелы/переносы
    raw = value.strip()
    if not raw:
        return []

    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]
