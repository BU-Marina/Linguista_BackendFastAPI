"""Exercises schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from core.utils.urls import get_full_media_url


class ExerciseShortOut(BaseModel):
    id: UUID
    slug: str
    name: str
    description: Optional[str] = None
    constraint_description: Optional[str] = None
    icon: Optional[str] = None
    available: bool = False
    favorite: bool = False
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    model_config = {'from_attributes': True}

    @field_validator('icon', mode='before')
    @classmethod
    def convert_icon_to_full(cls, v):
        return get_full_media_url(v) or v


class ExerciseListOut(BaseModel):
    available: List[ExerciseShortOut] = Field(default_factory=list)
    unavailable: List[ExerciseShortOut] = Field(default_factory=list)


class ExerciseDetailOut(ExerciseShortOut):
    hints_available: List[UUID] = Field(default_factory=list)


class ExerciseConfigurationIn(BaseModel):
    exercise_slug: str
    words: List[UUID] = Field(default_factory=list)
    words_set: List[UUID] = Field(default_factory=list)
    hints_available: List[UUID] = Field(default_factory=list)
    answer_time_limit: Optional[int] = None
    hints_use_amount: Optional[int] = None
    is_default: bool = False


class ExerciseConfigurationOut(BaseModel):
    id: UUID
    exercise_id: UUID
    exercise_slug: str | None = None
    author_id: UUID
    input_mode: str | None = None
    answer_time_limit: Optional[int] = None
    time_limit_mode: str | None = None
    repetitions_amount: Optional[int] = None
    translations_mode: str | None = None
    definitions_mode: str | None = None
    hints_use_amount: Optional[int] = None
    is_default: bool = False
    words: List[UUID] = Field(default_factory=list)
    words_set: List[UUID] = Field(default_factory=list)
    hints_available: List[UUID] = Field(default_factory=list)

    model_config = {'from_attributes': True}


class WordsSetIn(BaseModel):
    name: str
    words: List[UUID] = Field(default_factory=list)


class WordsSetOut(BaseModel):
    id: UUID
    slug: str
    name: str
    words: List[UUID] = Field(default_factory=list)
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    model_config = {'from_attributes': True}


class RandomConfigIn(BaseModel):
    words_limit: Optional[int] = Field(default=None, alias='words_amount')

    model_config = {'populate_by_name': True}


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: list


class ConfigWordsPageOut(PageOut):
    results: List[UUID]
