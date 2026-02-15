"""..."""

import os

ADMIN_USERNAME = os.getenv('DJANGO_SUPERUSER_USERNAME', default='admin')

REGEX_TEXT_MASK = r"^(\p{L}+)([\p{L}-!?.,…:/&'`’()  \d]*)"
REGEX_TEXT_MASK_DETAIL = (
    'Acceptable characters: Letters from any language, '
    'Hyphen, Exclamation point, Question mark, Dot, Comma, Colon, Apostrophe, Slash. '
    'Make sure text begins with a letter.'
)

REGEX_COLLECTIONS_TITLE_MASK = r"^([\p{L}-!?.,…:/|&'`’()  \d]*)"
REGEX_COLLECTIONS_TITLE_MASK_DETAIL = (
    'Acceptable characters: Letters from any language, Digits '
    'Hyphen, Exclamation point, Question mark, Dot, Comma, Colon, Apostrophe, Slash. '
)

REGEX_FORM_GROUP_NAME_MASK = r"^([\p{L}-!?.,:/&'`’()  \d]*)"
REGEX_FORM_GROUP_NAME_MASK_DETAIL = (
    'Acceptable characters: Letters from any language, Digits '
    'Hyphen, Exclamation point, Question mark, Dot, Comma, Colon, Apostrophe, Slash. '
)

REGEX_EXAMPLES_TEXT_MASK = r"^([\p{L}-!?.,…:/&'`’()  \d]*)"
REGEX_EXAMPLES_TEXT_MASK_DETAIL = (
    'Acceptable characters: Letters from any language, Digits '
    'Hyphen, Exclamation point, Question mark, Dot, Comma, Colon, Apostrophe, Slash. '
)

REGEX_DEFINITIONS_TEXT_MASK = r"^([\p{L}-!?.,…:/&'`’()  \d]*)"
REGEX_DEFINITIONS_TEXT_MASK_DETAIL = (
    'Acceptable characters: Letters from any language, Digits '
    'Hyphen, Exclamation point, Question mark, Dot, Comma, Colon, Apostrophe, Slash. '
)

REGEX_HEXCOLOR_MASK = r'^#[\w]+$'
REGEX_HEXCOLOR_MASK_DETAIL = 'Color must be in hex format.'

MAX_IMAGE_SIZE_MB = 20  # 20 MB is max size for uploaded images
MAX_IMAGE_SIZE = MAX_IMAGE_SIZE_MB * 1024 * 1024  # uploaded images max size in bytes

DEFAULT_MAX_SLUG_LENGTH = 1024

WEB_SOCKET_NORMAL_CLOSURE_CODE = 1000
WEB_SOCKET_SERVER_ERROR_CODE = 1011
WEB_SOCKET_MANUALLY_CLOSURE_CODE = 3000


class AmountLimits:
    """Class to store amount limit constants, detail messages."""

    class Vocabulary:
        MAX_TYPES_AMOUNT = 5
        MAX_TAGS_AMOUNT = 20
        MAX_TRANSLATIONS_AMOUNT = 10
        MAX_EXAMPLES_AMOUNT = 10
        MAX_DEFINITIONS_AMOUNT = 10
        MAX_FORMS_AMOUNT = 10
        MAX_IMAGES_AMOUNT = 10
        MAX_QUOTES_AMOUNT = 10
        MAX_SYNONYMS_AMOUNT = 16
        MAX_ANTONYMS_AMOUNT = 16
        MAX_SIMILARS_AMOUNT = 16
        MAX_FORM_GROUPS_AMOUNT = 4

        class Details:
            TYPES_AMOUNT_EXCEEDED = 'Word types amount limit exceeded'
            TAGS_AMOUNT_EXCEEDED = 'Word tags amount limit exceeded'
            TRANSLATIONS_AMOUNT_EXCEEDED = 'Word translations amount limit exceeded'
            EXAMPLES_AMOUNT_EXCEEDED = 'Word examples amount limit exceeded'
            DEFINITIONS_AMOUNT_EXCEEDED = 'Word definitions amount limit exceeded'
            FORMS_AMOUNT_EXCEEDED = 'Word forms amount limit exceeded'
            IMAGES_AMOUNT_EXCEEDED = 'Word image-associations amount limit exceeded'
            QUOTES_AMOUNT_EXCEEDED = 'Word quote-associations amount limit exceeded'
            SYNONYMS_AMOUNT_EXCEEDED = 'Word synonyms amount limit exceeded'
            ANTONYMS_AMOUNT_EXCEEDED = 'Word antonyms amount limit exceeded'
            SIMILARS_AMOUNT_EXCEEDED = 'Similar words amount limit exceeded'
            FORM_GROUPS_AMOUNT_EXCEEDED = 'Word form groups amount limit exceeded'

    class Languages:
        MAX_NATIVE_LANGUAGES_AMOUNT = 2
        MAX_LEARNING_LANGUAGES_AMOUNT = 5

        class Details:
            LEARNING_LANGUAGES_AMOUNT_EXCEEDED = (
                'Learning languages amount limit exceeded'
            )
            NATIVE_LANGUAGES_AMOUNT_EXCEEDED = 'Native languages amount limit exceeded'

    class Exercises:
        EXERCISE_MAX_WORDS_AMOUNT_LIMIT = 100
        MAX_WORD_SETS_AMOUNT_LIMIT = 50
        MAX_ANSWER_TIME_LIMIT = 5 * 60
        MIN_ANSWER_TIME_LIMIT = 5
        MAX_REPETITIONS_AMOUNT_LIMIT = 10
        MIN_REPETITIONS_AMOUNT_LIMIT = 1

        class Details:
            WORDS_AMOUNT_EXCEEDED = 'Words amount limit exceeded for this exercise'
            WORD_SETS_AMOUNT_EXCEEDED = (
                'Word sets amount limit exceeded for this exercise'
            )
            MAX_ANSWER_TIME_EXCEEDED = 'Maximum time limit exceeded'
            MIN_ANSWER_TIME_EXCEEDED = 'Minimum time limit exceeded'
            MAX_REPETITIONS_LIMIT_EXCEEDED = 'Maximum repetitions amount limit exceeded'
            MIN_REPETITIONS_LIMIT_EXCEEDED = 'Minimum repetitions amount limit exceeded'


class ActivityStatusEnum:
    INACTIVE = 'I'
    ACTIVE = 'A'
    MASTERED = 'M'

    activity_statuses = (
        (INACTIVE, 'Inactive'),
        (ACTIVE, 'Active'),
        (MASTERED, 'Mastered'),
    )

    max_length = 1

    activity_progress_default = 0


class LanguageLevelEnum:
    A1 = 'a1'
    A2 = 'a2'
    B1 = 'b1'
    B2 = 'b2'
    C1 = 'c1'
    C2 = 'c2'

    levels = (
        (A1, 'A1 Breakthrough/Begginer'),
        (A2, 'A2 Waystage/Elementary'),
        (B1, 'B1 Threshold/Intermediate'),
        (B2, 'B2 Vantage/Upper Intermediate'),
        (C1, 'C1 Effective Operational Proficiency/Advanced'),
        (C2, 'C2 Mastery/Proficiency'),
    )

    max_length = 2


class WordUsageTypes:
    ANY = 'Any'
    EXERCISES = 'In exercises'
    CHATS = 'In chats'

    usage_types = (
        (ANY, 'Any'),
        (EXERCISES, 'In exercises'),
        (CHATS, 'In chats'),
    )

    max_length = 32


class GoalStatusEnum:
    ACTIVE = 'ACT'
    DEFERRED = 'DEF'
    FINISHED = 'FIN'
    ARCHIVED = 'ARC'

    goal_statuses = (
        (ACTIVE, 'Active'),
        (DEFERRED, 'Deferred'),
        (FINISHED, 'Accomplished'),
        (ARCHIVED, 'Archived'),
    )

    max_length = 3


class RequestStatusEnum:
    APPROVED = 'A'
    REJECTED = 'R'
    PENDING = 'P'

    request_statuses = (
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (PENDING, 'Pending'),
    )

    max_length = 1


class AccessLevelsEnum:
    PUBLIC = 'PUB'
    FRIENDS = 'FR'
    STUDY_GROUPS = 'SG'
    FRIENDS_AND_STUDY_GROUPS = 'FS'
    LINK = 'LNK'
    LIST = 'LST'
    PRIVATE = 'PRV'
    PAID = 'P'

    access_levels = (
        (PUBLIC, 'Public'),
        (FRIENDS, 'Friends'),
        (STUDY_GROUPS, 'Study groups'),
        (FRIENDS_AND_STUDY_GROUPS, 'Friends and study groups'),
        (LINK, 'Link'),
        (LIST, 'List'),
        (PRIVATE, 'Private'),
        (PAID, 'Paid'),
    )
    default_level = PUBLIC

    max_length = 8


class WordsCardsTypesEnum:
    STANDART = 'ST'
    SHORT = 'SH'
    LONG = 'L'

    cards_types = (
        (STANDART, 'Standart'),
        (SHORT, 'Short'),
        (LONG, 'Long'),
    )

    max_length = 2


class CoreLengthLimits:
    """Length limits constants."""

    TAG_MAX_LENGTH = 32
    REVIEW_TEXT_MAX_LENGTH = 256
