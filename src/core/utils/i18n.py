"""..."""

from __future__ import annotations

from typing import Any, Optional, List

from config.settings import settings

SUPPORTED_LANGS: List[str] = settings.SUPPORTED_LANGS
DEFAULT_LANG: str = settings.DEFAULT_LANG


def parse_accept_language(value: Optional[str]) -> str:
    """
    Упрощённый парсер: берём первый язык из Accept-Language.
    'ru-RU,ru;q=0.9,en;q=0.8' -> 'ru'
    """
    if not value:
        return DEFAULT_LANG

    first = value.split(",")[0].strip()
    lang = first.split("-")[0].lower()

    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def i18n_get(obj: Any, field: str, lang: str, default_lang: str = DEFAULT_LANG) -> Any:
    """
    Берёт значение из obj.<field>_<lang> с fallback:
    1) field_lang
    2) field_default_lang
    3) любой из SUPPORTED_LANGS
    """
    candidates: list[str] = [f"{field}_{lang}"]
    if default_lang != lang:
        candidates.append(f"{field}_{default_lang}")
    candidates.extend(
        f"{field}_{lang_code}"
        for lang_code in SUPPORTED_LANGS
        if lang_code not in (lang, default_lang)
    )

    for attr in candidates:
        v = getattr(obj, attr, None)
        if v not in (None, ""):
            return v

    return None
