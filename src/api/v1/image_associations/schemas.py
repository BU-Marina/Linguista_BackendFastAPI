"""Image associations schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from core.utils.urls import get_full_media_url


class ImageIn(BaseModel):
    image_url: str
    width: Optional[int] = None
    height: Optional[int] = None
    num: Optional[int] = None


class ImageOut(BaseModel):
    id: UUID
    image_url: str
    width: Optional[int] = None
    height: Optional[int] = None
    num: Optional[int] = None
    other_words_count: int = 0
    last_6_words: List[str] = Field(default_factory=list)
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    model_config = {'from_attributes': True}

    @field_validator('image_url', mode='before')
    @classmethod
    def convert_image_url_to_full(cls, v):
        return get_full_media_url(v) or v


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: list


class ImageResolveOut(BaseModel):
    id: UUID
    slug: str
