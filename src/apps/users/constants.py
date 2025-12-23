"""Users app constants."""

APP_LABEL = "users"

GENDERS = (
    ('M', 'Male'),
    ('F', 'Female'),
)

BASE_PLAN = 'B'
ADVANCED_PLAN = 'A'
UNLIMITED_PLAN = 'U'
SUBSCRIPTION_PLANS = (
    (BASE_PLAN, 'Base'),
    (ADVANCED_PLAN, 'Advanced'),
    (UNLIMITED_PLAN, 'Unlimited'),
)

REGEX_NAME_MASK = r"^(\p{L}+)([\p{L}'`’ ]*)$"
REGEX_NAME_MASK_DETAIL = (
    'Acceptable characters: Letters from any language, '
    'Apostrophe, Space. '
    'Make sure name begin with a letter.'
)


class UsersLengthLimits:
    """Length limits constants."""

    FIRST_NAME_MAX_LENGTH = 32
    PROFILE_DESCRIPTION_MAX_LENGTH = 512
    TEACHING_GOAL_MAX_LENGTH = 64
    SOCIAL_LINK_NAME_MAX_LENGTH = 32
    SOCIAL_LINK_MAX_LENGTH = 2048
    CITY_NAME_MAX_LENGTH = 32
    INTEREST_NAME_MAX_LENGTH = 32

    GOAL_NAME_MAX_LENGTH = 32
    GOAL_DESCRIPTION_MAX_LENGTH = 128
    TASK_NAME_MAX_LENGTH = 64

    STUDY_PLAN_NAME_MAX_LENGTH = 32
    STUDY_PLAN_DESCRIPTION_MAX_LENGTH = 256

    CERTIFICATE_TITLE_MAX_LENGTH = 64
    REVIEW_TEXT_MAX_LENGTH = 1024

    MATERIAL_TITLE_MAX_LENGTH = 32
    MATERIAL_TEXT_MAX_LENGTH = 1024
    MATERIAL_GROUP_TITLE_MAX_LENGTH = 64

    GRAMMAR_NAME_MAX_LENGTH = 64
    GRAMMAR_TEXT_MAX_LENGTH = 256

    LESSON_NAME_MAX_LENGTH = 64
    LESSON_DESCRIPTION_MAX_LENGTH = 256
    LESSON_BLOCK_TITLE_MAX_LENGTH = 64
    LESSON_BLOCK_CONTENT_MAX_LENGTH = 2048

    STUDY_GROUP_NAME_MAX_LENGTH = 64

    COMMENT_TEXT_MAX_LENGTH = 512

    ISSUE_TEXT_MAX_LENGTH = 1024
    ISSUE_TITLE_MAX_LENGTH = 64


class ComplaintReasonEnum:
    SPAM = 'Spam'
    OFFENSE = 'Offense'
    VIOLENCE = 'Violence'
    NON_ORIGINAL_CONTENT = 'Non-original'
    OBSCENE = 'Obscene'
    INCITEMENT = 'Incitement'
    OTHER = 'Other'

    complaint_reasons = (
        (SPAM, 'Spam distribution'),
        (OFFENSE, 'Insulting users'),
        (VIOLENCE, 'Demonstration of pornography or violence'),
        (NON_ORIGINAL_CONTENT, 'Publishing non-original content'),
        (OBSCENE, 'The use of obscene language'),
        (INCITEMENT, 'Incitement of hostility and hatred'),
        (OTHER, 'Other reason'),
    )

    max_length = 32


class FriendsRequestPermissionsEnum:
    FRIENDS_OF_FRIENDS = 'FOF'
    STUDY_GROUPS = 'SG'
    FOF_AND_STUDY_GROUPS = 'FOFSG'
    USERS_LIST = 'UL'
    ALL = 'A'
    NOONE = 'N'

    permissions_choices = (
        (FRIENDS_OF_FRIENDS, 'Friends of friends'),
        (STUDY_GROUPS, 'My study groups'),
        (FOF_AND_STUDY_GROUPS, 'My study groups and friends of friends'),
        (USERS_LIST, 'Users from list'),
        (ALL, 'All'),
        (NOONE, 'No one'),
    )

    max_length = 8


class FriendsNotificationsPermissionsEnum:
    ALL_FRIENDS = 'A'
    FRIENDS_LIST = 'FL'
    NOONE = 'N'

    permissions_choices = (
        (ALL_FRIENDS, 'All friends'),
        (FRIENDS_LIST, 'Friends from list'),
        (NOONE, 'No one'),
    )

    max_length = 2


class ChatUsageAnalysPermissionEnum:
    ALL_CHATS = 'A'
    EXCEPT_PRIVATE = 'EP'
    CHATS_LIST = 'CL'
    DISALLOW = 'D'

    permissions_choices = (
        (ALL_CHATS, 'All chats'),
        (EXCEPT_PRIVATE, 'All chats except private'),
        (CHATS_LIST, 'Chats from list'),
        (DISALLOW, 'No chats'),
    )

    max_length = 2


class CommonPermissionsEnum:
    FRIENDS = 'FR'
    FRIENDS_AND_FRIENDS_OF_FRIENDS = 'FFOF'
    STUDY_GROUPS = 'SG'
    FRIENDS_AND_STUDY_GROUPS = 'FS'
    USERS_LIST = 'LST'
    ALL = 'A'
    NOONE = 'N'

    permissions_choices = (
        (FRIENDS, 'Friends'),
        (FRIENDS_AND_FRIENDS_OF_FRIENDS, 'Friends and friends of friends'),
        (STUDY_GROUPS, 'My study groups'),
        (FRIENDS_AND_STUDY_GROUPS, 'My study groups and friends'),
        (USERS_LIST, 'Users from list'),
        (ALL, 'All'),
        (NOONE, 'No one'),
    )

    max_length = 8
