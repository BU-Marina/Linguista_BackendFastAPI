"""Slug-generator. Генерация слага."""

from typing import Optional
import re
from unidecode import unidecode
from slugify import slugify as py_slugify  # optional, used for better behaviour
import unicodedata

NON_ALNUM_RE = re.compile(r'[^a-z0-9]+')

def slugify_value(value: Optional[str], max_len: int = 64, sep: str = '-') -> str:
    """
    Нормализует строку в slug:
    - unidecode (удаляет диакритику)
    - lower, заменить все не-латинско-цифровые символы на sep
    - убрать повторяющиеся sep, обрезать по краям
    - обрезать до max_len, гарантируя отсутствие завершающего sep
    """
    if not value:
        return ''
    # Нормализация и транслитерация
    try:
        s = unidecode(value)
    except Exception:
        s = value
    s = s.lower()
    # Используем python-slugify если хочется более гибкой логики:
    try:
        # py_slugify использует unidecode и regex внутри
        s = py_slugify(s, separator=sep, lowercase=True)
    except Exception:
        # fallback to simpler approach
        s = NON_ALNUM_RE.sub(sep, s)
        s = re.sub(rf'{sep}{{2,}}', sep, s).strip(sep)

    # Обрезка до max_len
    if len(s) > max_len:
        s = s[:max_len].rstrip(sep)
    return s