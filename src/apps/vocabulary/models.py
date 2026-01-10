"""Vocabulary app models."""

from sqlalchemy import (
    Column,
    String,
    SmallInteger,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    Table,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, declared_attr

from core.base import Base
from core.mixins import SlugMixin, PublicAccessMixin
from core.constants import ActivityStatusEnum, RequestStatusEnum, CoreLengthLimits

from .constants import VocabularyLengthLimits

# -------------------------
# Association tables (for plain M2M without through)
# -------------------------
# Word.types (WordType)
vocabulary_word_types = Table(
    "vocabulary_word_types",
    Base.metadata,
    Column(
        "word_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "wordtype_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_wordtype.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Word.tags -> core.Tag
vocabulary_word_tags = Table(
    "vocabulary_word_tags",
    Base.metadata,
    Column(
        "word_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        PG_UUID(as_uuid=True),
        ForeignKey("core_tag.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Collection.tags -> core.Tag
vocabulary_collection_tags = Table(
    "vocabulary_collection_tags",
    Base.metadata,
    Column(
        "collection_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        PG_UUID(as_uuid=True),
        ForeignKey("core_tag.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Collection.coauthors -> users_user
vocabulary_collection_coauthors = Table(
    "vocabulary_collection_coauthors",
    Base.metadata,
    Column(
        "collection_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Collection.subscribers (through CollectionSubscription model — handled as model, not table here)

vocabulary_word_share_with = Table(
    "vocabulary_word_share_with",
    Base.metadata,
    Column(
        "word_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    ),
    UniqueConstraint("word_id", "user_id", name="uniq_word_share_with"),
)

vocabulary_collection_share_with = Table(
    "vocabulary_collection_share_with",
    Base.metadata,
    Column(
        "collection_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    ),
    UniqueConstraint("collection_id", "user_id", name="uniq_collection_share_with"),
)

# -------------------------
# Models
# -------------------------


class Word(Base, SlugMixin, PublicAccessMixin):
    """Слово или фраза."""

    # fields
    text = Column(String(VocabularyLengthLimits.MAX_WORD_LENGTH), nullable=False)
    activity_status = Column(
        String(ActivityStatusEnum.max_length),
        nullable=False,
        server_default=ActivityStatusEnum.INACTIVE,
    )
    activity_progress = Column(SmallInteger, nullable=False, server_default="0")
    is_problematic = Column(Boolean, nullable=False, server_default="false")
    is_trophie = Column(Boolean, nullable=False, server_default="false")
    note = Column(String(VocabularyLengthLimits.MAX_NOTE_LENGTH), nullable=True)
    last_exercise_date = Column(DateTime(timezone=True), nullable=True)
    is_premium = Column(Boolean, nullable=False, server_default="false")
    allow_comments = Column(Boolean, nullable=False, server_default="true")

    # FK
    language_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("languages_language.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    language = relationship("Language", backref="words", lazy="selectin")
    source_word = relationship(
        "Word", remote_side="Word.id", backref="borrowings", lazy="selectin"
    )
    author = relationship("User", backref="words", lazy="selectin")

    # Many-to-many (some via explicit through-models below)
    types = relationship(
        "WordType", secondary=vocabulary_word_types, backref="words", lazy="selectin"
    )
    tags = relationship(
        "Tag", secondary=vocabulary_word_tags, backref="words", lazy="selectin"
    )
    share_with = relationship(
        "User",
        secondary=vocabulary_word_share_with,
        backref="shared_words",
        lazy="selectin",
    )

    __slug_source__ = ["text", "author__username", "language__isocode"]

    __table_args__ = (
        Index("ix_vocabulary_word_created_modified", "created", "modified"),
        # Note: Django had UniqueConstraint('text', 'author', 'language') — case-insensitive in Django.
        # We will create functional unique index (lower(...)) in Alembic migration to match original behavior.
    )

    def __repr__(self):
        return f"<Word(text={self.text}, author_id={self.author_id})>"


class WordActivityHistory(Base):
    """История изменений статусов активности слов."""

    # fields
    previous_activity_progress = Column(SmallInteger, nullable=True)
    new_activity_progress = Column(SmallInteger, nullable=True)
    upgrade = Column(Boolean, nullable=False, server_default="true")

    # FK
    session_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesessionhistory.id", ondelete="CASCADE"),
        nullable=True,
    )
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )

    # fields with choices stored as String
    previous_activity_status = Column(
        String(ActivityStatusEnum.max_length),
        nullable=False,
        server_default=ActivityStatusEnum.INACTIVE,
    )
    new_activity_status = Column(
        String(ActivityStatusEnum.max_length),
        nullable=False,
        server_default=ActivityStatusEnum.ACTIVE,
    )

    # Relationships (FK)
    session = relationship(
        "ExerciseSessionHistory", backref="words_activity_changes", lazy="selectin"
    )
    word = relationship("Word", backref="activity_history", lazy="selectin")

    __table_args__ = (Index("ix_vocabulary_wordactivityhistory_created", "created"),)

    def __repr__(self):
        return f"<WordActivityHistory(word_id={self.word_id})>"


class WordType(Base, SlugMixin):
    """Часть речи слова или фразы."""

    # fields
    name_ru = Column(String(64), nullable=False, unique=True)
    name_en = Column(String(64), nullable=False, unique=True)

    __slug_source__ = ["name"]

    __table_args__ = (Index("ix_vocabulary_wordtype_created", "created"),)

    def __repr__(self):
        return f"<WordType(name={self.name})>"


class FormGroup(Base, SlugMixin):
    """Группа форм."""

    # fields
    name = Column(
        String(VocabularyLengthLimits.MAX_FORMSGROUP_NAME_LENGTH), nullable=False
    )
    color = Column(String(7), nullable=True)
    translation = Column(
        String(VocabularyLengthLimits.MAX_FORMSGROUP_TRANSLATION_LENGTH), nullable=True
    )

    # FK
    language_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("languages_language.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    language = relationship("Language", backref="form_groups", lazy="selectin")
    author = relationship("User", backref="form_groups", lazy="selectin")

    __slug_source__ = ["name", "author__username"]

    __table_args__ = (
        Index("ix_vocabulary_formgroup_created_modified", "created", "modified"),
        # functional unique lower(name)+author -> create in Alembic
    )

    def __repr__(self):
        return f"<FormGroup(name={self.name})>"


class WordTranslation(Base, SlugMixin):
    """Перевод слова или фразы."""

    # fields
    text = Column(String(VocabularyLengthLimits.MAX_TRANSLATION_LENGTH), nullable=False)

    # FK
    language_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("languages_language.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    language = relationship("Language", backref="word_translations", lazy="selectin")
    author = relationship("User", backref="word_translations", lazy="selectin")

    __slug_source__ = ["text", "author__username", "language__name"]

    __table_args__ = (
        Index("ix_vocabulary_wordtranslation_created_modified", "created", "modified"),
        # functional unique lower(text)+author+language -> create in Alembic
    )

    def __repr__(self):
        return f"<WordTranslation(text={self.text})>"


class Definition(Base, SlugMixin):
    """Определение."""

    # fields
    text = Column(String(VocabularyLengthLimits.MAX_DEFINITION_LENGTH), nullable=False)
    translation = Column(
        String(VocabularyLengthLimits.MAX_DEFINITION_LENGTH), nullable=True
    )

    # FK
    language_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("languages_language.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    language = relationship("Language", backref="definitions", lazy="selectin")
    author = relationship("User", backref="definitions", lazy="selectin")

    __slug_source__ = ["text", "author__username"]

    __table_args__ = (
        Index("ix_vocabulary_definition_created_modified", "created", "modified"),
        # functional unique lower(text)+author -> create in Alembic
    )

    def __repr__(self):
        return f"<Definition(text={self.text})>"


class UsageExample(Base, SlugMixin):
    """Пример использования."""

    # fields
    text = Column(String(VocabularyLengthLimits.MAX_EXAMPLE_LENGTH), nullable=False)
    translation = Column(
        String(VocabularyLengthLimits.MAX_EXAMPLE_LENGTH), nullable=True
    )
    source = Column(String(3), nullable=False, server_default="OTH")
    source_name = Column(
        String(VocabularyLengthLimits.MAX_EXAMPLE_SOURCE_LENGTH), nullable=True
    )
    source_url = Column(
        String(VocabularyLengthLimits.MAX_EXAMPLE_SOURCE_LINK_LENGTH), nullable=True
    )

    # FK
    language_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("languages_language.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    language = relationship("Language", backref="examples", lazy="selectin")
    author = relationship("User", backref="examples", lazy="selectin")

    __slug_source__ = ["text", "author__username"]

    __table_args__ = (
        Index("ix_vocabulary_usageexample_created_modified", "created", "modified"),
        # functional unique lower(text)+author -> create in Alembic
    )

    def __repr__(self):
        return f"<UsageExample(text={self.text})>"


class ImageAssociation(Base):
    """Картинка-ассоциация."""

    # fields
    image_url = Column(String(1024), nullable=True)
    width = Column(SmallInteger, nullable=True)
    height = Column(SmallInteger, nullable=True)
    num = Column(SmallInteger, nullable=True)

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship("User", backref="image_associations", lazy="selectin")

    __table_args__ = (
        Index("ix_vocabulary_imageassociation_created_modified", "created", "modified"),
    )

    def __repr__(self):
        return f"<ImageAssociation(id={self.id})>"


class QuoteAssociation(Base):
    # fields
    text = Column(String(VocabularyLengthLimits.MAX_QUOTE_TEXT_LENGTH), nullable=False)
    quote_author = Column(
        String(VocabularyLengthLimits.MAX_QUOTE_AUTHOR_LENGTH), nullable=True
    )

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship("User", backref="quote_associations", lazy="selectin")

    __table_args__ = (
        Index("ix_vocabulary_quoteassociation_created_modified", "created", "modified"),
    )

    def __repr__(self):
        return f"<QuoteAssociation(text={self.text})>"


class Collection(Base, SlugMixin, PublicAccessMixin):
    """Коллекция."""

    # fields
    title = Column(
        String(VocabularyLengthLimits.MAX_COLLECTION_TITLE_LENGTH), nullable=False
    )
    description = Column(
        String(VocabularyLengthLimits.MAX_COLLECTION_DESCRIPTION_LENGTH), nullable=True
    )
    allow_comments = Column(Boolean, nullable=False, server_default="true")
    allow_suggestions = Column(Boolean, nullable=False, server_default="true")
    allow_suggestions_notifications = Column(
        Boolean, nullable=False, server_default="true"
    )
    is_premium = Column(Boolean, nullable=False, server_default="false")

    # FK
    source_collection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    source_collection = relationship(
        "Collection", remote_side="Collection.id", backref="borrowings", lazy="selectin"
    )
    author = relationship("User", backref="collections", lazy="selectin")

    # Many-to-many via through models:
    # - words via WordsInCollections model
    # - tags via vocabulary_collection_tags
    # - coauthors via vocabulary_collection_coauthors
    tags = relationship(
        "Tag",
        secondary=vocabulary_collection_tags,
        backref="collections",
        lazy="selectin",
    )
    coauthors = relationship(
        "User",
        secondary=vocabulary_collection_coauthors,
        backref="joint_collections",
        lazy="selectin",
    )
    share_with = relationship(
        "User",
        secondary=vocabulary_collection_share_with,
        backref="shared_collections",
        lazy="selectin",
    )

    __slug_source__ = ["title", "author__username"]

    __table_args__ = (
        Index("ix_vocabulary_collection_created_modified", "created", "modified"),
        # functional unique lower(title)+author -> create in Alembic
    )

    def __repr__(self):
        return f"<Collection(title={self.title})>"


class CollectionSubscription(Base):
    """Промежуточная модель подписки на коллекцию."""

    # fields
    enable_notifications = Column(Boolean, nullable=False, server_default="true")
    new_words = Column(Text, nullable=True)
    updated_words = Column(Text, nullable=True)

    # FK
    subscriber_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    collection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    subscriber = relationship(
        "User", backref="collections_subscriptions_detail", lazy="selectin"
    )
    collection = relationship(
        "Collection", backref="subscribers_detail", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint(
            "subscriber_id", "collection_id", name="unique_collection_subscription"
        ),
        Index("ix_vocabulary_collectionsubscription_created", "created"),
    )

    def __repr__(self):
        return f"<CollectionSubscription(subscriber={self.subscriber_id}, collection={self.collection_id})>"


# -------------------------
# Through / intermediary models
# -------------------------


class WordsFormGroups(Base):
    """Промежуточная модель связи слова и группы форм."""

    # fields none extra

    # FK
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )
    forms_group_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_formgroup.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships (FK)
    word = relationship("Word", backref="words_form_groups", lazy="selectin")
    forms_group = relationship(
        "FormGroup", backref="words_form_groups", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("word_id", "forms_group_id", name="unique_word_forms_group"),
    )


class WordTranslations(Base):
    """Промежуточная модель связи переводов и слов."""

    translation_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_wordtranslation.id", ondelete="CASCADE"),
        nullable=False,
    )
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )

    translation = relationship(
        "WordTranslation", backref="wordtranslations", lazy="selectin"
    )
    word = relationship("Word", backref="wordtranslations", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("word_id", "translation_id", name="unique_word_translation"),
    )


class WordDefinitions(Base):
    """Промежуточная модель связи определений и слов."""

    definition_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_definition.id", ondelete="CASCADE"),
        nullable=False,
    )
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )

    definition = relationship("Definition", backref="worddefinitions", lazy="selectin")
    word = relationship("Word", backref="worddefinitions", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("word_id", "definition_id", name="unique_word_definition"),
    )


class WordUsageExamples(Base):
    """Промежуточная модель связи примеров и слов."""

    example_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_usageexample.id", ondelete="CASCADE"),
        nullable=False,
    )
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )

    example = relationship("UsageExample", backref="wordusageexamples", lazy="selectin")
    word = relationship("Word", backref="wordusageexamples", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("word_id", "example_id", name="unique_word_example"),
    )


class WordImageAssociations(Base):
    """Промежуточная модель связи картинок-ассоциаций и слов."""

    image_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_imageassociation.id", ondelete="CASCADE"),
        nullable=False,
    )
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )

    image = relationship(
        "ImageAssociation", backref="wordimageassociations", lazy="selectin"
    )
    word = relationship("Word", backref="wordimageassociations", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("word_id", "image_id", name="unique_word_image"),
    )


class WordQuoteAssociations(Base):
    quote_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_quoteassociation.id", ondelete="CASCADE"),
        nullable=False,
    )
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )

    quote = relationship(
        "QuoteAssociation", backref="wordquoteassociations", lazy="selectin"
    )
    word = relationship("Word", backref="wordquoteassociations", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("word_id", "quote_id", name="unique_word_quote"),
    )


class WordsInCollections(Base):
    """Промежуточная модель слов в коллекциях."""

    collection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="CASCADE"),
        nullable=False,
    )
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )

    collection = relationship(
        "Collection", backref="words_in_collections", lazy="selectin"
    )
    word = relationship("Word", backref="words_in_collections", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("word_id", "collection_id", name="unique_word_in_collection"),
    )


class WordsSuggestedToCollections(Base):
    """Промежуточная модель предложенных слов в коллекциях."""

    # fields
    status = Column(
        String(RequestStatusEnum.max_length),
        nullable=False,
        server_default=RequestStatusEnum.PENDING,
    )

    # FK
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )
    collection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    word = relationship("Word", backref="suggestions", lazy="selectin")
    collection = relationship("Collection", backref="suggestions", lazy="selectin")
    user = relationship("User", backref="words_suggested", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "word_id", "collection_id", "user_id", name="unique_suggested_word"
        ),
    )


# -------------------------
# Self-related models (synonyms/antonyms/forms/similar/derivative)
# -------------------------
class WordSelfRelationBase:
    """Промежуточная модель связи слово х слово."""

    @declared_attr
    def from_word_id(cls):
        return Column(
            PG_UUID(as_uuid=True),
            ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
            nullable=False,
        )

    @declared_attr
    def to_word_id(cls):
        return Column(
            PG_UUID(as_uuid=True),
            ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
            nullable=False,
        )

    @declared_attr
    def from_word(cls):
        return relationship(
            "Word",
            foreign_keys=[cls.from_word_id],
            backref=f"{cls.__name__.lower()}_from_words",
            lazy="selectin",
        )

    @declared_attr
    def to_word(cls):
        return relationship(
            "Word",
            foreign_keys=[cls.to_word_id],
            backref=f"{cls.__name__.lower()}_to_words",
            lazy="selectin",
        )

    @declared_attr
    def __table_args__(cls):
        # даём уникальные имена constraint'ам, чтобы они не конфликтовали между разными классами
        return (
            UniqueConstraint(
                "from_word_id",
                "to_word_id",
                name=f"unique_words_pair_{cls.__name__.lower()}",
            ),
            CheckConstraint(
                "from_word_id <> to_word_id",
                name=f"{cls.__name__.lower()}_not_same_word",
            ),
        )


class Synonym(Base, WordSelfRelationBase):
    """Синоним."""

    # inherits WordSelfRelationBase-like fields
    note = Column(String(VocabularyLengthLimits.MAX_NOTE_LENGTH), nullable=True)


class Antonym(Base, WordSelfRelationBase):
    """Антоним."""

    note = Column(String(VocabularyLengthLimits.MAX_NOTE_LENGTH), nullable=True)


class Form(Base, WordSelfRelationBase):
    """Форма."""


class Derivative(Base, WordSelfRelationBase):
    """Производное."""


class Similar(Base, WordSelfRelationBase):
    """Похожее."""


# -------------------------
# Favorites, Views, Approves, PremiumRequest, Comments
# -------------------------
class FavoriteWord(Base):
    """Избранное слово."""

    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    word = relationship("Word", backref="favorite_for", lazy="selectin")
    user = relationship("User", backref="favorite_words", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("word_id", "user_id", name="unique_user_favorite_word"),
    )


class FavoriteCollection(Base):
    """Избранная коллекция."""

    collection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    collection = relationship("Collection", backref="favorite_for", lazy="selectin")
    user = relationship("User", backref="favorite_collections", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "collection_id", "user_id", name="unique_user_favorite_collection"
        ),
    )


class ViewWord(Base):
    """Просмотр слова. Для статистики."""

    view_datetime = Column(DateTime(timezone=True), nullable=True)

    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    word = relationship("Word", backref="views", lazy="selectin")
    user = relationship("User", backref="word_views", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("word_id", "user_id", name="unique_word_view"),
        Index("ix_vocabulary_viewword_viewdatetime", "view_datetime"),
    )


class ViewCollection(Base):
    """Просмотр коллекции. Для статистики."""

    view_datetime = Column(DateTime(timezone=True), nullable=True)

    collection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    collection = relationship("Collection", backref="views", lazy="selectin")
    user = relationship("User", backref="collection_views", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("collection_id", "user_id", name="unique_collection_view"),
        Index("ix_vocabulary_viewcollection_viewdatetime", "view_datetime"),
    )


class WordApprove(Base):
    """Одобрение слова."""

    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    word = relationship("Word", backref="approves", lazy="selectin")
    user = relationship("User", backref="approves", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("word_id", "user_id", name="unique_word_approve"),
    )


class PremiumRequest(Base):
    """Запрос на добавление в премиум-контент."""

    # fields
    review = Column(String(CoreLengthLimits.REVIEW_TEXT_MAX_LENGTH), nullable=True)
    request_status = Column(
        String(RequestStatusEnum.max_length),
        nullable=False,
        server_default=RequestStatusEnum.PENDING,
    )

    # FK (one-to-one semantics in Django -> modeled as unique FK here)
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    collection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    word = relationship("Word", backref="premium_requests", lazy="selectin")
    collection = relationship("Collection", backref="premium_requests", lazy="selectin")
    author = relationship("User", backref="premium_requests", lazy="selectin")


# -------------------------
# Comment models (simplified)
# Note: original CommentModel is abstract and contains answers M2M etc.
# For now implement Comment classes with essential fields + likes/dislikes as M2M association tables.
# -------------------------
vocabulary_collectioncomment_likes = Table(
    "vocabulary_collectioncomment_likes",
    Base.metadata,
    Column(
        "collectioncomment_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collectioncomment.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

vocabulary_collectioncomment_dislikes = Table(
    "vocabulary_collectioncomment_dislikes",
    Base.metadata,
    Column(
        "collectioncomment_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collectioncomment.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

vocabulary_wordcomment_likes = Table(
    "vocabulary_wordcomment_likes",
    Base.metadata,
    Column(
        "wordcomment_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_wordcomment.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

vocabulary_wordcomment_dislikes = Table(
    "vocabulary_wordcomment_dislikes",
    Base.metadata,
    Column(
        "wordcomment_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_wordcomment.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# association tables для ответа (answers -> self M2M)
vocabulary_collectioncomment_answers = Table(
    "vocabulary_collectioncomment_answers",
    Base.metadata,
    Column(
        "collectioncomment_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collectioncomment.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "answer_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collectioncomment.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

vocabulary_wordcomment_answers = Table(
    "vocabulary_wordcomment_answers",
    Base.metadata,
    Column(
        "wordcomment_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_wordcomment.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "answer_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_wordcomment.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class CollectionComment(Base):
    """Комментарий к коллекции."""

    # fields (inherited comment model fields: text, author_liked, text_modified) — добавляем явно
    text = Column(Text, nullable=False)
    author_liked = Column(Boolean, nullable=False, server_default="false")
    text_modified = Column(Boolean, nullable=False, server_default="false")

    # FK
    collection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_collection.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    collection = relationship("Collection", backref="comments", lazy="selectin")
    author = relationship("User", backref="collection_comments", lazy="selectin")

    # M2M relationships (likes/dislikes/answers)
    likes = relationship(
        "User",
        secondary=vocabulary_collectioncomment_likes,
        backref="collection_comments_liked",
        lazy="selectin",
    )
    dislikes = relationship(
        "User",
        secondary=vocabulary_collectioncomment_dislikes,
        backref="collection_comments_disliked",
        lazy="selectin",
    )
    answers = relationship(
        "CollectionComment",
        secondary=vocabulary_collectioncomment_answers,
        primaryjoin="CollectionComment.id==vocabulary_collectioncomment_answers.c.collectioncomment_id",
        secondaryjoin="CollectionComment.id==vocabulary_collectioncomment_answers.c.answer_id",
        backref="answer_for",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_vocabulary_collectioncomment_created", "created"),)

    def __repr__(self):
        return f"<CollectionComment(id={self.id}, collection_id={self.collection_id})>"


class WordComment(Base):
    """Комментарий к слову."""

    # fields
    text = Column(Text, nullable=False)
    author_liked = Column(Boolean, nullable=False, server_default="false")
    text_modified = Column(Boolean, nullable=False, server_default="false")

    # FK
    word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    word = relationship("Word", backref="comments", lazy="selectin")
    author = relationship("User", backref="word_comments", lazy="selectin")

    # M2M relationships (likes/dislikes/answers)
    likes = relationship(
        "User",
        secondary=vocabulary_wordcomment_likes,
        backref="word_comments_liked",
        lazy="selectin",
    )
    dislikes = relationship(
        "User",
        secondary=vocabulary_wordcomment_dislikes,
        backref="word_comments_disliked",
        lazy="selectin",
    )
    answers = relationship(
        "WordComment",
        secondary=vocabulary_wordcomment_answers,
        primaryjoin="WordComment.id==vocabulary_wordcomment_answers.c.wordcomment_id",
        secondaryjoin="WordComment.id==vocabulary_wordcomment_answers.c.answer_id",
        backref="answer_for",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_vocabulary_wordcomment_created", "created"),)

    def __repr__(self):
        return f"<WordComment(id={self.id}, word_id={self.word_id})>"
