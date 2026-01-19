"""Translations schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class TranslationIn(BaseModel):
    text: str
    language: Optional[str] = None


class TranslationWordOut(BaseModel):
    text: str
    language__isocode: Optional[str] = None


class TranslationOut(BaseModel):
    id: UUID
    slug: str
    text: str
    language: Optional[str] = None
    other_words_count: int = 0
    last_6_words: List[TranslationWordOut] = Field(default_factory=list)
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    model_config = {'from_attributes': True}


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: list


class TranslationResolveOut(BaseModel):
    id: UUID
    slug: str
