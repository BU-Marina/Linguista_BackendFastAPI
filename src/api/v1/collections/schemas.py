"""Collections schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from core.utils.urls import get_full_media_url


class CollectionWordOut(BaseModel):
    """Word summary for collection preview."""

    slug: str
    text: str
    image: Optional[str] = None


class AuthorShortOut(BaseModel):
    """Simplified author info."""

    slug: str
    username: str
    first_name: str | None = None
    profile_image_url: str | None = None

    @field_validator('profile_image_url', mode='before')
    @classmethod
    def convert_image_url_to_full(cls, v):
        return get_full_media_url(v)


class CollectionShortOut(BaseModel):
    id: UUID
    slug: str
    author: Union[
        str, AuthorShortOut
    ]  # Can be author ID (str) or author details (dict)
    title: str
    description: Optional[str] = None
    words_count: int = 0
    words_languages: List[str] = Field(default_factory=list)
    last_4_words: List[CollectionWordOut] = Field(default_factory=list)
    available_words_count: Optional[int] = None
    read_access_level: Optional[str] = None
    add_access_level: Optional[str] = None
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
    pass


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: list
    next: str | None = None
    previous: str | None = None


class CollectionResolveOut(BaseModel):
    id: UUID
    slug: str


class CollectionSubscriptionDetailOut(BaseModel):
    collection_id: UUID
    collection_slug: str
    collection_title: str
    new_words: list[str] | None = None
    updated_words: list[str] | None = None
