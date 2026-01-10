"""Translations schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TranslationIn(BaseModel):
    text: str
    language: Optional[str] = None


class TranslationOut(BaseModel):
    id: UUID
    slug: str
    text: str
    language: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: list
