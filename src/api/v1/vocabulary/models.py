"""Container for vocabulary-related ORM models."""

from apps.vocabulary.models import (
    Word,
    WordTranslation,
    WordTranslations,
    Definition,
    WordDefinitions,
    UsageExample,
    WordUsageExamples,
    WordType,
    Collection,
    WordsInCollections,
    FavoriteWord,
    FavoriteCollection,
    Synonym,
    Antonym,
    Similar,
    Form,
    ImageAssociation,
    WordImageAssociations,
)
from apps.languages.models import Language
from apps.core.models import Tag

VOCAB_MODELS = {
    "Word": Word,
    "WordTranslation": WordTranslation,
    "WordTranslations": WordTranslations,
    "Definition": Definition,
    "WordDefinitions": WordDefinitions,
    "UsageExample": UsageExample,
    "WordUsageExamples": WordUsageExamples,
    "Tag": Tag,
    "WordType": WordType,
    "Collection": Collection,
    "WordsInCollections": WordsInCollections,
    "FavoriteWord": FavoriteWord,
    "FavoriteCollection": FavoriteCollection,
    "Synonym": Synonym,
    "Antonym": Antonym,
    "Similar": Similar,
    "Form": Form,
    "ImageAssociation": ImageAssociation,
    "WordImageAssociations": WordImageAssociations,
    "Language": Language,
}
