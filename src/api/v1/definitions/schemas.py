"""Definitions schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class DefinitionIn(BaseModel):
    text: str
    translation: Optional[str] = None
    language: Optional[str] = None


class DefinitionOut(BaseModel):
    id: UUID
    slug: str
    text: str
    translation: Optional[str] = None
    language: Optional[str] = None
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


class DefinitionResolveOut(BaseModel):
    id: UUID
    slug: str
