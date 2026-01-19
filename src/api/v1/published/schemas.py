"""Schemas for published resources."""

from __future__ import annotations

from typing import List

from api.v1.vocabulary.schemas import WordListOut, WordReadOut, PageOut as WordsPageBase
from api.v1.collections.schemas import (
    CollectionShortOut,
    CollectionReadOut,
    PageOut as CollectionsPageBase,
)
from api.v1.translations.schemas import TranslationOut, PageOut as TranslationsPageBase
from api.v1.definitions.schemas import DefinitionOut, PageOut as DefinitionsPageBase
from api.v1.usage_examples.schemas import ExampleOut, PageOut as ExamplesPageBase
from api.v1.image_associations.schemas import ImageOut, PageOut as ImagesPageBase
from api.v1.vocabulary.schemas import PageOut as SynonymsPageBase
from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional
from core.constants import RequestStatusEnum
from core.utils.urls import get_full_media_url


class WordsPageOut(WordsPageBase):
    results: List[WordListOut]


class TranslationShortOut(BaseModel):
    """Minimal translation info for word lists."""

    text: str
    language: Optional[str] = None


class AuthorShortOut(BaseModel):
    """Simplified author info for word/collection lists."""

    slug: str
    username: str
    first_name: str | None = None
    profile_image_url: str | None = None

    @field_validator('profile_image_url', mode='before')
    @classmethod
    def convert_image_url_to_full(cls, v):
        return get_full_media_url(v)


class AuthorOut(BaseModel):
    """Author info for word profile."""

    id: UUID
    slug: str
    username: str
    first_name: str | None = None
    profile_image_url: str | None = None
    profile_header_image_url: str | None = None
    is_official: bool = False
    allow_subscriptions: bool = True
    subscribers_count: int = 0
    is_subscribed: bool = False
    enable_notifications: bool = False

    @field_validator('profile_image_url', 'profile_header_image_url', mode='before')
    @classmethod
    def convert_profile_urls(cls, v):
        return get_full_media_url(v)


class WordListWithAuthorOut(WordListOut):
    author: AuthorShortOut | None = None
    background_image_url: str | None = None
    translations: list[TranslationShortOut] = []

    @field_validator('background_image_url', mode='before')
    @classmethod
    def convert_background_image_url_to_full(cls, v):
        return get_full_media_url(v)


class WordsWithAuthorPageOut(WordsPageBase):
    results: List[WordListWithAuthorOut]


class CollectionsPageOut(CollectionsPageBase):
    results: List[CollectionShortOut]


class TranslationsPageOut(TranslationsPageBase):
    results: List[TranslationOut]


class DefinitionsPageOut(DefinitionsPageBase):
    results: List[DefinitionOut]


class ExamplesPageOut(ExamplesPageBase):
    results: List[ExampleOut]


class ImagesPageOut(ImagesPageBase):
    results: List[ImageOut]


class SynonymsPageOut(SynonymsPageBase):
    results: List[WordListOut]


class CollectionCommentIn(BaseModel):
    text: str


class CollectionCommentOut(BaseModel):
    id: UUID
    collection_id: UUID
    author_id: UUID
    text: str
    author_liked: bool = False
    likes_count: int = 0
    dislikes_count: int = 0
    answers_count: int = 0
    created: datetime | None = None
    modified: datetime | None = None

    model_config = {'from_attributes': True}


class CollectionCommentsPageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: List[CollectionCommentOut]


class WordCommentIn(BaseModel):
    text: str


class WordCommentOut(BaseModel):
    id: UUID
    word_id: UUID
    author_id: UUID
    text: str
    author_liked: bool = False
    likes_count: int = 0
    dislikes_count: int = 0
    answers_count: int = 0
    created: datetime | None = None
    modified: datetime | None = None

    model_config = {'from_attributes': True}


class WordPublishedProfileOut(WordReadOut):
    author: AuthorOut
    synonyms: list = []
    collections: list[CollectionShortOut] = []
    comments_count: int = 0
    comments: list[WordCommentOut] = []
    images_count: int = 0
    definitions_count: int = 0
    examples_count: int = 0
    synonyms_count: int = 0
    collections_count: int = 0
    favorite_for_amount: int = 0
    borrowings_amount: int = 0


class CollectionPublishedProfileOut(BaseModel):
    id: UUID
    slug: str
    author: AuthorOut
    title: str
    description: str | None = None
    favorite: bool = False
    created: datetime | None = None
    modified: datetime | None = None
    words_languages: list[str] = []
    words_count: int = 0
    words_texts: dict[str, list[str]] = {}
    words_images: list[str] = []
    words_images_count: int = 0
    words_translations_count: int = 0
    words_definitions_count: int = 0
    words_examples_count: int = 0
    translations: TranslationsPageOut | None = None
    image_associations: ImagesPageOut | None = None
    definitions: DefinitionsPageOut | None = None
    examples: ExamplesPageOut | None = None
    read_access_level: str | None = None
    add_access_level: str | None = None
    borrowings_amount: int = 0
    favorite_for_amount: int = 0
    views_amount: int = 0
    last_viewed: str | None = None
    borrowed: bool = False
    borrow_new_words_count: int = 0
    subscribers_count: int = 0
    subscribed: bool = False
    enable_notifications: bool = False
    new_words: list[str] = []
    updated_words: list[str] = []
    last_word_added: str | None = None
    allow_comments: bool = True
    comments_count: int = 0
    comments: list[CollectionCommentOut] = []
    allow_suggestions: bool = True
    allow_suggestions_notifications: bool = True
    suggestions_count: int = 0
    suggestions_approved_count: int = 0
    suggestions_rejected_count: int = 0
    disallow_suggestions_for: bool = False
    suggestions: list[CollectionSuggestedWordOut] = []


class WordCommentsPageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: List[WordCommentOut]


class CollectionSuggestedWordOut(BaseModel):
    id: UUID
    word_id: UUID
    collection_id: UUID
    user_id: UUID
    status: str = RequestStatusEnum.PENDING
    created: datetime | None = None

    model_config = {'from_attributes': True}


class CollectionSuggestedWordsPageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: List[CollectionSuggestedWordOut]


__all__ = [
    'WordListOut',
    'WordReadOut',
    'WordsPageOut',
    'AuthorOut',
    'AuthorShortOut',
    'WordListWithAuthorOut',
    'WordsWithAuthorPageOut',
    'WordPublishedProfileOut',
    'CollectionShortOut',
    'CollectionReadOut',
    'CollectionsPageOut',
    'TranslationOut',
    'TranslationsPageOut',
    'DefinitionOut',
    'DefinitionsPageOut',
    'ExampleOut',
    'ExamplesPageOut',
    'ImageOut',
    'ImagesPageOut',
    'SynonymsPageOut',
    'WordCommentIn',
    'WordCommentOut',
    'WordCommentsPageOut',
    'CollectionPublishedProfileOut',
]
