"""..."""

from uuid import UUID
from typing import List, Optional

from pydantic import BaseModel, Field
from fastapi_users.schemas import (
    BaseUserCreate,
)

from api.v1.users.schemas import (
    LearningLanguageInline,
)

from .examples import USER_PROFILE_READ


class UserCreate(BaseUserCreate):
    username: str


class UserSettingsRead(BaseModel):
    """
    Соответствует UserSettingsReadUpdateSerializer.
    Подставлены разумные типы — при необходимости скорректируй (например enum для access levels).
    """

    interface_language: Optional[str] = None
    words_default_access_level: Optional[str] = None
    collections_default_access_level: Optional[str] = None
    collections_allow_comments: Optional[bool] = None
    words_allow_comments: Optional[bool] = None
    collections_allow_suggestions: Optional[bool] = None
    collections_allow_suggestions_notifications: Optional[bool] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


class UserMeRead(BaseModel):
    id: UUID
    slug: str
    username: str
    first_name: Optional[str] = None

    profile_image_url: Optional[str] = None
    profile_header_image_url: Optional[str] = None
    profile_description: Optional[str] = None

    is_teacher: bool = Field(False)
    teaching_goal: Optional[str] = None

    interests: List[str] = Field(default_factory=list)
    cities: List[str] = Field(default_factory=list)

    native_languages: List[str] = Field(default_factory=list)  # slug_field isocode
    learning_languages: List[LearningLanguageInline] = Field(default_factory=list)
    taught_languages: List[LearningLanguageInline] = Field(default_factory=list)

    onboarding_passed: bool
    settings: Optional[UserSettingsRead] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "json_schema_extra": {
            "example": USER_PROFILE_READ,
        },
    }


class UserMeUpdate(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None

    profile_image_url: Optional[str] = None
    profile_header_image_url: Optional[str] = None
    profile_description: Optional[str] = None

    is_teacher: Optional[bool] = None
    teaching_goal: Optional[str] = None

    interests: Optional[List[str]] = None
    cities: Optional[List[str]] = None

    native_languages: Optional[List[str]] = None  # slug_field isocode
    learning_languages: Optional[List[LearningLanguageInline]] = None
    taught_languages: Optional[List[LearningLanguageInline]] = None

    settings: Optional[UserSettingsRead] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "json_schema_extra": {
            "example": USER_PROFILE_READ,
        },
    }


class UserSettingsUpdate(BaseModel):
    """
    Соответствует UserSettingsReadUpdateSerializer.
    Подставлены разумные типы — при необходимости скорректируй (например enum для access levels).
    """

    interface_language: Optional[str] = None
    words_default_access_level: Optional[str] = None
    collections_default_access_level: Optional[str] = None
    collections_allow_comments: Optional[bool] = None
    words_allow_comments: Optional[bool] = None
    collections_allow_suggestions: Optional[bool] = None
    collections_allow_suggestions_notifications: Optional[bool] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


class DeleteAccountRequest(BaseModel):
    password: Optional[str] = None
    reason: Optional[str] = None  # опционально для логов/аналитики

    model_config = {
        "from_attributes": True,
    }


class UserMeReadScalar(BaseModel):
    id: UUID
    username: str
    email: Optional[str] = None

    model_config = {
        "from_attributes": True,
    }
