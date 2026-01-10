"""Vocabulary API schemas (simplified)."""

from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from api.v1.translations.schemas import TranslationIn, TranslationOut
from api.v1.definitions.schemas import DefinitionIn, DefinitionOut
from api.v1.usage_examples.schemas import ExampleIn, ExampleOut
from api.v1.image_associations.schemas import ImageIn, ImageOut


class TagOut(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


class TypeOut(BaseModel):
    id: UUID
    name_en: str
    name_ru: str

    model_config = {"from_attributes": True}


class WordListOut(BaseModel):
    id: UUID
    slug: str
    text: str
    language: Optional[str] = None
    translations_count: int = 0
    tags: List[str] = Field(default_factory=list)
    types: List[str] = Field(default_factory=list)
    favorite: bool = False
    created: Optional[datetime] = None
    modified: Optional[datetime] = None


class RelatedWordsOut(BaseModel):
    count: int
    results: List[WordListOut]


class WordIn(BaseModel):
    text: str
    language: str
    note: Optional[str] = None
    activity_status: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    types: List[str] = Field(default_factory=list)
    translations: List[TranslationIn] = Field(default_factory=list)
    definitions: List[DefinitionIn] = Field(default_factory=list)
    examples: List[ExampleIn] = Field(default_factory=list)
    images: List[ImageIn] = Field(default_factory=list)
    synonyms: List["RelationWordIn"] = Field(default_factory=list)
    antonyms: List["RelationWordIn"] = Field(default_factory=list)
    similars: List["RelationWordIn"] = Field(default_factory=list)


class WordReadOut(WordListOut):
    note: Optional[str] = None
    activity_status: Optional[str] = None
    translations: List[TranslationOut] = Field(default_factory=list)
    examples: List[ExampleOut] = Field(default_factory=list)
    definitions: List[DefinitionOut] = Field(default_factory=list)
    images: List[ImageOut] = Field(default_factory=list)


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
    activity_status: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    types: List[str] = Field(default_factory=list)
    translations: List[TranslationIn] = Field(default_factory=list)
    definitions: List[DefinitionIn] = Field(default_factory=list)
    examples: List[ExampleIn] = Field(default_factory=list)
    images: List[ImageIn] = Field(default_factory=list)

    def is_reference(self) -> bool:
        return bool(self.id or self.slug)

    def ensure_creatable(self, default_language: str | None):
        if self.is_reference():
            return
        if not self.text:
            raise ValueError("text is required for new related word")
        if not (self.language or default_language):
            raise ValueError("language is required for new related word")


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: list


class MultipleWordsIn(BaseModel):
    words: List[WordIn]
    collections: List[str] = Field(default_factory=list)


class MultipleWordsCreateOut(PageOut):
    words_created_count: int
    words_created: List[UUID]
    collections_count: int
