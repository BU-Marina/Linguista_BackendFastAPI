"""Collections schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field

from api.v1.vocabulary.schemas import WordListOut


class CollectionShortOut(BaseModel):
    id: UUID
    slug: str
    title: str
    description: Optional[str] = None
    words_count: int = 0
    favorite: bool = False
    created: Optional[datetime] = None
    modified: Optional[datetime] = None


class CollectionIn(BaseModel):
    title: str
    description: Optional[str] = None
    allow_comments: Optional[bool] = True
    allow_suggestions: Optional[bool] = True
    allow_suggestions_notifications: Optional[bool] = True


class CollectionReadOut(CollectionShortOut):
    words: List[WordListOut] = Field(default_factory=list)


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: list
