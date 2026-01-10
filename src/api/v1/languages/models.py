"""Container with ORM models used by languages API."""

from apps.languages.models import (
    Language,
    LanguageCoverImage,
    UserLearningLanguage,
    UserNativeLanguage,
)
from apps.users.models import User
from apps.vocabulary.models import Word, Collection, WordsInCollections

LANGUAGE_MODELS = {
    "Language": Language,
    "LanguageCoverImage": LanguageCoverImage,
    "UserLearningLanguage": UserLearningLanguage,
    "UserNativeLanguage": UserNativeLanguage,
    "User": User,
    "Word": Word,
    "Collection": Collection,
    "WordsInCollections": WordsInCollections,
}
