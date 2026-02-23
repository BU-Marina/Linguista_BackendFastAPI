"""Translations schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class TranslationIn(BaseModel):
    id: Optional[UUID] = None  # If provided, update instead of create
    text: str
    language: Optional[str] = None
    words: Optional[List[UUID]] = None  # Word IDs to associate with this translation


class TranslationWordOut(BaseModel):
    """Word object in last_6_words for TranslationDto."""

    text: str
    language__isocode: str


class TranslationOut(BaseModel):
    id: UUID
    slug: str
    text: str
    language: str = ''  # Frontend expects non-optional string
    words_count: int = 0
    other_words_count: int = 0
    # Last related words as objects with text and language__isocode (for translation lists/cards)
    last_6_words: List[TranslationWordOut] = Field(default_factory=list)
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    model_config = {'from_attributes': True}


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    next: str | None = None
    previous: str | None = None
    results: list


class TranslationResolveOut(BaseModel):
    id: UUID
    slug: str
