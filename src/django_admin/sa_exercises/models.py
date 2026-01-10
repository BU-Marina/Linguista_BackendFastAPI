"""..."""

from __future__ import annotations

from django.db import models

from sa_core.mixins import SaStampedModel
from sa_vocabulary.models import (
    SaWord,
    SaWordTranslation,
    SaDefinition,
)
from sa_users.models import SaUser


# -----------------------
# Hint
# -----------------------


class SaHint(SaStampedModel):
    name_ru = models.CharField(max_length=32, unique=True)
    name_en = models.CharField(max_length=32, unique=True)
    description_ru = models.CharField(max_length=128)
    description_en = models.CharField(max_length=128)

    code = models.CharField(max_length=32, unique=True)

    variants_mode = models.BooleanField(default=False)
    free_input_mode = models.BooleanField(default=False)

    word_customization_content_needed = models.CharField(
        max_length=64, null=True, blank=True
    )

    class Meta:
        managed = False
        db_table = "exercises_hint"

    def __str__(self) -> str:
        return self.code


# -----------------------
# Exercise
# -----------------------


class SaExercise(SaStampedModel):
    name_ru = models.CharField(max_length=256)
    name_en = models.CharField(max_length=256)

    description_ru = models.CharField(max_length=4096)
    description_en = models.CharField(max_length=4096)

    constraint_description_ru = models.CharField(max_length=512, null=True, blank=True)
    constraint_description_en = models.CharField(max_length=512, null=True, blank=True)

    icon = models.CharField(max_length=1024, null=True, blank=True)
    available = models.BooleanField(default=False)

    # M2M: hints_available (secondary=exercises_exercise_hints_available)
    hints_available = models.ManyToManyField(
        SaHint,
        through="SaExerciseHintsAvailable",
        related_name="exercises",
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "exercises_exercise"

    def __str__(self) -> str:
        # в SQLA был self.name (property/fallback), тут просто en/ru
        return self.name_en or self.name_ru or str(self.id)


class SaExerciseHintsAvailable(models.Model):
    exercise = models.ForeignKey(
        SaExercise,
        on_delete=models.DO_NOTHING,
        db_column="exercise_id",
        related_name="+",
    )
    hint = models.ForeignKey(
        SaHint, on_delete=models.DO_NOTHING, db_column="hint_id", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "exercises_exercise_hints_available"
        constraints = [
            models.UniqueConstraint(
                fields=["exercise", "hint"], name="uniq_exercise_hint_avail"
            ),
        ]


# -----------------------
# ExerciseSessionHistory
# -----------------------


class SaExerciseSessionHistory(SaStampedModel):
    words_amount = models.SmallIntegerField()
    tasks_amount = models.SmallIntegerField()
    corrects_amount = models.SmallIntegerField(default=0)
    incorrects_amount = models.SmallIntegerField(default=0)
    semi_corrects_amount = models.SmallIntegerField(default=0)

    complete_time = models.FloatField(null=True, blank=True)

    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="user_id",
        related_name="exercises_history",
    )
    exercise = models.ForeignKey(
        SaExercise,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="exercise_id",
        related_name="users_history",
    )

    class Meta:
        managed = False
        db_table = "exercises_exercisesessionhistory"

    def __str__(self) -> str:
        return f"{self.user_id} / {self.exercise_id} / {self.created}"


# -----------------------
# ExerciseSessionTasksHistory
# -----------------------


class SaExerciseSessionTasksHistory(SaStampedModel):
    # max_length'и зависят от констант ExercisesLengthLimits/Enum.max_length
    task = models.CharField(
        max_length=2048
    )  # TODO: ExercisesLengthLimits.TASK_TEXT_MAX_LENGTH
    task_type = models.CharField(
        max_length=32, default="TEXT"
    )  # TODO: TaskTypesEnum.max_length
    task_language = models.CharField(max_length=8, null=True, blank=True)
    task_index = models.SmallIntegerField()

    answer = models.CharField(
        max_length=2048
    )  # TODO: ExercisesLengthLimits.ANSWER_TEXT_MAX_LENGTH
    verdict = models.CharField(max_length=32)  # TODO: ExercisesAnswerEnum.max_length

    answers_list = models.TextField(null=True, blank=True)
    verdicts_list = models.TextField(null=True, blank=True)

    answer_time = models.FloatField(null=True, blank=True)
    answer_time_limit = models.SmallIntegerField(null=True, blank=True)

    image_width = models.SmallIntegerField(null=True, blank=True)
    image_height = models.SmallIntegerField(null=True, blank=True)

    session = models.ForeignKey(
        SaExerciseSessionHistory,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="session_id",
        related_name="details",
    )
    task_word = models.ForeignKey(
        SaWord,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="task_word_id",
        related_name="exercises_history",
    )
    task_translation = models.ForeignKey(
        SaWordTranslation,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column="task_translation_id",
        null=True,
        blank=True,
        related_name="exercises_history",
    )

    # M2M: right answers
    right_answers_words = models.ManyToManyField(
        SaWord,
        through="SaTasksHistoryRightAnswersWords",
        related_name="tasks_history",
        blank=True,
    )
    right_answers_translations = models.ManyToManyField(
        SaWordTranslation,
        through="SaTasksHistoryRightAnswersTranslations",
        related_name="tasks_history",
        blank=True,
    )
    right_answers_definitions = models.ManyToManyField(
        SaDefinition,
        through="SaTasksHistoryRightAnswersDefinitions",
        related_name="tasks_history",
        blank=True,
    )

    # M2M: hints
    hints_available = models.ManyToManyField(
        SaHint,
        through="SaTasksHistoryHintsAvailable",
        related_name="sessions",
        blank=True,
    )
    hints_used = models.ManyToManyField(
        SaHint,
        through="SaTasksHistoryHintsUsed",
        related_name="history",
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "exercises_exercisesessiontaskshistory"

    def __str__(self) -> str:
        return f"{self.session_id} #{self.task_index}"


class SaTasksHistoryRightAnswersWords(models.Model):
    task = models.ForeignKey(
        SaExerciseSessionTasksHistory,
        on_delete=models.DO_NOTHING,
        db_column="exercisesessiontaskshistory_id",
        related_name="+",
    )
    word = models.ForeignKey(
        SaWord, on_delete=models.DO_NOTHING, db_column="word_id", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "exercises_exercisesessiontaskshistory_right_answers_words"
        constraints = [
            models.UniqueConstraint(
                fields=["task", "word"], name="uniq_tsks_right_word"
            ),
        ]


class SaTasksHistoryRightAnswersTranslations(models.Model):
    task = models.ForeignKey(
        SaExerciseSessionTasksHistory,
        on_delete=models.DO_NOTHING,
        db_column="exercisesessiontaskshistory_id",
        related_name="+",
    )
    translation = models.ForeignKey(
        SaWordTranslation,
        on_delete=models.DO_NOTHING,
        db_column="wordtranslation_id",
        related_name="+",
    )

    class Meta:
        managed = False
        db_table = "exercises_exercisesessiontaskshistory_right_answers_translations"
        constraints = [
            models.UniqueConstraint(
                fields=["task", "translation"], name="uniq_tsks_right_tr"
            ),
        ]


class SaTasksHistoryRightAnswersDefinitions(models.Model):
    task = models.ForeignKey(
        SaExerciseSessionTasksHistory,
        on_delete=models.DO_NOTHING,
        db_column="exercisesessiontaskshistory_id",
        related_name="+",
    )
    definition = models.ForeignKey(
        SaDefinition,
        on_delete=models.DO_NOTHING,
        db_column="definition_id",
        related_name="+",
    )

    class Meta:
        managed = False
        db_table = "exercises_exercisesessiontaskshistory_right_answers_definitions"
        constraints = [
            models.UniqueConstraint(
                fields=["task", "definition"], name="uniq_tsks_right_def"
            ),
        ]


class SaTasksHistoryHintsAvailable(models.Model):
    task = models.ForeignKey(
        SaExerciseSessionTasksHistory,
        on_delete=models.DO_NOTHING,
        db_column="exercisesessiontaskshistory_id",
        related_name="+",
    )
    hint = models.ForeignKey(
        SaHint, on_delete=models.DO_NOTHING, db_column="hint_id", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "exercises_exercisesessiontaskshistory_hints_available"
        constraints = [
            models.UniqueConstraint(fields=["task", "hint"], name="uniq_tsks_hint_av"),
        ]


class SaTasksHistoryHintsUsed(models.Model):
    task = models.ForeignKey(
        SaExerciseSessionTasksHistory,
        on_delete=models.DO_NOTHING,
        db_column="exercisesessiontaskshistory_id",
        related_name="+",
    )
    hint = models.ForeignKey(
        SaHint, on_delete=models.DO_NOTHING, db_column="hint_id", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "exercises_exercisesessiontaskshistory_hints_used"
        constraints = [
            models.UniqueConstraint(
                fields=["task", "hint"], name="uniq_tsks_hint_used"
            ),
        ]


# -----------------------
# ExerciseConfiguration
# -----------------------


class SaWordsSet(SaStampedModel):
    """
    WordsSet объявляю раньше, потому что на него ссылается ExerciseConfiguration.words_set.
    """

    name = models.CharField(
        max_length=256
    )  # TODO: ExercisesLengthLimits.WORDS_SET_NAME_MAX_LENGTH
    last_exercise_date = models.DateTimeField(null=True, blank=True)

    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column="author_id",
        related_name="words_sets",
    )
    exercise = models.ForeignKey(
        SaExercise,
        on_delete=models.DO_NOTHING,
        db_column="exercise_id",
        related_name="words_sets",
    )

    words = models.ManyToManyField(
        SaWord,
        through="SaWordsSetWords",
        related_name="sets",
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "exercises_wordsset"

    def __str__(self) -> str:
        return self.name


class SaWordsSetWords(models.Model):
    words_set = models.ForeignKey(
        SaWordsSet,
        on_delete=models.DO_NOTHING,
        db_column="wordsset_id",
        related_name="+",
    )
    word = models.ForeignKey(
        SaWord, on_delete=models.DO_NOTHING, db_column="word_id", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "exercises_wordsset_words"
        constraints = [
            models.UniqueConstraint(
                fields=["words_set", "word"], name="uniq_wordsset_word"
            ),
        ]


class SaExerciseConfiguration(SaStampedModel):
    input_mode = models.CharField(
        max_length=32, default="FREE_INPUT"
    )  # TODO: ExercisesInputModeEnum.max_length
    answer_time_limit = models.SmallIntegerField(null=True, blank=True)
    time_limit_mode = models.CharField(
        max_length=32, default="ALL"
    )  # TODO: TimeLimitModeEnum.max_length
    repetitions_amount = models.SmallIntegerField(default=1)
    translations_mode = models.CharField(
        max_length=32, null=True, blank=True, default="FROM_LEARNING"
    )  # TODO
    definitions_mode = models.CharField(
        max_length=32, null=True, blank=True, default="DEFINITION_BY_WORD"
    )  # TODO
    is_default = models.BooleanField(default=False)
    hints_use_amount = models.SmallIntegerField(null=True, blank=True)

    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column="author_id",
        related_name="exercises_configurations",
    )
    exercise = models.ForeignKey(
        SaExercise,
        on_delete=models.DO_NOTHING,
        db_column="exercise_id",
        related_name="configurations",
    )

    # M2M
    words_set = models.ManyToManyField(
        SaWordsSet,
        through="SaExerciseConfigurationWordsSet",
        related_name="exercise_configurations",
        blank=True,
    )
    words = models.ManyToManyField(
        SaWord,
        through="SaExerciseConfigurationWords",
        related_name="exercise_configurations",
        blank=True,
    )
    hints_available = models.ManyToManyField(
        SaHint,
        through="SaExerciseConfigurationHintsAvailable",
        related_name="exercise_configurations",
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "exercises_exerciseconfiguration"

    def __str__(self) -> str:
        return f"{self.author_id} / {self.exercise_id}"


class SaExerciseConfigurationWordsSet(models.Model):
    exercise_configuration = models.ForeignKey(
        SaExerciseConfiguration,
        on_delete=models.DO_NOTHING,
        db_column="exerciseconfiguration_id",
        related_name="+",
    )
    words_set = models.ForeignKey(
        SaWordsSet,
        on_delete=models.DO_NOTHING,
        db_column="wordsset_id",
        related_name="+",
    )

    class Meta:
        managed = False
        db_table = "exercises_exerciseconfiguration_words_set"
        constraints = [
            models.UniqueConstraint(
                fields=["exercise_configuration", "words_set"], name="uniq_excfg_set"
            ),
        ]


class SaExerciseConfigurationWords(models.Model):
    exercise_configuration = models.ForeignKey(
        SaExerciseConfiguration,
        on_delete=models.DO_NOTHING,
        db_column="exerciseconfiguration_id",
        related_name="+",
    )
    word = models.ForeignKey(
        SaWord, on_delete=models.DO_NOTHING, db_column="word_id", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "exercises_exerciseconfiguration_words"
        constraints = [
            models.UniqueConstraint(
                fields=["exercise_configuration", "word"], name="uniq_excfg_word"
            ),
        ]


class SaExerciseConfigurationHintsAvailable(models.Model):
    exercise_configuration = models.ForeignKey(
        SaExerciseConfiguration,
        on_delete=models.DO_NOTHING,
        db_column="exerciseconfiguration_id",
        related_name="+",
    )
    hint = models.ForeignKey(
        SaHint, on_delete=models.DO_NOTHING, db_column="hint_id", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "exercises_exerciseconfiguration_hints_available"
        constraints = [
            models.UniqueConstraint(
                fields=["exercise_configuration", "hint"], name="uniq_excfg_hint"
            ),
        ]


# -----------------------
# FavoriteExercise
# -----------------------


class SaFavoriteExercise(SaStampedModel):
    exercise = models.ForeignKey(
        SaExercise,
        on_delete=models.DO_NOTHING,
        db_column="exercise_id",
        related_name="favorite_for",
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column="user_id",
        related_name="favorite_exercises",
    )

    class Meta:
        managed = False
        db_table = "exercises_favoriteexercise"
        constraints = [
            models.UniqueConstraint(
                fields=["exercise", "user"], name="unique_favorite_exercise"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} ♥ {self.exercise_id}"


# -----------------------
# CustomExerciseConfiguration / CustomGap
# -----------------------


class SaCustomGap(SaStampedModel):
    pre_position = models.IntegerField()
    order_position = models.IntegerField()
    correct_answers = models.TextField(null=True, blank=True)

    allowed_words = models.ManyToManyField(
        SaWord,
        through="SaCustomGapAllowedWords",
        related_name="custom_exercises_gaps",
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "exercises_customgap"

    def __str__(self) -> str:
        return str(self.id)


class SaCustomGapAllowedWords(models.Model):
    custom_gap = models.ForeignKey(
        SaCustomGap,
        on_delete=models.DO_NOTHING,
        db_column="customgap_id",
        related_name="+",
    )
    word = models.ForeignKey(
        SaWord, on_delete=models.DO_NOTHING, db_column="word_id", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "exercises_customgap_allowed_words"
        constraints = [
            models.UniqueConstraint(
                fields=["custom_gap", "word"], name="uniq_gap_word"
            ),
        ]


class SaCustomExerciseConfiguration(SaStampedModel):
    task = models.CharField(
        max_length=1024
    )  # TODO: ExercisesLengthLimits.EXERCISE_TASK_MAX_LENGTH
    content_text = models.CharField(
        max_length=4096, null=True, blank=True
    )  # TODO: ExercisesLengthLimits.EXERCISE_TASK_CONTENT_MAX_LENGTH
    content_image = models.CharField(max_length=1024, null=True, blank=True)
    correct_answers = models.TextField(null=True, blank=True)
    answer_time_limit = models.SmallIntegerField(null=True, blank=True)
    variants = models.TextField(null=True, blank=True)
    several_answers_allowed = models.BooleanField(default=False)

    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column="author_id",
        related_name="custom_exercises",
    )

    gaps = models.ManyToManyField(
        SaCustomGap,
        through="SaCustomExerciseConfigurationGaps",
        related_name="custom_exercises",
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "exercises_customexerciseconfiguration"

    def __str__(self) -> str:
        return self.task


class SaCustomExerciseConfigurationGaps(models.Model):
    custom_exercise_configuration = models.ForeignKey(
        SaCustomExerciseConfiguration,
        on_delete=models.DO_NOTHING,
        db_column="customexerciseconfiguration_id",
        related_name="+",
    )
    custom_gap = models.ForeignKey(
        SaCustomGap,
        on_delete=models.DO_NOTHING,
        db_column="customgap_id",
        related_name="+",
    )

    class Meta:
        managed = False
        db_table = "exercises_customexerciseconfiguration_gaps"
        constraints = [
            models.UniqueConstraint(
                fields=["custom_exercise_configuration", "custom_gap"],
                name="uniq_cex_gap",
            ),
        ]


# -----------------------
# ExercisesSet + favorites + schedule
# -----------------------


class SaExercisesSet(SaStampedModel):
    title = models.CharField(
        max_length=256
    )  # TODO: ExercisesLengthLimits.EXERCISES_SET_TITLE_MAX_LENGTH
    run_access_level = models.CharField(
        max_length=16, default="PUBLIC"
    )  # TODO: AccessLevelsEnum.max_length
    add_access_level = models.CharField(
        max_length=16, default="PUBLIC"
    )  # TODO: AccessLevelsEnum.max_length
    views_amount = models.IntegerField(default=0)

    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column="author_id",
        related_name="exercises_sets",
    )

    words = models.ManyToManyField(
        SaWord,
        through="SaExercisesSetWords",
        related_name="exercises_sets",
        blank=True,
    )
    exercises = models.ManyToManyField(
        SaExerciseConfiguration,
        through="SaExercisesSetExercises",
        related_name="exercises_sets",
        blank=True,
    )
    custom_exercises = models.ManyToManyField(
        SaCustomExerciseConfiguration,
        through="SaExercisesSetCustomExercises",
        related_name="exercises_sets",
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "exercises_exercisesset"

    def __str__(self) -> str:
        return self.title


class SaExercisesSetWords(models.Model):
    exercises_set = models.ForeignKey(
        SaExercisesSet,
        on_delete=models.DO_NOTHING,
        db_column="exercisesset_id",
        related_name="+",
    )
    word = models.ForeignKey(
        SaWord, on_delete=models.DO_NOTHING, db_column="word_id", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "exercises_exercisesset_words"
        constraints = [
            models.UniqueConstraint(
                fields=["exercises_set", "word"], name="uniq_exset_word"
            ),
        ]


class SaExercisesSetExercises(models.Model):
    exercises_set = models.ForeignKey(
        SaExercisesSet,
        on_delete=models.DO_NOTHING,
        db_column="exercisesset_id",
        related_name="+",
    )
    exercise_configuration = models.ForeignKey(
        SaExerciseConfiguration,
        on_delete=models.DO_NOTHING,
        db_column="exerciseconfiguration_id",
        related_name="+",
    )

    class Meta:
        managed = False
        db_table = "exercises_exercisesset_exercises"
        constraints = [
            models.UniqueConstraint(
                fields=["exercises_set", "exercise_configuration"],
                name="uniq_exset_excfg",
            ),
        ]


class SaExercisesSetCustomExercises(models.Model):
    exercises_set = models.ForeignKey(
        SaExercisesSet,
        on_delete=models.DO_NOTHING,
        db_column="exercisesset_id",
        related_name="+",
    )
    custom_exercise_configuration = models.ForeignKey(
        SaCustomExerciseConfiguration,
        on_delete=models.DO_NOTHING,
        db_column="customexerciseconfiguration_id",
        related_name="+",
    )

    class Meta:
        managed = False
        db_table = "exercises_exercisesset_custom_exercises"
        constraints = [
            models.UniqueConstraint(
                fields=["exercises_set", "custom_exercise_configuration"],
                name="uniq_exset_cex",
            ),
        ]


class SaFavoriteExercisesSet(SaStampedModel):
    exercises_set = models.ForeignKey(
        SaExercisesSet,
        on_delete=models.DO_NOTHING,
        db_column="exercises_set_id",
        related_name="favorite_for",
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column="user_id",
        related_name="favorite_exercises_sets",
    )

    class Meta:
        managed = False
        db_table = "exercises_favoriteexerciseset"
        constraints = [
            models.UniqueConstraint(
                fields=["exercises_set", "user"], name="unique_favorite_exercises_set"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} ♥ {self.exercises_set_id}"


class SaExerciseSchedule(SaStampedModel):
    scheduled_datetime = models.DateTimeField()
    send_notification = models.BooleanField(default=True)

    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column="user_id",
        related_name="schedule",
    )
    exercise = models.ForeignKey(
        SaExercise,
        on_delete=models.DO_NOTHING,
        db_column="exercise_id",
        null=True,
        blank=True,
        related_name="schedule",
    )
    exercise_configuration = models.ForeignKey(
        SaExerciseConfiguration,
        on_delete=models.DO_NOTHING,
        db_column="exercise_configuration_id",
        null=True,
        blank=True,
        related_name="schedule",
    )
    exercises_set = models.ForeignKey(
        SaExercisesSet,
        on_delete=models.DO_NOTHING,
        db_column="exercises_set_id",
        null=True,
        blank=True,
        related_name="schedule",
    )

    class Meta:
        managed = False
        db_table = "exercises_exerciseschedule"

    def __str__(self) -> str:
        return f"{self.user_id} @ {self.scheduled_datetime}"
