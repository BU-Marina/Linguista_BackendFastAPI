"""Vocabulary API schemas (simplified)."""

from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from api.v1.translations.schemas import TranslationIn, TranslationOut
from api.v1.definitions.schemas import DefinitionIn, DefinitionOut
from api.v1.usage_examples.schemas import ExampleIn, ExampleOut
from api.v1.image_associations.schemas import ImageIn, ImageOut
from core.utils.urls import get_full_media_url


class TagOut(BaseModel):
    id: UUID
    name: str

    model_config = {'from_attributes': True}


class TypeOut(BaseModel):
    id: UUID
    slug: str
    # Localized name resolved according to Accept-Language
    name: str
    # Raw names for specific languages (kept for backward compatibility / admin tools)

    model_config = {'from_attributes': True}


class TranslationShortOut(BaseModel):
    """Minimal translation info for word lists."""

    text: str
    language: Optional[str] = None


class AuthorShortOut(BaseModel):
    """Simplified author info for word/collection lists and profiles."""

    slug: str
    username: str
    first_name: Optional[str] = None
    profile_image_url: Optional[str] = None

    @field_validator('profile_image_url', mode='before')
    @classmethod
    def convert_profile_image_url_to_full(cls, v):
        return get_full_media_url(v)


class WordCommentOut(BaseModel):
    """Minimal word comment info for word profile."""

    id: UUID
    word_id: UUID
    author_id: UUID
    author: Optional[AuthorShortOut] = None
    text: str
    author_liked: bool = False
    liked_by_user: bool = False
    disliked_by_user: bool = False
    likes_count: int = 0
    dislikes_count: int = 0
    answers_count: int = 0
    created: datetime | None = None
    modified: datetime | None = None
    modified_relative: str = ''
    text_modified: bool = False


class WordCommentsPageOut(BaseModel):
    count: int
    next: str | None = None
    previous: str | None = None
    results: List[WordCommentOut]


class WordCommentIn(BaseModel):
    text: str


class WordListOut(BaseModel):
    id: UUID
    slug: str
    text: str
    language: Optional[str] = None
    activity_status: Optional[str] = None
    activity_progress: Optional[int] = None
    is_problematic: Optional[bool] = None
    background_image_url: Optional[str] = None
    translations_count: int = 0
    translations: List[TranslationShortOut] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    types: List[str] = Field(default_factory=list)
    favorite: bool = False
    author: Optional[str] = None  # username
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    @field_validator('background_image_url', mode='before')
    @classmethod
    def convert_background_image_url_to_full(cls, v):
        return get_full_media_url(v)


class RelatedWordsOut(BaseModel):
    count: int
    results: List[WordListOut]


class WordListWithAuthorOut(WordListOut):
    author: AuthorShortOut | None = None

    def model_dump(self, **kwargs):
        """Exclude activity_status and activity_progress from serialization."""
        data = super().model_dump(**kwargs)
        data.pop('activity_status', None)
        data.pop('activity_progress', None)
        return data


class WordIn(BaseModel):
    id: Optional[UUID] = None  # If provided, update instead of create
    text: str
    language: str
    note: Optional[str] = None
    is_problematic: Optional[bool] = None
    tags: List[str] = Field(default_factory=list)
    types: List[str] = Field(default_factory=list)
    translations: List[TranslationIn] = Field(default_factory=list)
    definitions: List[DefinitionIn] = Field(default_factory=list)
    examples: List[ExampleIn] = Field(default_factory=list)
    # Frontend sends "image_associations"; map it into images via alias
    images: List[ImageIn] = Field(default_factory=list, alias='image_associations')
    synonyms: List['RelationWordIn'] = Field(default_factory=list)
    antonyms: List['RelationWordIn'] = Field(default_factory=list)
    similars: List['RelationWordIn'] = Field(default_factory=list)


class WordInPartial(BaseModel):
    """
    Partial payload for PATCH operations.
    All fields are optional so clients can send only what they want to change.
    """

    id: Optional[UUID] = None
    text: Optional[str] = None
    language: Optional[str] = None
    note: Optional[str] = None
    is_problematic: Optional[bool] = None
    tags: Optional[List[str]] = None
    types: Optional[List[str]] = None
    translations: Optional[List[TranslationIn]] = None
    definitions: Optional[List[DefinitionIn]] = None
    examples: Optional[List[ExampleIn]] = None
    # Frontend sends "image_associations"; map it into images via alias
    images: Optional[List[ImageIn]] = Field(default=None, alias='image_associations')
    synonyms: Optional[List['RelationWordIn']] = None
    antonyms: Optional[List['RelationWordIn']] = None
    similars: Optional[List['RelationWordIn']] = None


class SourceWordOut(BaseModel):
    """Source word info when word is borrowed."""

    id: UUID
    slug: str
    text: str
    author: Optional[AuthorShortOut] = None


class WordReadOut(WordListOut):
    author: Optional[AuthorShortOut] = None
    note: Optional[str] = None
    source_word: Optional[SourceWordOut] = None
    translations: List[TranslationOut] = Field(default_factory=list)
    examples: List[ExampleOut] = Field(default_factory=list)
    definitions: List[DefinitionOut] = Field(default_factory=list)
    images: List[ImageOut] = Field(default_factory=list)
    # frontend expects image_associations, keep both for compatibility
    image_associations: List[ImageOut] = Field(default_factory=list)
    images_count: int = 0
    definitions_count: int = 0
    examples_count: int = 0
    synonyms_count: int = 0
    synonyms: List[dict] = Field(default_factory=list)
    collections_count: int = 0
    collections: List[dict] = Field(default_factory=list)
    comments_count: int = 0
    comments: List[WordCommentOut] = Field(default_factory=list)
    read_access_level: Optional[str] = None
    add_access_level: Optional[str] = None
    allow_access_change: bool = True
    allow_comments: bool = True


class RelationWordIn(BaseModel):
    """
    Relation payload can be:
    - existing word reference via id or slug
    - embedded new word payload (text + language + optional nested objects)
    """

    id: Optional[UUID] = None
    slug: Optional[str] = None
    text: Optional[str] = None
    language: Optional[str] = None
    note: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    types: List[str] = Field(default_factory=list)
    translations: List[TranslationIn] = Field(default_factory=list)
    definitions: List[DefinitionIn] = Field(default_factory=list)
    examples: List[ExampleIn] = Field(default_factory=list)
    images: List[ImageIn] = Field(default_factory=list, alias='image_associations')

    def is_reference(self) -> bool:
        return bool(self.id or self.slug)

    def ensure_creatable(self, default_language: str | None):
        if self.is_reference():
            return
        if not self.text:
            raise ValueError('text is required for new related word')
        if not (self.language or default_language):
            raise ValueError('language is required for new related word')


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    next: str | None = None
    previous: str | None = None
    results: list


class WordsWithAuthorPageOut(PageOut):
    results: List[WordListWithAuthorOut]


class WordResolveOut(BaseModel):
    id: UUID
    slug: str


class WordCollectionsIn(BaseModel):
    collections: List[UUID]


class WordsIdsIn(BaseModel):
    words: List[UUID]


class WordAccessLevelUpdateIn(BaseModel):
    id: UUID
    read_access_level: Optional[str] = None
    add_access_level: Optional[str] = None
    allow_access_change: Optional[bool] = None


class SynonymListFromWordOut(BaseModel):
    id: UUID
    to_word: str
    from_word: WordReadOut
    note: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None


class OtherSynonymsListOut(BaseModel):
    translation_id: Optional[UUID] = None
    translation_language: Optional[str] = None
    word: Optional[str] = None
    synonyms: List[SynonymListFromWordOut] = Field(default_factory=list)


class SynonymReadOut(BaseModel):
    id: UUID
    to_word: WordReadOut
    from_word: WordReadOut
    other_synonyms: dict[str, OtherSynonymsListOut] = Field(default_factory=dict)
    note: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None


class MultipleWordsIn(BaseModel):
    words: List[WordIn]
    collections: List[str] = Field(default_factory=list)


class MultipleWordsCreateOut(PageOut):
    words_created_count: int
    words_created: List[UUID]
    collections_count: int
