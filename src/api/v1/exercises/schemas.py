"""Exercises schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from core.utils.urls import get_full_media_url


class HintOut(BaseModel):
    """Public schema for exercise hints (DRF-compatible)."""

    id: UUID
    name: str
    description: str
    code: str
    variants_mode: bool
    free_input_mode: bool
    word_customization_content_needed: Optional[str] = None

    model_config = {'from_attributes': True}


class ExerciseShortOut(BaseModel):
    id: UUID
    slug: str
    name: str
    description: Optional[str] = None
    constraint_description: Optional[str] = None
    icon: Optional[str] = None
    available: bool = False
    favorite: bool = False
    # For list responses frontend expects full HintDto objects here
    hints_available: List[HintOut] = Field(default_factory=list)
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
    """Full exercise details; currently same hints shape as list (HintOut)."""


class ExerciseConfigurationIn(BaseModel):
    # Exercise slug is taken from the path in FastAPI; this field is kept
    # only for parity with DRF, but is not required here.
    exercise_slug: str | None = None
    # Config fields that frontend sends (match ExerciseConfigurationOut)
    input_mode: Optional[str] = None
    answer_time_limit: Optional[int] = None
    time_limit_mode: Optional[str] = None
    repetitions_amount: Optional[int] = None
    translations_mode: Optional[str] = None
    definitions_mode: Optional[str] = None
    words: List[UUID] = Field(default_factory=list)
    words_set: List[UUID] = Field(default_factory=list)
    hints_available: List[UUID] = Field(default_factory=list)
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
