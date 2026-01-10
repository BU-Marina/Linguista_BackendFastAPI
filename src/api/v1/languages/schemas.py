"""Languages API schemas."""

from typing import Optional

from pydantic import BaseModel, Field


class LanguageBase(BaseModel):
    id: str
    isocode: str
    name_local: Optional[str] = None
    name_en: Optional[str] = None
    name_ru: Optional[str] = None
    flag_icon: Optional[str] = None
    sorting: Optional[int] = None
    learning_available: bool = False
    interface_available: bool = False
    words_count: Optional[int] = None
    is_native: Optional[bool] = None
    is_learning: Optional[bool] = None


class LanguageCoverOut(BaseModel):
    id: str
    image_url: str
    default: bool = False
    is_current_cover: bool = False


class LearningLanguageOut(BaseModel):
    id: str
    slug: str
    language: LanguageBase
    level: Optional[str] = None
    is_confirmed: bool = False
    is_taught: bool = False
    cover_url: Optional[str] = None
    cover_id: Optional[str] = None
    cover_height: Optional[int] = None
    cover_width: Optional[int] = None
    words_count: int = 0
    inactive_words_count: int = 0
    active_words_count: int = 0
    mastered_words_count: int = 0


class LearningLanguageCreateIn(BaseModel):
    language_isocode: str = Field(..., alias="language")
    level: Optional[str] = None
    is_taught: bool = False

    model_config = {
        "populate_by_name": True,
    }


class LearningLanguagesListOut(BaseModel):
    count: int
    results: list[LearningLanguageOut]


class LanguagesListOut(BaseModel):
    count: int
    results: list[LanguageBase]


class CollectionShortOut(BaseModel):
    id: str
    slug: str
    title: str
    words_count: int = 0


class CollectionsByLanguageOut(BaseModel):
    count: int
    results: list[CollectionShortOut]


class CoverSetIn(BaseModel):
    cover_id: Optional[str] = None
    image_url: Optional[str] = None


class CoverDeleteIn(BaseModel):
    cover_id: str
