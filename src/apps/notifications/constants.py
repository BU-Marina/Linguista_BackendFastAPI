"""Notifications app constants."""

from typing import List

APP_LABEL = "notifications"


class NotificationsLengthLimits:
    """Length limits constants."""

    NOTIFICATION_TEXT_MAX_LENGTH = 128
    NOTIFICATION_TYPE_MAX_LENGTH = 64


class NotificationTypesEnum:
    """Notification types choices."""

    # WORDS
    WORD_ACTIVITY_STATUS_CHANGE_TYPE = 'word_activity_status_change'
    WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING = 'word_activity_status_downgrade_warning'
    WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING_GROUP = (
        'word_activity_status_downgrade_warning_group'
    )

    # COLLECTIONS
    SUBSCRIBED_COLLECTION_UPDATE = 'subscribed_collection_update'
    NEW_SUGGESTED_WORDS = 'new_suggested_words'
    NEW_SUGGESTED_WORDS_GROUP = 'new_suggested_words_group'

    # USERS
    FRIEND_REQUEST_TYPE = 'friend_request'
    SUBSCRIBED_AUTHOR_UPDATE = 'subscribed_author_update'

    notification_types = (
        # WORDS
        (WORD_ACTIVITY_STATUS_CHANGE_TYPE, 'Word activity status changed notification'),
        (
            WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING,
            'Word activity status downgrade warning',
        ),
        (
            WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING_GROUP,
            'Group of word activity status downgrade warnings',
        ),
        # COLLECTIONS
        (
            SUBSCRIBED_COLLECTION_UPDATE,
            'New or updated words in collection user subscribed to',
        ),
        (NEW_SUGGESTED_WORDS, 'New suggested words in collection'),
        (NEW_SUGGESTED_WORDS_GROUP, 'Group of new suggested words notifications'),
        # USERS
        (FRIEND_REQUEST_TYPE, 'Request to add to friends'),
        (
            SUBSCRIBED_AUTHOR_UPDATE,
            'New or updated words from author user subscribed to',
        ),
    )

    system_notification_types = (WORD_ACTIVITY_STATUS_CHANGE_TYPE,)

    types_to_create_groups = (
        WORD_ACTIVITY_STATUS_DOWNGRADE_WARNING,
        NEW_SUGGESTED_WORDS,
    )

    types_to_update_data = (
        SUBSCRIBED_COLLECTION_UPDATE,
        SUBSCRIBED_AUTHOR_UPDATE,
    )

    @classmethod
    def get_data_fields_to_update(cls, notification_type: str) -> List[str]:
        """
        Returns list of notificatiom `extra_data` fields to update names based on notification_type.
        """
        match notification_type:
            case cls.SUBSCRIBED_COLLECTION_UPDATE:
                return [
                    'new_words',
                    'updated_words',
                ]

            case cls.SUBSCRIBED_AUTHOR_UPDATE:
                return [
                    'new_words',
                    'updated_words',
                    'new_collections',
                ]
