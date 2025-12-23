"""Exercises app constants."""

import types

APP_LABEL = "exercises"


exercises_lookups = types.SimpleNamespace()
exercises_lookups.TRANSLATOR_EXERCISE_SLUG = 'translator'
exercises_lookups.ASSOCIATE_EXERCISE_SLUG = 'associate-it'
exercises_lookups.WITH_LETTER_EXERCISE_SLUG = 'with-letter'
exercises_lookups.DEFINITIONS_TIME_EXERCISE_SLUG = 'definitions-time'

hints_codes = types.SimpleNamespace()
hints_codes.ASSOCIATION_HINT_CODE = 'show_association'
hints_codes.FIRST_LETTER_HINT_CODE = 'show_first_letter'
hints_codes.SECOND_LETTER_HINT_CODE = 'show_second_letter'
hints_codes.LETTERS_AMOUNT_HINT_CODE = 'show_letters_amount'
hints_codes.SYNONYM_HINT_CODE = 'show_synonym'
hints_codes.REMOVE_INCORRECT_HINT_CODE = 'remove_incorrect'
hints_codes.REMOVE_HALF_HINT_CODE = 'remove_half'

VARIANTS_AMOUNT = 4
EXERCISE_WORDS_MIN_AMOUNT = 4
EXERCISE_WORDS_MAX_AMOUNT = 1000


class ExercisesLengthLimits:
    """Length limits constants."""

    WORDS_SET_NAME_MAX_LENGTH = 64

    EXERCISES_SET_TITLE_MAX_LENGTH = 64

    EXERCISE_TASK_MAX_LENGTH = 64
    EXERCISE_TASK_CONTENT_MAX_LENGTH = 256

    VARIANTS_LIST_MAX_LENGTH = 6
    ANSWER_TEXT_MAX_LENGTH = 1024
    TASK_TEXT_MAX_LENGTH = 2048


class ExercisesInputModeEnum:
    FREE_INPUT = 'FI'
    FREE_INPUT_MAX = 'FIM'
    VARIANTS = 'V'
    VARIANTS_MAX = 'VM'
    ALTERNATELY = 'A'
    ALTERNATELY_MAX = 'AM'

    input_modes = (
        (FREE_INPUT, 'Free input'),
        (FREE_INPUT_MAX, 'Free input (several answers allowed)'),
        (VARIANTS, 'Choose from variants'),
        (VARIANTS_MAX, 'Choose from variants (several answers allowed)'),
        (ALTERNATELY, 'Alternately'),
        (ALTERNATELY_MAX, 'Alternately (several answers allowed)'),
    )

    max_length = 3


class ExercisesAnswerEnum:
    CORRECT = 'C'
    INCORRECT = 'I'
    SEMI_CORRECT = 'SC'

    answer_verdicts = (
        (CORRECT, 'Correct'),
        (INCORRECT, 'Incorrect'),
        (SEMI_CORRECT, 'Semi-correct'),
    )

    max_length = 2


class TranslationsModeEnum:
    FROM_LEARNING = 'LTN'
    FROM_NATIVE = 'NTL'
    FROM_LEARNING_TO_LEARNING = 'LTL'
    ALTERNATELY = 'A'

    translations_modes = (
        (FROM_LEARNING, 'From learning'),
        (FROM_NATIVE, 'From native'),
        (FROM_LEARNING_TO_LEARNING, 'From learning to learning'),
        (ALTERNATELY, 'Alternately'),
    )

    max_length = 3


class DefinitionsModeEnum:
    DEFINITION_BY_WORD = 'DBW'
    WORD_BY_DEFINITION = 'WBD'
    ALTERNATELY = 'A'

    definitions_modes = (
        (DEFINITION_BY_WORD, 'Definition by word'),
        (WORD_BY_DEFINITION, 'Word by definition'),
        (ALTERNATELY, 'Alternately'),
    )

    max_length = 3


class TimeLimitModeEnum:
    ALL = 'A'
    RANDOM = 'R'

    time_limit_modes = (
        (ALL, 'All tasks'),
        (RANDOM, 'Random tasks'),
    )

    max_length = 1


class TaskTypesEnum:
    TEXT = 'T'
    IMAGE = 'I'

    enum = (
        (TEXT, 'Text'),
        (IMAGE, 'Image'),
    )

    max_length = 1
