"""Exercises app models."""

from sqlalchemy import (
    Column,
    String,
    Integer,
    SmallInteger,
    Boolean,
    Text,
    Float,
    DateTime,
    ForeignKey,
    Table,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from core.base import Base
from core.mixins import SlugMixin
from core.constants import AccessLevelsEnum
from apps.exercises.constants import (
    ExercisesLengthLimits,
    TaskTypesEnum,
    ExercisesInputModeEnum,
    ExercisesAnswerEnum,
    TimeLimitModeEnum,
    TranslationsModeEnum,
    DefinitionsModeEnum,
)

# ---------------------------
# Association tables (many-to-many)
# names follow Django default pattern: <app>_<model>_<field>
# ---------------------------

# Exercise.hints_available
exercises_exercise_hints_available = Table(
    "exercises_exercise_hints_available",
    Base.metadata,
    Column(
        "exercise_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercise.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "hint_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_hint.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Exercise.hints (Hint.exercises backref created via relationship)
# ExerciseConfiguration.words_set <-> WordsSet
exercises_exerciseconfiguration_words_set = Table(
    "exercises_exerciseconfiguration_words_set",
    Base.metadata,
    Column(
        "exerciseconfiguration_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exerciseconfiguration.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "wordsset_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_wordsset.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# ExerciseConfiguration.words -> vocabulary.Word
exercises_exerciseconfiguration_words = Table(
    "exercises_exerciseconfiguration_words",
    Base.metadata,
    Column(
        "exerciseconfiguration_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exerciseconfiguration.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "word_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# ExerciseConfiguration.hints_available
exercises_exerciseconfiguration_hints_available = Table(
    "exercises_exerciseconfiguration_hints_available",
    Base.metadata,
    Column(
        "exerciseconfiguration_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exerciseconfiguration.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "hint_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_hint.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# ExerciseSessionTasksHistory -> many-to-many: right_answers_words/translations/definitions
exercises_exercisesessiontaskshistory_right_answers_words = Table(
    "exercises_exercisesessiontaskshistory_right_answers_words",
    Base.metadata,
    Column(
        "exercisesessiontaskshistory_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesessiontaskshistory.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "word_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
exercises_exercisesessiontaskshistory_right_answers_translations = Table(
    "exercises_exercisesessiontaskshistory_right_answers_translations",
    Base.metadata,
    Column(
        "exercisesessiontaskshistory_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesessiontaskshistory.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "translation_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_wordtranslation.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
exercises_exercisesessiontaskshistory_right_answers_definitions = Table(
    "exercises_exercisesessiontaskshistory_right_answers_definitions",
    Base.metadata,
    Column(
        "exercisesessiontaskshistory_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesessiontaskshistory.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "definition_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_definition.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# ExerciseSessionTasksHistory.hints_available / hints_used
exercises_exercisesessiontaskshistory_hints_available = Table(
    "exercises_exercisesessiontaskshistory_hints_available",
    Base.metadata,
    Column(
        "exercisesessiontaskshistory_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesessiontaskshistory.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "hint_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_hint.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
exercises_exercisesessiontaskshistory_hints_used = Table(
    "exercises_exercisesessiontaskshistory_hints_used",
    Base.metadata,
    Column(
        "exercisesessiontaskshistory_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesessiontaskshistory.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "hint_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_hint.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# WordsSet.words
exercises_wordsset_words = Table(
    "exercises_wordsset_words",
    Base.metadata,
    Column(
        "wordsset_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_wordsset.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "word_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# CustomExerciseConfiguration.gaps
exercises_customexerciseconfiguration_gaps = Table(
    "exercises_customexerciseconfiguration_gaps",
    Base.metadata,
    Column(
        "customexerciseconfiguration_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_customexerciseconfiguration.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "customgap_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_customgap.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# CustomGap.allowed_words
exercises_customgap_allowed_words = Table(
    "exercises_customgap_allowed_words",
    Base.metadata,
    Column(
        "customgap_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_customgap.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "word_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# ExercisesSet.words
exercises_exercisesset_words = Table(
    "exercises_exercisesset_words",
    Base.metadata,
    Column(
        "exerciseset_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesset.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "word_id",
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# ExercisesSet.exercises -> ExerciseConfiguration
exercises_exercisesset_exercises = Table(
    "exercises_exercisesset_exercises",
    Base.metadata,
    Column(
        "exerciseset_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesset.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "exerciseconfiguration_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exerciseconfiguration.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# ExercisesSet.custom_exercises -> CustomExerciseConfiguration
exercises_exercisesset_custom_exercises = Table(
    "exercises_exercisesset_custom_exercises",
    Base.metadata,
    Column(
        "exerciseset_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesset.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "customexerciseconfiguration_id",
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_customexerciseconfiguration.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# FavoriteExerciseSet is simple FK pair — no M2M table needed


# ---------------------------
# Models
# ---------------------------


class Exercise(Base, SlugMixin):
    """Упражнение."""

    # fields
    name_ru = Column(String(256), nullable=False)
    name_en = Column(String(256), nullable=False)
    description_ru = Column(String(4096), nullable=False)
    description_en = Column(String(4096), nullable=False)
    constraint_description_ru = Column(String(512), nullable=True)
    constraint_description_en = Column(String(512), nullable=True)
    icon = Column(String(1024), nullable=True)  # image path
    available = Column(Boolean, nullable=False, server_default="false")

    # FK (none here except M2M handled below)

    # Relationships (many-to-many)
    hints_available = relationship(
        "Hint",
        secondary=exercises_exercise_hints_available,
        backref="exercises",
        lazy="selectin",
    )

    __slug_source__ = ["name"]

    __table_args__ = (Index("ix_exercises_exercise_created", "created"),)

    def __repr__(self):
        return f"<Exercise(name={self.name})>"

    # NOTE: methods words_available / collections_available in Django rely on ORM QuerySet
    # In service layer you will implement equivalent queries using SQLAlchemy async sessions.


class Hint(Base):
    """Подсказка."""

    # fields
    name_ru = Column(String(32), nullable=False, unique=True)
    name_en = Column(String(32), nullable=False, unique=True)
    description_ru = Column(String(128), nullable=False)
    description_en = Column(String(128), nullable=False)
    code = Column(String(32), nullable=False, unique=True)
    variants_mode = Column(Boolean, nullable=False, server_default="false")
    free_input_mode = Column(Boolean, nullable=False, server_default="false")
    word_customization_content_needed = Column(String(64), nullable=True)

    __table_args__ = (Index("ix_exercises_hint_created", "created"),)

    def __repr__(self):
        return f"<Hint(name={self.name})>"


class ExerciseSessionHistory(
    Base,
):
    """История прохождения упражнения."""

    # fields
    words_amount = Column(SmallInteger, nullable=False)
    tasks_amount = Column(SmallInteger, nullable=False)
    corrects_amount = Column(SmallInteger, nullable=False, server_default="0")
    incorrects_amount = Column(SmallInteger, nullable=False, server_default="0")
    semi_corrects_amount = Column(SmallInteger, nullable=False, server_default="0")
    complete_time = Column(Float, nullable=True)

    # FK
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercise.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    user = relationship("User", backref="exercises_history", lazy="selectin")
    exercise = relationship("Exercise", backref="users_history", lazy="selectin")

    __table_args__ = (Index("ix_exercises_exercisesessionhistory_created", "created"),)

    def __repr__(self):
        return f"<ExerciseSessionHistory(user={self.user_id}, exercise={self.exercise_id})>"


class ExerciseSessionTasksHistory(Base):
    """История ответа на задание упражнения."""

    # fields
    task = Column(String(ExercisesLengthLimits.TASK_TEXT_MAX_LENGTH), nullable=False)
    task_type = Column(
        String(TaskTypesEnum.max_length),
        nullable=False,
        server_default=TaskTypesEnum.TEXT,
    )
    task_language = Column(String(8), nullable=True)
    task_index = Column(SmallInteger, nullable=False)
    answer = Column(
        String(ExercisesLengthLimits.ANSWER_TEXT_MAX_LENGTH), nullable=False
    )
    verdict = Column(String(ExercisesAnswerEnum.max_length), nullable=False)
    answers_list = Column(Text, nullable=True)
    verdicts_list = Column(Text, nullable=True)
    answer_time = Column(Float, nullable=True)
    answer_time_limit = Column(SmallInteger, nullable=True)
    image_width = Column(SmallInteger, nullable=True)
    image_height = Column(SmallInteger, nullable=True)

    # FK
    session_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesessionhistory.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_word_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_word.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_translation_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vocabulary_wordtranslation.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Relationships (FK)
    session = relationship("ExerciseSessionHistory", backref="details", lazy="selectin")
    task_word = relationship("Word", backref="exercises_history", lazy="selectin")
    task_translation = relationship(
        "WordTranslation", backref="exercises_history", lazy="selectin"
    )

    # Many-to-many relationships
    right_answers_words = relationship(
        "Word",
        secondary=exercises_exercisesessiontaskshistory_right_answers_words,
        backref="tasks_history",
        lazy="selectin",
    )
    right_answers_translations = relationship(
        "WordTranslation",
        secondary=exercises_exercisesessiontaskshistory_right_answers_translations,
        backref="tasks_history",
        lazy="selectin",
    )
    right_answers_definitions = relationship(
        "Definition",
        secondary=exercises_exercisesessiontaskshistory_right_answers_definitions,
        backref="tasks_history",
        lazy="selectin",
    )

    hints_available = relationship(
        "Hint",
        secondary=exercises_exercisesessiontaskshistory_hints_available,
        backref="sessions",
        lazy="selectin",
    )
    hints_used = relationship(
        "Hint",
        secondary=exercises_exercisesessiontaskshistory_hints_used,
        backref="history",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_exercises_exercisesessiontaskshistory_created_taskindex",
            "created",
            "task_index",
        ),
    )

    def __repr__(self):
        return f"<ExerciseSessionTasksHistory(session={self.session_id}, task_index={self.task_index})>"


class ExerciseConfiguration(Base):
    """Конфигурация упражнения."""

    # fields
    input_mode = Column(
        String(ExercisesInputModeEnum.max_length),
        nullable=False,
        server_default=ExercisesInputModeEnum.FREE_INPUT,
    )
    answer_time_limit = Column(SmallInteger, nullable=True)
    time_limit_mode = Column(
        String(TimeLimitModeEnum.max_length),
        nullable=False,
        server_default=TimeLimitModeEnum.ALL,
    )
    repetitions_amount = Column(SmallInteger, nullable=False, server_default="1")
    translations_mode = Column(
        String(TranslationsModeEnum.max_length),
        nullable=True,
        server_default=TranslationsModeEnum.FROM_LEARNING,
    )
    definitions_mode = Column(
        String(DefinitionsModeEnum.max_length),
        nullable=True,
        server_default=DefinitionsModeEnum.DEFINITION_BY_WORD,
    )
    is_default = Column(Boolean, nullable=False, server_default="false")
    hints_use_amount = Column(SmallInteger, nullable=True)

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercise.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship("User", backref="exercises_configurations", lazy="selectin")
    exercise = relationship("Exercise", backref="configurations", lazy="selectin")

    # Many-to-many relationships
    words_set = relationship(
        "WordsSet",
        secondary=exercises_exerciseconfiguration_words_set,
        backref="exercise_configurations",
        lazy="selectin",
    )
    words = relationship(
        "Word",
        secondary=exercises_exerciseconfiguration_words,
        backref="exercise_configurations",
        lazy="selectin",
    )
    hints_available = relationship(
        "Hint",
        secondary=exercises_exerciseconfiguration_hints_available,
        backref="exercise_configurations",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_exercises_exerciseconfiguration_created", "created"),)

    def __repr__(self):
        return f"<ExerciseConfiguration(author={self.author_id}, exercise={self.exercise_id})>"


class FavoriteExercise(Base):
    """Избранное упражнение."""

    # fields (none extra)
    # FK
    exercise_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercise.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    exercise = relationship("Exercise", backref="favorite_for", lazy="selectin")
    user = relationship("User", backref="favorite_exercises", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("exercise_id", "user_id", name="unique_favorite_exercise"),
        Index("ix_exercises_favoriteexercise_created", "created"),
    )

    def __repr__(self):
        return f"<FavoriteExercise(user={self.user_id}, exercise={self.exercise_id})>"


class WordsSet(Base, SlugMixin):
    """Набор слов."""

    # fields
    name = Column(
        String(ExercisesLengthLimits.WORDS_SET_NAME_MAX_LENGTH), nullable=False
    )
    last_exercise_date = Column(DateTime(timezone=True), nullable=True)

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercise.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship("User", backref="words_sets", lazy="selectin")
    exercise = relationship("Exercise", backref="words_sets", lazy="selectin")

    # Many-to-many
    words = relationship(
        "Word", secondary=exercises_wordsset_words, backref="sets", lazy="selectin"
    )

    __slug_source__ = ["name", "exercise__name", "author__username"]

    __table_args__ = (
        Index(
            "ix_exercises_wordsset_lastexercise_created",
            "last_exercise_date",
            "created",
        ),
        # functional unique on lower(name), exercise, author -> create in Alembic
    )

    def __repr__(self):
        return f"<WordsSet(name={self.name})>"


class CustomExerciseConfiguration(Base):
    """Конфигурация кастомного упражнения."""

    # fields
    task = Column(
        String(ExercisesLengthLimits.EXERCISE_TASK_MAX_LENGTH), nullable=False
    )
    content_text = Column(
        String(ExercisesLengthLimits.EXERCISE_TASK_CONTENT_MAX_LENGTH), nullable=True
    )
    content_image = Column(String(1024), nullable=True)
    correct_answers = Column(Text, nullable=True)
    answer_time_limit = Column(SmallInteger, nullable=True)
    variants = Column(Text, nullable=True)
    several_answers_allowed = Column(Boolean, nullable=False, server_default="false")

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship("User", backref="custom_exercises", lazy="selectin")

    # Many-to-many: gaps
    gaps = relationship(
        "CustomGap",
        secondary=exercises_customexerciseconfiguration_gaps,
        backref="custom_exercises",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_exercises_customexerciseconfiguration_created", "created"),
    )

    def __repr__(self):
        return f"<CustomExerciseConfiguration(task={self.task})>"


class CustomGap(Base):
    """Пропуск для заполнения в кастомном упражнении."""

    # fields
    pre_position = Column(Integer, nullable=False)
    order_position = Column(Integer, nullable=False)
    correct_answers = Column(Text, nullable=True)

    # Many-to-many
    allowed_words = relationship(
        "Word",
        secondary=exercises_customgap_allowed_words,
        backref="custom_exercises_gaps",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_exercises_customgap_created", "created"),)

    def __repr__(self):
        return f"<CustomGap(id={self.id})>"


class ExercisesSet(Base, SlugMixin):
    """Набор упражнений."""

    # fields
    title = Column(
        String(ExercisesLengthLimits.EXERCISES_SET_TITLE_MAX_LENGTH), nullable=False
    )
    run_access_level = Column(
        String(AccessLevelsEnum.max_length),
        nullable=False,
        server_default=AccessLevelsEnum.PUBLIC,
    )
    add_access_level = Column(
        String(AccessLevelsEnum.max_length),
        nullable=False,
        server_default=AccessLevelsEnum.PUBLIC,
    )
    views_amount = Column(Integer, nullable=False, server_default="0")

    # FK
    author_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    author = relationship("User", backref="exercises_sets", lazy="selectin")

    # Many-to-many
    words = relationship(
        "Word",
        secondary=exercises_exercisesset_words,
        backref="exercises_sets",
        lazy="selectin",
    )
    exercises = relationship(
        "ExerciseConfiguration",
        secondary=exercises_exercisesset_exercises,
        backref="exercises_sets",
        lazy="selectin",
    )
    custom_exercises = relationship(
        "CustomExerciseConfiguration",
        secondary=exercises_exercisesset_custom_exercises,
        backref="exercises_sets",
        lazy="selectin",
    )

    __slug_source__ = ["title", "author__username"]

    __table_args__ = (
        Index("ix_exercises_exercisesset_created_modified", "created", "modified"),
        # functional unique lower(title)+author -> create in Alembic
    )

    def __repr__(self):
        return f"<ExercisesSet(title={self.title})>"


class FavoriteExerciseSet(Base):
    """Избранный набор упражнений."""

    # fields none

    # FK
    exercises_set_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesset.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships (FK)
    exercises_set = relationship(
        "ExercisesSet", backref="favorite_for", lazy="selectin"
    )
    user = relationship("User", backref="favorite_exercises_sets", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "exercises_set_id", "user_id", name="unique_favorite_exercises_set"
        ),
        Index("ix_exercises_favoriteexerciseset_created", "created"),
    )

    def __repr__(self):
        return f"<FavoriteExerciseSet(user={self.user_id}, exercises_set={self.exercises_set_id})>"


class ExerciseSchedule(Base):
    """Расписание прохождения упражнений."""

    # fields
    scheduled_datetime = Column(DateTime(timezone=True), nullable=False)
    send_notification = Column(Boolean, nullable=False, server_default="true")

    # FK
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercise.id", ondelete="CASCADE"),
        nullable=True,
    )
    exercise_configuration_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exerciseconfiguration.id", ondelete="CASCADE"),
        nullable=True,
    )
    exercises_set_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercises_exercisesset.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Relationships (FK)
    user = relationship("User", backref="schedule", lazy="selectin")
    exercise = relationship("Exercise", backref="schedule", lazy="selectin")
    exercise_configuration = relationship(
        "ExerciseConfiguration", backref="schedule", lazy="selectin"
    )
    exercises_set = relationship("ExercisesSet", backref="schedule", lazy="selectin")

    __table_args__ = (
        Index(
            "ix_exercises_schedule_scheduled_created_modified",
            "scheduled_datetime",
            "created",
            "modified",
        ),
    )

    def __repr__(self):
        return f"<ExerciseSchedule(user={self.user_id}, scheduled={self.scheduled_datetime})>"
