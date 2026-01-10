"""Row -> Pydantic mappers for languages API."""

from __future__ import annotations

from typing import Any

from .schemas import (
    CollectionShortOut,
    LanguageBase,
    LanguageCoverOut,
    LearningLanguageOut,
)


def map_language_row(r: dict[str, Any]) -> LanguageBase:
    return LanguageBase(
        id=str(r["id"]),
        isocode=r["isocode"],
        name_local=r.get("name_local"),
        name_en=r.get("name_en"),
        name_ru=r.get("name_ru"),
        flag_icon=r.get("flag_icon"),
        sorting=r.get("sorting"),
        learning_available=bool(r.get("learning_available") or False),
        interface_available=bool(r.get("interface_available") or False),
        words_count=r.get("words_count"),
        is_native=bool(r.get("is_native") or False)
        if r.get("is_native") is not None
        else None,
        is_learning=bool(r.get("is_learning") or False)
        if r.get("is_learning") is not None
        else None,
    )


def map_learning_language_row(r: dict[str, Any]) -> LearningLanguageOut:
    language_payload = {
        "id": str(r.get("language_id") or r["id"]),
        "isocode": r["isocode"],
        "name_local": r.get("name_local"),
        "name_en": r.get("name_en"),
        "name_ru": r.get("name_ru"),
        "flag_icon": r.get("flag_icon"),
        "learning_available": r.get("learning_available"),
        "interface_available": r.get("interface_available"),
        "sorting": r.get("sorting"),
        "words_count": r.get("words_count"),
    }
    return LearningLanguageOut(
        id=str(r["id"]),
        slug=r.get("slug", ""),
        language=LanguageBase(**language_payload),
        level=r.get("level"),
        is_confirmed=bool(r.get("is_confirmed") or False),
        is_taught=bool(r.get("is_taught") or False),
        cover_url=r.get("cover_url"),
        cover_id=str(r.get("cover_id")) if r.get("cover_id") else None,
        cover_height=r.get("cover_height"),
        cover_width=r.get("cover_width"),
        words_count=int(r.get("words_count") or 0),
        inactive_words_count=int(r.get("inactive_words_count") or 0),
        active_words_count=int(r.get("active_words_count") or 0),
        mastered_words_count=int(r.get("mastered_words_count") or 0),
    )


def map_cover_row(r: dict[str, Any]) -> LanguageCoverOut:
    return LanguageCoverOut(
        id=str(r["id"]),
        image_url=r["image_url"],
        default=bool(r.get("default") or False),
        is_current_cover=bool(r.get("is_current_cover") or False),
    )


def map_collection_row(r: dict[str, Any]) -> CollectionShortOut:
    return CollectionShortOut(
        id=str(r["id"]),
        slug=r["slug"],
        title=r.get("title") or "",
        words_count=int(r.get("words_count") or 0),
    )
