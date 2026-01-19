"""Общие миксины для таблиц из SQLAlchemy Base."""

import uuid

from django.db import models

from sa_core.constants import DEFAULT_MAX_SLUG_LENGTH


class SaStampedModel(models.Model):
    """
    Отражает поля, которые приходят из core.base.Base:
    - id UUID PK
    - created/updated timestamps
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        managed = False


class SaSlugModel(models.Model):
    """
    Отражает SlugMixin.
    """

    slug = models.SlugField(
        max_length=DEFAULT_MAX_SLUG_LENGTH, unique=False, null=True, blank=True
    )

    class Meta:
        abstract = True
        managed = False


class SaPublicAccessModel(models.Model):
    """
    Django mirror-аналог PublicAccessModel для SA-таблиц.

    Предполагается, что реальная схема/ограничения создаются Alembic’ом,
    а в Django это используется как "обертка" (managed=False у конечных моделей).

    ВАЖНО:
    - Поле share_with здесь объявлено как M2M БЕЗ through, поэтому Django будет
      ожидать таблицу с именем по своим правилам.
      share_with лучше объявлять в конкретных моделях Word/Collection с through=...
    """

    read_access_level = models.CharField(
        max_length=8,  # AccessLevelsEnum.max_length
        default='PUB',  # AccessLevelsEnum.PUBLIC
    )
    add_access_level = models.CharField(
        max_length=8,
        default='PUB',
    )
    allow_access_change = models.BooleanField(default=True)

    class Meta:
        abstract = True
        managed = False


class WordsCountMixin:
    """Custom model mixin to add `words_count` method"""

    def words_count(self) -> int:
        """
        Returns object related words amount.
        Related name of word objects must be `words`.
        """
        # Prefer explicit words M2M, fallback to through relation for collections
        if hasattr(self, 'words'):
            return self.words.count()
        if hasattr(self, 'words_in_collections'):
            return self.words_in_collections.count()
        return 0
