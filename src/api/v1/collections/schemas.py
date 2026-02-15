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


class SourceCollectionOut(BaseModel):
    """Source collection info when collection is borrowed."""

    id: UUID
    slug: str
    title: str
    author: Optional[AuthorShortOut] = None


class CollectionReadOut(CollectionShortOut):
    # In profile responses we always return full author info
    author: AuthorShortOut
    source_collection: Optional[SourceCollectionOut] = None
    words_translations_count: int = 0
    words_images_count: int = 0
    words_definitions_count: int = 0
    words_examples_count: int = 0
    allow_comments: bool = True
    allow_suggestions: bool = True
    allow_suggestions_notifications: bool = True
    comments_count: int = 0
    comments: list['CollectionCommentOut'] = []
    favorite_for_amount: int = 0
    views_amount: int = 0
    borrowings_amount: int = 0
    borrowed: bool = False
    words_images: list[str] = Field(default_factory=list)
    words_texts: dict[str, list[str]] = Field(default_factory=dict)
    subscribers_count: int = 0


class CollectionIn(BaseModel):
    title: str
    description: Optional[str] = None
    words: Optional[List[UUID]] = None  # Word IDs
    allow_comments: Optional[bool] = True
    allow_suggestions: Optional[bool] = True
    allow_suggestions_notifications: Optional[bool] = True
    read_access_level: Optional[str] = None
    add_access_level: Optional[str] = None


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


class CollectionCommentIn(BaseModel):
    text: str


class CollectionCommentOut(BaseModel):
    id: UUID
    collection: str  # collection slug
    author: AuthorShortOut
    text: str
    author_liked: bool = False
    liked_by_user: bool = False
    disliked_by_user: bool = False
    likes_count: int = 0
    dislikes_count: int = 0
    answers_count: int = 0
    modified_relative: str = ''
    text_modified: bool = False


class CollectionCommentsPageOut(BaseModel):
    count: int
    next: str | None = None
    previous: str | None = None
    results: List[CollectionCommentOut]


class CollectionSubscriptionDetailOut(BaseModel):
    collection_id: UUID
    collection_slug: str
    collection_title: str
    new_words: list[str] | None = None
    updated_words: list[str] | None = None
