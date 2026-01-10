"""Exercises schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class ExerciseShortOut(BaseModel):
    id: UUID
    slug: str
    name: str
    icon: Optional[str] = None
    available: bool = False
    favorite: bool = False
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    model_config = {'from_attributes': True}


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
    author_id: UUID
    answer_time_limit: Optional[int] = None
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


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: list
