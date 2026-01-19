"""..."""

from __future__ import annotations

from django.db import models

from sa_core.mixins import (
    SaStampedModel,
    SaSlugModel,
    SaPublicAccessModel,
    WordsCountMixin,
)
from sa_core.models import SaTag
from sa_languages.models import SaLanguage
from sa_users.models import SaUser


# ===== Through таблицы для M2M (secondary) =====


class SaVocabularyWordTypes(models.Model):
    word = models.ForeignKey(
        'SaWord', on_delete=models.DO_NOTHING, db_column='word_id', related_name='+'
    )
    word_type = models.ForeignKey(
        'SaWordType',
        on_delete=models.DO_NOTHING,
        db_column='wordtype_id',
        related_name='+',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_word_types'
        constraints = [
            models.UniqueConstraint(
                fields=['word', 'word_type'], name='uniq_word_wordtype'
            ),
        ]


class SaVocabularyWordTags(models.Model):
    word = models.ForeignKey(
        'SaWord', on_delete=models.DO_NOTHING, db_column='word_id', related_name='+'
    )
    tag = models.ForeignKey(
        SaTag, on_delete=models.DO_NOTHING, db_column='tag_id', related_name='+'
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_word_tags'
        constraints = [
            models.UniqueConstraint(fields=['word', 'tag'], name='uniq_word_tag'),
        ]


class SaVocabularyCollectionTags(models.Model):
    collection = models.ForeignKey(
        'SaCollection',
        on_delete=models.DO_NOTHING,
        db_column='collection_id',
        related_name='+',
    )
    tag = models.ForeignKey(
        SaTag, on_delete=models.DO_NOTHING, db_column='tag_id', related_name='+'
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_collection_tags'
        constraints = [
            models.UniqueConstraint(
                fields=['collection', 'tag'], name='uniq_collection_tag'
            ),
        ]


class SaVocabularyCollectionCoauthors(models.Model):
    collection = models.ForeignKey(
        'SaCollection',
        on_delete=models.DO_NOTHING,
        db_column='collection_id',
        related_name='+',
    )
    user = models.ForeignKey(
        SaUser, on_delete=models.DO_NOTHING, db_column='user_id', related_name='+'
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_collection_coauthors'
        constraints = [
            models.UniqueConstraint(
                fields=['collection', 'user'], name='uniq_collection_coauthor'
            ),
        ]


class SaVocabularyWordShareWith(models.Model):
    word = models.ForeignKey(
        'SaWord', on_delete=models.DO_NOTHING, db_column='word_id', related_name='+'
    )
    user = models.ForeignKey(
        SaUser, on_delete=models.DO_NOTHING, db_column='user_id', related_name='+'
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_word_share_with'
        constraints = [
            models.UniqueConstraint(
                fields=['word', 'user'], name='uniq_word_share_with'
            ),
        ]


class SaVocabularyCollectionShareWith(models.Model):
    collection = models.ForeignKey(
        'SaCollection',
        on_delete=models.DO_NOTHING,
        db_column='collection_id',
        related_name='+',
    )
    user = models.ForeignKey(
        SaUser, on_delete=models.DO_NOTHING, db_column='user_id', related_name='+'
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_collection_share_with'
        constraints = [
            models.UniqueConstraint(
                fields=['collection', 'user'], name='uniq_collection_share_with'
            ),
        ]


# -----------------------
# WordType
# -----------------------


class SaWordType(SaStampedModel, SaSlugModel, WordsCountMixin):
    name_ru = models.CharField(max_length=64, unique=True)
    name_en = models.CharField(max_length=64, unique=True)

    class Meta:
        managed = False
        db_table = 'vocabulary_wordtype'

    def __str__(self) -> str:
        return self.name_en or self.name_ru


# -----------------------
# Word
# -----------------------


class SaWord(SaStampedModel, SaSlugModel, SaPublicAccessModel):
    text = models.CharField(
        max_length=256
    )  # TODO: VocabularyLengthLimits.MAX_WORD_LENGTH

    activity_status = models.CharField(
        max_length=32, default='INACTIVE'
    )  # TODO: ActivityStatusEnum.max_length
    activity_progress = models.SmallIntegerField(default=0)

    is_problematic = models.BooleanField(default=False)
    is_trophie = models.BooleanField(default=False)

    note = models.CharField(
        max_length=1024, null=True, blank=True
    )  # TODO: VocabularyLengthLimits.MAX_NOTE_LENGTH
    last_exercise_date = models.DateTimeField(null=True, blank=True)

    is_premium = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)

    language = models.ForeignKey(
        SaLanguage,
        on_delete=models.DO_NOTHING,  # в БД SET NULL
        db_column='language_id',
        null=True,
        blank=True,
        related_name='words',
    )
    source_word = models.ForeignKey(
        'self',
        on_delete=models.DO_NOTHING,  # в БД SET NULL
        db_column='source_word_id',
        null=True,
        blank=True,
        related_name='borrowings',
    )
    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column='author_id',
        related_name='words',
    )

    # M2M
    types = models.ManyToManyField(
        SaWordType,
        through=SaVocabularyWordTypes,
        related_name='words',
        blank=True,
    )
    tags = models.ManyToManyField(
        SaTag,
        through=SaVocabularyWordTags,
        related_name='words',
        blank=True,
    )
    share_with = models.ManyToManyField(
        SaUser,
        through=SaVocabularyWordShareWith,
        related_name='shared_words',
        blank=True,
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_word'
        # case-insensitive уникальность (lower(text), author, language) — в Alembic.

    def __str__(self) -> str:
        return self.text


# -----------------------
# WordActivityHistory
# -----------------------


class SaExerciseSessionHistory(SaStampedModel):
    """
    FK на exercises_exercisesessionhistory (заглушка).
    Если модель уже есть в sa_exercises — импортируй её, а эту удали.
    """

    class Meta:
        managed = False
        db_table = 'exercises_exercisesessionhistory'


class SaWordActivityHistory(SaStampedModel):
    previous_activity_progress = models.SmallIntegerField(null=True, blank=True)
    new_activity_progress = models.SmallIntegerField(null=True, blank=True)
    upgrade = models.BooleanField(default=True)

    session = models.ForeignKey(
        SaExerciseSessionHistory,
        on_delete=models.DO_NOTHING,
        db_column='session_id',
        null=True,
        blank=True,
        related_name='words_activity_changes',
    )
    word = models.ForeignKey(
        SaWord,
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        related_name='activity_history',
    )

    previous_activity_status = models.CharField(
        max_length=32, default='INACTIVE'
    )  # TODO: ActivityStatusEnum.max_length
    new_activity_status = models.CharField(
        max_length=32, default='ACTIVE'
    )  # TODO: ActivityStatusEnum.max_length

    class Meta:
        managed = False
        db_table = 'vocabulary_wordactivityhistory'

    def __str__(self) -> str:
        return f'{self.word_id} @ {self.created}'


# -----------------------
# FormGroup
# -----------------------


class SaFormGroup(SaStampedModel, SaSlugModel, WordsCountMixin):
    name = models.CharField(
        max_length=256
    )  # TODO: VocabularyLengthLimits.MAX_FORMSGROUP_NAME_LENGTH
    color = models.CharField(max_length=7, null=True, blank=True)
    translation = models.CharField(
        max_length=256, null=True, blank=True
    )  # TODO: VocabularyLengthLimits.MAX_FORMSGROUP_TRANSLATION_LENGTH

    language = models.ForeignKey(
        SaLanguage,
        on_delete=models.DO_NOTHING,  # SET NULL
        db_column='language_id',
        null=True,
        blank=True,
        related_name='form_groups',
    )
    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # CASCADE
        db_column='author_id',
        related_name='form_groups',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_formgroup'
        # functional unique lower(name)+author — в Alembic.

    def __str__(self) -> str:
        return self.name


# -----------------------
# WordTranslation
# -----------------------


class SaWordTranslation(SaStampedModel, SaSlugModel, WordsCountMixin):
    text = models.CharField(
        max_length=256
    )  # TODO: VocabularyLengthLimits.MAX_TRANSLATION_LENGTH

    language = models.ForeignKey(
        SaLanguage,
        on_delete=models.DO_NOTHING,
        db_column='language_id',
        null=True,
        blank=True,
        related_name='word_translations',
    )
    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='author_id',
        related_name='word_translations',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordtranslation'
        # functional unique lower(text)+author+language — в Alembic.

    def __str__(self) -> str:
        return self.text


# -----------------------
# Definition
# -----------------------


class SaDefinition(SaStampedModel, SaSlugModel, WordsCountMixin):
    text = models.CharField(
        max_length=1024
    )  # TODO: VocabularyLengthLimits.MAX_DEFINITION_LENGTH
    translation = models.CharField(
        max_length=1024, null=True, blank=True
    )  # TODO: VocabularyLengthLimits.MAX_DEFINITION_LENGTH

    language = models.ForeignKey(
        SaLanguage,
        on_delete=models.DO_NOTHING,
        db_column='language_id',
        null=True,
        blank=True,
        related_name='definitions',
    )
    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='author_id',
        related_name='definitions',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_definition'
        # functional unique lower(text)+author — в Alembic.

    def __str__(self) -> str:
        return self.text


# -----------------------
# UsageExample
# -----------------------


class SaUsageExample(SaStampedModel, SaSlugModel, WordsCountMixin):
    text = models.CharField(
        max_length=2048
    )  # TODO: VocabularyLengthLimits.MAX_EXAMPLE_LENGTH
    translation = models.CharField(max_length=2048, null=True, blank=True)  # TODO

    source = models.CharField(max_length=3, default='OTH')
    source_name = models.CharField(
        max_length=256, null=True, blank=True
    )  # TODO: VocabularyLengthLimits.MAX_EXAMPLE_SOURCE_LENGTH
    source_url = models.CharField(
        max_length=1024, null=True, blank=True
    )  # TODO: VocabularyLengthLimits.MAX_EXAMPLE_SOURCE_LINK_LENGTH

    language = models.ForeignKey(
        SaLanguage,
        on_delete=models.DO_NOTHING,
        db_column='language_id',
        null=True,
        blank=True,
        related_name='examples',
    )
    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='author_id',
        related_name='examples',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_usageexample'
        # functional unique lower(text)+author — в Alembic.

    def __str__(self) -> str:
        return self.text[:80]


# -----------------------
# ImageAssociation
# -----------------------


class SaImageAssociation(SaStampedModel, WordsCountMixin):
    image_url = models.CharField(max_length=1024, null=True, blank=True)
    width = models.SmallIntegerField(null=True, blank=True)
    height = models.SmallIntegerField(null=True, blank=True)
    num = models.SmallIntegerField(null=True, blank=True)

    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='author_id',
        related_name='image_associations',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_imageassociation'

    def __str__(self) -> str:
        return str(self.id)


# -----------------------
# QuoteAssociation
# -----------------------


class SaQuoteAssociation(SaStampedModel):
    text = models.CharField(
        max_length=1024
    )  # TODO: VocabularyLengthLimits.MAX_QUOTE_TEXT_LENGTH
    quote_author = models.CharField(
        max_length=256, null=True, blank=True
    )  # TODO: VocabularyLengthLimits.MAX_QUOTE_AUTHOR_LENGTH

    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='author_id',
        related_name='quote_associations',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_quoteassociation'

    def __str__(self) -> str:
        return self.text[:80]


# -----------------------
# Collection
# -----------------------


class SaCollection(SaStampedModel, SaSlugModel, SaPublicAccessModel, WordsCountMixin):
    title = models.CharField(
        max_length=256
    )  # TODO: VocabularyLengthLimits.MAX_COLLECTION_TITLE_LENGTH
    description = models.CharField(
        max_length=2048, null=True, blank=True
    )  # TODO: VocabularyLengthLimits.MAX_COLLECTION_DESCRIPTION_LENGTH

    allow_comments = models.BooleanField(default=True)
    allow_suggestions = models.BooleanField(default=True)
    allow_suggestions_notifications = models.BooleanField(default=True)
    is_premium = models.BooleanField(default=False)

    source_collection = models.ForeignKey(
        'self',
        on_delete=models.DO_NOTHING,  # SET NULL
        db_column='source_collection_id',
        null=True,
        blank=True,
        related_name='borrowings',
    )
    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # CASCADE
        db_column='author_id',
        related_name='collections',
    )

    tags = models.ManyToManyField(
        SaTag,
        through=SaVocabularyCollectionTags,
        related_name='collections',
        blank=True,
    )
    coauthors = models.ManyToManyField(
        SaUser,
        through=SaVocabularyCollectionCoauthors,
        related_name='joint_collections',
        blank=True,
    )
    share_with = models.ManyToManyField(
        SaUser,
        through=SaVocabularyCollectionShareWith,
        related_name='shared_collections',
        blank=True,
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_collection'
        # functional unique lower(title)+author — в Alembic.

    def __str__(self) -> str:
        return self.title


# -----------------------
# CollectionSubscription
# -----------------------


class SaCollectionSubscription(SaStampedModel):
    enable_notifications = models.BooleanField(default=True)
    new_words = models.TextField(null=True, blank=True)
    updated_words = models.TextField(null=True, blank=True)

    subscriber = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,  # CASCADE
        db_column='subscriber_id',
        related_name='collections_subscriptions_detail',
    )
    collection = models.ForeignKey(
        SaCollection,
        on_delete=models.DO_NOTHING,  # CASCADE
        db_column='collection_id',
        related_name='subscribers_detail',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_collectionsubscription'
        constraints = [
            models.UniqueConstraint(
                fields=['subscriber', 'collection'],
                name='unique_collection_subscription',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.subscriber_id} -> {self.collection_id}'


# -------------------------
# Through / intermediary models
# -------------------------


class SaWordsFormGroups(SaStampedModel):
    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,  # в БД CASCADE
        db_column='word_id',
        related_name='words_form_groups',
    )
    forms_group = models.ForeignKey(
        'SaFormGroup',
        on_delete=models.DO_NOTHING,  # в БД SET NULL
        db_column='forms_group_id',
        null=True,
        blank=True,
        related_name='words_form_groups',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordsformgroups'
        constraints = [
            models.UniqueConstraint(
                fields=['word', 'forms_group'], name='unique_word_forms_group'
            ),
        ]


class SaWordTranslations(SaStampedModel):
    translation = models.ForeignKey(
        'SaWordTranslation',
        on_delete=models.DO_NOTHING,
        db_column='translation_id',
        related_name='wordtranslations',
    )
    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        related_name='wordtranslations',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordtranslations'
        constraints = [
            models.UniqueConstraint(
                fields=['word', 'translation'], name='unique_word_translation'
            ),
        ]


class SaWordDefinitions(SaStampedModel):
    definition = models.ForeignKey(
        'SaDefinition',
        on_delete=models.DO_NOTHING,
        db_column='definition_id',
        related_name='worddefinitions',
    )
    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        related_name='worddefinitions',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_worddefinitions'
        constraints = [
            models.UniqueConstraint(
                fields=['word', 'definition'], name='unique_word_definition'
            ),
        ]


class SaWordUsageExamples(SaStampedModel):
    example = models.ForeignKey(
        'SaUsageExample',
        on_delete=models.DO_NOTHING,
        db_column='example_id',
        related_name='wordusageexamples',
    )
    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        related_name='wordusageexamples',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordusageexamples'
        constraints = [
            models.UniqueConstraint(
                fields=['word', 'example'], name='unique_word_example'
            ),
        ]


class SaWordImageAssociations(SaStampedModel):
    image = models.ForeignKey(
        'SaImageAssociation',
        on_delete=models.DO_NOTHING,
        db_column='image_id',
        related_name='wordimageassociations',
    )
    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        related_name='wordimageassociations',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordimageassociations'
        constraints = [
            models.UniqueConstraint(fields=['word', 'image'], name='unique_word_image'),
        ]


class SaWordQuoteAssociations(SaStampedModel):
    quote = models.ForeignKey(
        'SaQuoteAssociation',
        on_delete=models.DO_NOTHING,
        db_column='quote_id',
        related_name='wordquoteassociations',
    )
    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        related_name='wordquoteassociations',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordquoteassociations'
        constraints = [
            models.UniqueConstraint(fields=['word', 'quote'], name='unique_word_quote'),
        ]


class SaWordsInCollections(SaStampedModel):
    collection = models.ForeignKey(
        'SaCollection',
        on_delete=models.DO_NOTHING,
        db_column='collection_id',
        related_name='words_in_collections',
    )
    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        related_name='words_in_collections',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordsincollections'
        constraints = [
            models.UniqueConstraint(
                fields=['word', 'collection'], name='unique_word_in_collection'
            ),
        ]


class SaWordsSuggestedToCollections(SaStampedModel):
    status = models.CharField(
        max_length=32,  # TODO: RequestStatusEnum.max_length
        default='PENDING',
    )

    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        related_name='suggestions',
    )
    collection = models.ForeignKey(
        'SaCollection',
        on_delete=models.DO_NOTHING,
        db_column='collection_id',
        related_name='suggestions',
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='user_id',
        related_name='words_suggested',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordssuggestedtocollections'
        constraints = [
            models.UniqueConstraint(
                fields=['word', 'collection', 'user'], name='unique_suggested_word'
            ),
        ]


# -------------------------
# Self-related models (synonyms/antonyms/forms/similar/derivative)
# -------------------------


class SaWordSelfRelationBase(SaStampedModel):
    """
    Абстрактная база для synonym/antonym/form/derivative/similar.
    В Sa у тебя динамические имена constraint'ов — в Django надо задать конкретные имена на классах.
    """

    from_word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='from_word_id',
        related_name='%(class)s_from_words',
    )
    to_word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='to_word_id',
        related_name='%(class)s_to_words',
    )

    class Meta:
        abstract = True
        managed = False


class SaSynonym(SaWordSelfRelationBase):
    note = models.CharField(
        max_length=1024, null=True, blank=True
    )  # TODO: VocabularyLengthLimits.MAX_NOTE_LENGTH

    class Meta:
        managed = False
        db_table = 'vocabulary_synonym'
        constraints = [
            models.UniqueConstraint(
                fields=['from_word', 'to_word'], name='uniq_pair_synonym'
            ),
            models.CheckConstraint(
                check=~models.Q(from_word=models.F('to_word')),
                name='synonym_not_same_word',
            ),
        ]


class SaAntonym(SaWordSelfRelationBase):
    note = models.CharField(
        max_length=1024, null=True, blank=True
    )  # TODO: VocabularyLengthLimits.MAX_NOTE_LENGTH

    class Meta:
        managed = False
        db_table = 'vocabulary_antonym'
        constraints = [
            models.UniqueConstraint(
                fields=['from_word', 'to_word'], name='uniq_pair_antonym'
            ),
            models.CheckConstraint(
                check=~models.Q(from_word=models.F('to_word')),
                name='antonym_not_same_word',
            ),
        ]


class SaForm(SaWordSelfRelationBase):
    class Meta:
        managed = False
        db_table = 'vocabulary_form'
        constraints = [
            models.UniqueConstraint(
                fields=['from_word', 'to_word'], name='uniq_pair_form'
            ),
            models.CheckConstraint(
                check=~models.Q(from_word=models.F('to_word')),
                name='form_not_same_word',
            ),
        ]


class SaDerivative(SaWordSelfRelationBase):
    class Meta:
        managed = False
        db_table = 'vocabulary_derivative'
        constraints = [
            models.UniqueConstraint(
                fields=['from_word', 'to_word'], name='uniq_pair_derivative'
            ),
            models.CheckConstraint(
                check=~models.Q(from_word=models.F('to_word')),
                name='derivative_not_same_word',
            ),
        ]


class SaSimilar(SaWordSelfRelationBase):
    class Meta:
        managed = False
        db_table = 'vocabulary_similar'
        constraints = [
            models.UniqueConstraint(
                fields=['from_word', 'to_word'], name='uniq_pair_similar'
            ),
            models.CheckConstraint(
                check=~models.Q(from_word=models.F('to_word')),
                name='similar_not_same_word',
            ),
        ]


# -------------------------
# Favorites, Views, Approves, PremiumRequest
# -------------------------


class SaFavoriteWord(SaStampedModel):
    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        related_name='favorite_for',
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='user_id',
        related_name='favorite_words',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_favoriteword'
        constraints = [
            models.UniqueConstraint(
                fields=['word', 'user'], name='unique_user_favorite_word'
            ),
        ]


class SaFavoriteCollection(SaStampedModel):
    collection = models.ForeignKey(
        'SaCollection',
        on_delete=models.DO_NOTHING,
        db_column='collection_id',
        related_name='favorite_for',
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='user_id',
        related_name='favorite_collections',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_favoritecollection'
        constraints = [
            models.UniqueConstraint(
                fields=['collection', 'user'], name='unique_user_favorite_collection'
            ),
        ]


class SaViewWord(SaStampedModel):
    view_datetime = models.DateTimeField(null=True, blank=True)

    word = models.ForeignKey(
        'SaWord', on_delete=models.DO_NOTHING, db_column='word_id', related_name='views'
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='user_id',
        related_name='word_views',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_viewword'
        constraints = [
            models.UniqueConstraint(fields=['word', 'user'], name='unique_word_view'),
        ]


class SaViewCollection(SaStampedModel):
    view_datetime = models.DateTimeField(null=True, blank=True)

    collection = models.ForeignKey(
        'SaCollection',
        on_delete=models.DO_NOTHING,
        db_column='collection_id',
        related_name='views',
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='user_id',
        related_name='collection_views',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_viewcollection'
        constraints = [
            models.UniqueConstraint(
                fields=['collection', 'user'], name='unique_collection_view'
            ),
        ]


class SaWordApprove(SaStampedModel):
    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        related_name='approves',
    )
    user = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='user_id',
        related_name='approves',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordapprove'
        constraints = [
            models.UniqueConstraint(
                fields=['word', 'user'], name='unique_word_approve'
            ),
        ]


class SaPremiumRequest(SaStampedModel):
    review = models.CharField(
        max_length=2048, null=True, blank=True
    )  # TODO: CoreLengthLimits.REVIEW_TEXT_MAX_LENGTH
    request_status = models.CharField(
        max_length=32, default='PENDING'
    )  # TODO: RequestStatusEnum.max_length

    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        null=True,
        blank=True,
        related_name='premium_requests',
    )
    collection = models.ForeignKey(
        'SaCollection',
        on_delete=models.DO_NOTHING,
        db_column='collection_id',
        null=True,
        blank=True,
        related_name='premium_requests',
    )
    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='author_id',
        related_name='premium_requests',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_premiumrequest'
        # В Sa word_id/collection_id unique=True (one-to-one semantics).
        # В Django это можно отразить constraints'ами:
        constraints = [
            models.UniqueConstraint(fields=['word'], name='uniq_premium_word'),
            models.UniqueConstraint(
                fields=['collection'], name='uniq_premium_collection'
            ),
        ]


# -------------------------
# Comments
# -------------------------


class SaCollectionComment(SaStampedModel):
    text = models.TextField()
    author_liked = models.BooleanField(default=False)
    text_modified = models.BooleanField(default=False)

    collection = models.ForeignKey(
        'SaCollection',
        on_delete=models.DO_NOTHING,
        db_column='collection_id',
        related_name='comments',
    )
    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='author_id',
        related_name='collection_comments',
    )

    # likes/dislikes/answers через secondary таблицы
    likes = models.ManyToManyField(
        SaUser,
        through='SaVocabularyCollectionCommentLikes',
        related_name='collection_comments_liked',
        blank=True,
    )
    dislikes = models.ManyToManyField(
        SaUser,
        through='SaVocabularyCollectionCommentDislikes',
        related_name='collection_comments_disliked',
        blank=True,
    )
    answers = models.ManyToManyField(
        'self',
        through='SaVocabularyCollectionCommentAnswers',
        symmetrical=False,
        related_name='answer_for',
        blank=True,
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_collectioncomment'

    def __str__(self) -> str:
        return f'CollectionComment({self.id})'


class SaWordComment(SaStampedModel):
    text = models.TextField()
    author_liked = models.BooleanField(default=False)
    text_modified = models.BooleanField(default=False)

    word = models.ForeignKey(
        'SaWord',
        on_delete=models.DO_NOTHING,
        db_column='word_id',
        related_name='comments',
    )
    author = models.ForeignKey(
        SaUser,
        on_delete=models.DO_NOTHING,
        db_column='author_id',
        related_name='word_comments',
    )

    likes = models.ManyToManyField(
        SaUser,
        through='SaVocabularyWordCommentLikes',
        related_name='word_comments_liked',
        blank=True,
    )
    dislikes = models.ManyToManyField(
        SaUser,
        through='SaVocabularyWordCommentDislikes',
        related_name='word_comments_disliked',
        blank=True,
    )
    answers = models.ManyToManyField(
        'self',
        through='SaVocabularyWordCommentAnswers',
        symmetrical=False,
        related_name='answer_for',
        blank=True,
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordcomment'

    def __str__(self) -> str:
        return f'WordComment({self.id})'


# ===== Through tables for comment likes/dislikes/answers =====
# ИМЕНА ТАБЛИЦ И КОЛОНОК — предположения. Если у тебя другие, поправим.


class SaVocabularyCollectionCommentLikes(models.Model):
    collectioncomment = models.ForeignKey(
        SaCollectionComment,
        on_delete=models.DO_NOTHING,
        db_column='collectioncomment_id',
        related_name='+',
    )
    user = models.ForeignKey(
        SaUser, on_delete=models.DO_NOTHING, db_column='user_id', related_name='+'
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_collectioncomment_likes'
        constraints = [
            models.UniqueConstraint(
                fields=['collectioncomment', 'user'], name='uniq_colcom_like'
            ),
        ]


class SaVocabularyCollectionCommentDislikes(models.Model):
    collectioncomment = models.ForeignKey(
        SaCollectionComment,
        on_delete=models.DO_NOTHING,
        db_column='collectioncomment_id',
        related_name='+',
    )
    user = models.ForeignKey(
        SaUser, on_delete=models.DO_NOTHING, db_column='user_id', related_name='+'
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_collectioncomment_dislikes'
        constraints = [
            models.UniqueConstraint(
                fields=['collectioncomment', 'user'], name='uniq_colcom_dislike'
            ),
        ]


class SaVocabularyCollectionCommentAnswers(models.Model):
    collectioncomment = models.ForeignKey(
        SaCollectionComment,
        on_delete=models.DO_NOTHING,
        db_column='collectioncomment_id',
        related_name='+',
    )
    answer = models.ForeignKey(
        SaCollectionComment,
        on_delete=models.DO_NOTHING,
        db_column='answer_id',
        related_name='+',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_collectioncomment_answers'
        constraints = [
            models.UniqueConstraint(
                fields=['collectioncomment', 'answer'], name='uniq_colcom_answer'
            ),
        ]


class SaVocabularyWordCommentLikes(models.Model):
    wordcomment = models.ForeignKey(
        SaWordComment,
        on_delete=models.DO_NOTHING,
        db_column='wordcomment_id',
        related_name='+',
    )
    user = models.ForeignKey(
        SaUser, on_delete=models.DO_NOTHING, db_column='user_id', related_name='+'
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordcomment_likes'
        constraints = [
            models.UniqueConstraint(
                fields=['wordcomment', 'user'], name='uniq_wordcom_like'
            ),
        ]


class SaVocabularyWordCommentDislikes(models.Model):
    wordcomment = models.ForeignKey(
        SaWordComment,
        on_delete=models.DO_NOTHING,
        db_column='wordcomment_id',
        related_name='+',
    )
    user = models.ForeignKey(
        SaUser, on_delete=models.DO_NOTHING, db_column='user_id', related_name='+'
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordcomment_dislikes'
        constraints = [
            models.UniqueConstraint(
                fields=['wordcomment', 'user'], name='uniq_wordcom_dislike'
            ),
        ]


class SaVocabularyWordCommentAnswers(models.Model):
    wordcomment = models.ForeignKey(
        SaWordComment,
        on_delete=models.DO_NOTHING,
        db_column='wordcomment_id',
        related_name='+',
    )
    answer = models.ForeignKey(
        SaWordComment,
        on_delete=models.DO_NOTHING,
        db_column='answer_id',
        related_name='+',
    )

    class Meta:
        managed = False
        db_table = 'vocabulary_wordcomment_answers'
        constraints = [
            models.UniqueConstraint(
                fields=['wordcomment', 'answer'], name='uniq_wordcom_answer'
            ),
        ]
