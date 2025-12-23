"""Achievements app constants."""

APP_LABEL = "achievements"


class AchievementsLengthLimits:
    """Length limits constants."""

    ACHIEVEMENT_NAME_MAX_LENGTH = 64
    ACHIEVEMENT_DESCRIPTION_MAX_LENGTH = 256

    ACHIEVEMENT_GROUP_TITLE_MAX_LENGTH = 64


class AchievementTypeEnum:
    WORDS_SAVE = 'words_save'
    COLLECTIONS_SAVE = 'collections_save'
    ACTIVITY_STATUS_AMOUNT = 'activity_status_amount'
    LANGUAGES_ADD = 'languages_add'
    WORDS_BY_LANGUAGES_AMOUNT = 'words_by_languages_amount'
    RUN_MISTAKES_CORRECTION = 'run_mistakes_correction'
    RUN_EXERCISE = 'run_exercise'
    COLLECTION_ACTIVITY = 'collection_activity'
    STUDY_GROUPS = 'study_groups'
    STRIKE_SERIA = 'strike_seria'
    GOALS_ACCOMPLISH = 'goals_accomplish'
    ACHIEVEMENTS_AMOUNT = 'achievement_amount'
    MATERIALS_AMOUNT = 'materials_amount'
    CHATS_WORDS_USAGE = 'chats_words_usage'
    EXERCISES_WORDS_USAGE = 'exercises_words_usage'
    CHATS_AMOUNT = 'chats_amount'
    FRIENDS_AMOUNT = 'friends_amount'
    FAVORITE_AUTHOR = 'favorite_author'
    WORDS_BORROWINGS = 'words_borrowings'
    COLLECTIONS_BORROWINGS = 'collections_borrowings'
    GRAMMARS_BORROWINGS = 'grammars_borrowing'
    GOAL_MEMBERS = 'goal_members'
    COLLECTION_COAUTHORS = 'collection_coauthors'
    SUBSCRIBERS = 'subscribers'
    SETTINGS = 'settings'

    achievement_types = (
        (WORDS_SAVE, WORDS_SAVE),
        (COLLECTIONS_SAVE, COLLECTIONS_SAVE),
        (ACTIVITY_STATUS_AMOUNT, ACTIVITY_STATUS_AMOUNT),
        (LANGUAGES_ADD, LANGUAGES_ADD),
        (WORDS_BY_LANGUAGES_AMOUNT, WORDS_BY_LANGUAGES_AMOUNT),
        (RUN_MISTAKES_CORRECTION, RUN_MISTAKES_CORRECTION),
        (RUN_EXERCISE, RUN_EXERCISE),
        (COLLECTION_ACTIVITY, COLLECTION_ACTIVITY),
        (STUDY_GROUPS, STUDY_GROUPS),
        (STRIKE_SERIA, STRIKE_SERIA),
        (GOALS_ACCOMPLISH, GOALS_ACCOMPLISH),
        (ACHIEVEMENTS_AMOUNT, ACHIEVEMENTS_AMOUNT),
        (MATERIALS_AMOUNT, MATERIALS_AMOUNT),
        (CHATS_WORDS_USAGE, CHATS_WORDS_USAGE),
        (EXERCISES_WORDS_USAGE, EXERCISES_WORDS_USAGE),
        (CHATS_AMOUNT, CHATS_AMOUNT),
        (FRIENDS_AMOUNT, FRIENDS_AMOUNT),
        (FAVORITE_AUTHOR, FAVORITE_AUTHOR),
        (WORDS_BORROWINGS, WORDS_BORROWINGS),
        (COLLECTIONS_BORROWINGS, COLLECTIONS_BORROWINGS),
        (GRAMMARS_BORROWINGS, GRAMMARS_BORROWINGS),
        (GOAL_MEMBERS, GOAL_MEMBERS),
        (COLLECTION_COAUTHORS, COLLECTION_COAUTHORS),
        (SUBSCRIBERS, SUBSCRIBERS),
        (SETTINGS, SETTINGS),
    )

    max_length = 32