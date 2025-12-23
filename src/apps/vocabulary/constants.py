"""Vocabulary app constants."""

APP_LABEL = "vocabulary"


WORD_ACTIVITY_STATUS_MIN_PROGRESS = 0
WORD_ACTIVITY_STATUS_MAX_PROGRESS_DEFAULT = 2
WORD_ACTIVITY_STATUS_MAX_PROGRESS_PROBLEMATIC = 5

INACTIVE_DOWNGRADE_INTERVAL_DAYS = 2
ACTIVE_1_DOWNGRADE_INTERVAL_DAYS = 7
ACTIVE_2_DOWNGRADE_INTERVAL_DAYS = 14

DOWNGRADE_MAX_INCREASED_VALUE_DAYS = 60


class VocabularyLengthLimits:
    """Length limits constants."""

    MAX_WORD_LENGTH = 256
    MIN_WORD_LENGTH = 1
    MAX_TRANSLATION_LENGTH = 256
    MIN_TRANSLATION_LENGTH = 1
    MAX_DEFINITION_LENGTH = 512
    MIN_DEFINITION_LENGTH = 2
    MAX_EXAMPLE_LENGTH = 512
    MIN_EXAMPLE_LENGTH = 2
    MAX_EXAMPLE_SOURCE_LENGTH = 128
    MAX_EXAMPLE_SOURCE_LINK_LENGTH = 1024
    MAX_NOTE_LENGTH = 2048
    MIN_NOTE_LENGTH = 1
    MAX_COLLECTION_TITLE_LENGTH = 128
    MIN_COLLECTION_TITLE_LENGTH = 1
    MAX_COLLECTION_DESCRIPTION_LENGTH = 512
    MAX_FORMSGROUP_NAME_LENGTH = 64
    MIN_FORMSGROUP_NAME_LENGTH = 1
    MAX_FORMSGROUP_TRANSLATION_LENGTH = 64
    MAX_QUOTE_TEXT_LENGTH = 256
    MAX_QUOTE_AUTHOR_LENGTH = 64


# WORDS

words_popularity_ordering = (
    '-in_user_learning_languages',
    '-favorite_for_count',
    '-borrowings_count',
    '-views_count',
    '-comments_count',
    '-approves_count',
    '-teachers_approves_count',
    '-created',
    '-modified',
)

words_count_popularity_ordering = (
    '-words_count',
    '-created',
    '-modified',
)

words_list_prefetch_related = (
    'tags',
    'types',
    'translations',
    'image_associations',
    'form_groups',
)

words_list_select_related = (
    'author',
    'language',
)

# COLLECTIONS

collections_popularity_ordering = (
    '-subscribers_count',
    '-favorite_for_count',
    '-borrowings_count',
    '-views_count',
    '-comments_count',
    '-created',
    '-modified',
)

collections_subscribed_ordering = (
    '-new_words_count',
    '-updated_words_count',
    '-subscribers_count',
    '-favorite_for_count',
    '-borrowings_count',
    '-views_count',
    '-comments_count',
    '-created',
    '-modified',
)

collections_list_select_related = ('author',)
