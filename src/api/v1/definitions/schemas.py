"""Definitions schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


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
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: list
