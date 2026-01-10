"""Common dependencies."""

from typing import Optional
from fastapi import Header

from core.utils.i18n import parse_accept_language


def get_ui_lang(accept_language: Optional[str] = Header(default=None)) -> str:
    return parse_accept_language(accept_language)
