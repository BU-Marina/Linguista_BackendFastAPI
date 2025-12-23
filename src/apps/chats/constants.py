"""Chats app constants."""

APP_LABEL = "chats"

class ChatsLengthLimits:
    """Length limits constants."""

    CHAT_NAME_MAX_LENGTH = 32
    CHAT_DESCRIPTION_MAX_LENGTH = 256

    MESSAGE_TEXT_MAX_LENGTH = 512


class ChatTypesEnum:
    PRIVATE = 'P'
    GROUP = 'G'
    OPEN = 'O'

    chat_types = (
        (PRIVATE, 'Private chat'),
        (GROUP, 'Group chat'),
        (OPEN, 'Open group chat'),
    )

    max_length = 1
