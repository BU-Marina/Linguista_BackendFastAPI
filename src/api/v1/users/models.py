"""Centralized container for users-related ORM models."""

from apps.users.models import (
    User,
    UserSettings,
    City,
    Interest,
    Subscription,
    Friend,
    FriendRequest,
    users_user_cities,
    users_user_interests,
)
from apps.languages.models import (
    Language,
    UserLearningLanguage,
    UserNativeLanguage,
)

# Mapping used by services/queries to avoid circular imports and keep signatures tidy.
USER_MODELS = {
    "User": User,
    "UserSettings": UserSettings,
    "City": City,
    "Interest": Interest,
    "Language": Language,
    "UserLearningLanguage": UserLearningLanguage,
    "UserNativeLanguage": UserNativeLanguage,
    "Subscription": Subscription,
    "Friend": Friend,
    "FriendRequest": FriendRequest,
    "users_user_cities": users_user_cities,
    "users_user_interests": users_user_interests,
}
