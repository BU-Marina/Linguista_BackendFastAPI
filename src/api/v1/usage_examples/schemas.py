"""Usage examples schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class ExampleIn(BaseModel):
    text: str
    translation: Optional[str] = None
    language: Optional[str] = None
    source: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None


class ExampleOut(BaseModel):
    id: UUID
    slug: str
    text: str
    translation: Optional[str] = None
    language: Optional[str] = None
    source: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    other_words_count: int = 0
    last_4_words: List[str] = Field(default_factory=list)
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    model_config = {'from_attributes': True}


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: list


class ExampleResolveOut(BaseModel):
    id: UUID
    slug: str
