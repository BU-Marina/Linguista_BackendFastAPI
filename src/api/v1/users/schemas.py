"""Users api schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator
from core.utils.urls import get_full_media_url


class LearningLanguageInline(BaseModel):
    """Inline representation for user learning/taught languages."""

    isocode: str
    level: Optional[str] = None
    is_confirmed: bool = False
    is_taught: bool = False
    words_count: Optional[int] = None


class UserListOut(BaseModel):
    """User list item."""

    id: Optional[str] = None
    slug: str
    username: str
    first_name: Optional[str] = None
    profile_image_url: Optional[str] = None
    profile_header_image_url: Optional[str] = None
    profile_description: Optional[str] = None
    is_teacher: bool = False
    teaching_goal: Optional[str] = None

    interests: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    native_languages: list[str] = Field(default_factory=list)

    learning_languages: list[LearningLanguageInline] = Field(default_factory=list)
    taught_languages: list[LearningLanguageInline] = Field(default_factory=list)

    collections_count: Optional[int] = None
    subscribers_count: Optional[int] = None
    is_subscribed: bool = False
    enable_notifications: bool = False

    learning_languages_overlap_percent: Optional[float] = None
    interests_overlap_percent: Optional[float] = None

    @field_validator('profile_image_url', 'profile_header_image_url', mode='before')
    @classmethod
    def convert_image_urls_to_full(cls, v):
        return get_full_media_url(v)


class PageOut(BaseModel):
    """Paginated response for list endpoints."""

    page: int
    limit: int
    count: int
    results: list[UserListOut]


class UserReadOut(BaseModel):
    """User profile representation."""

    id: str
    slug: str
    username: str
    first_name: Optional[str] = None

    profile_image_url: Optional[str] = None
    profile_header_image_url: Optional[str] = None
    profile_description: Optional[str] = None
    image_height: Optional[int] = None
    image_width: Optional[int] = None

    is_teacher: bool = False
    teaching_goal: Optional[str] = None

    allow_subscriptions: bool = False
    allow_buddy_search: bool = False

    interests: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)

    native_languages: list[str] = Field(default_factory=list)
    learning_languages: list[LearningLanguageInline] = Field(default_factory=list)
    taught_languages: list[LearningLanguageInline] = Field(default_factory=list)

    collections_count: Optional[int] = None
    subscribers_count: int = 0
    is_subscribed: bool = False

    enable_notifications: bool = False
    is_friend: bool = False
    is_friend_request_sent: bool = False

    new_words: list[str] = Field(default_factory=list)
    updated_words: list[str] = Field(default_factory=list)
    new_collections: list[str] = Field(default_factory=list)

    @field_validator('profile_image_url', 'profile_header_image_url', mode='before')
    @classmethod
    def convert_image_urls_to_full(cls, v):
        return get_full_media_url(v)


class SubscriptionToggleOut(BaseModel):
    """Response for subscribe/unsubscribe toggles."""

    is_subscribed: bool
    subscribers_count: int


class EnableNotificationsOut(BaseModel):
    """Response for notifications toggle."""

    enable_notifications: bool
    subscribers_count: int


class FriendRequestSentOut(BaseModel):
    """Response for add-to-friends action."""

    is_friend_request_sent: bool


class IsFriendOut(BaseModel):
    """Response for remove-from-friends action."""

    is_friend: bool
