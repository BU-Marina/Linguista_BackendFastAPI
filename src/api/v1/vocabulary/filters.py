"""Vocabulary filters for FastAPI - reusable filter functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy import select, or_, func


@dataclass
class WordFilterParams:
    """Parameters for filtering words."""

    # Basic filters
    languages: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    types: Optional[list[str]] = None
    activity_status: Optional[list[str]] = None
    is_problematic: Optional[bool] = None
    first_letter: Optional[str] = None
    last_letter: Optional[str] = None
    have_associations: Optional[bool] = None
    read_access: Optional[list[str]] = None
    add_access: Optional[list[str]] = None
    borrowed: Optional[bool] = None

    # Related object filters (include)
    words: Optional[list[str]] = None
    collections: Optional[list[str]] = None
    translations: Optional[list[str]] = None
    images: Optional[list[str]] = None
    definitions: Optional[list[str]] = None
    examples: Optional[list[str]] = None

    # Related object filters (exclude)
    words_exclude: Optional[list[str]] = None
    collections_exclude: Optional[list[str]] = None
    translations_exclude: Optional[list[str]] = None
    images_exclude: Optional[list[str]] = None
    definitions_exclude: Optional[list[str]] = None
    examples_exclude: Optional[list[str]] = None
    suggested_words_exclude: Optional[list[str]] = None

    # Count filters
    translations_count: Optional[int] = None
    translations_count_gt: Optional[int] = None
    translations_count_lt: Optional[int] = None
    examples_count: Optional[int] = None
    examples_count_gt: Optional[int] = None
    examples_count_lt: Optional[int] = None
    definitions_count: Optional[int] = None
    definitions_count_gt: Optional[int] = None
    definitions_count_lt: Optional[int] = None
    images_count: Optional[int] = None
    images_count_gt: Optional[int] = None
    images_count_lt: Optional[int] = None
    synonyms_count: Optional[int] = None
    synonyms_count_gt: Optional[int] = None
    synonyms_count_lt: Optional[int] = None
    antonyms_count: Optional[int] = None
    antonyms_count_gt: Optional[int] = None
    antonyms_count_lt: Optional[int] = None
    forms_count: Optional[int] = None
    forms_count_gt: Optional[int] = None
    forms_count_lt: Optional[int] = None
    similars_count: Optional[int] = None
    similars_count_gt: Optional[int] = None
    similars_count_lt: Optional[int] = None
    tags_count: Optional[int] = None
    tags_count_gt: Optional[int] = None
    tags_count_lt: Optional[int] = None
    types_count: Optional[int] = None
    types_count_gt: Optional[int] = None
    types_count_lt: Optional[int] = None

    # Favorite
    favorite_only: bool = False


def apply_word_basic_filters(
    stmt,
    params: WordFilterParams,
    *,
    Word,
    Language,
    Tag,
    WordType,
    FavoriteWord=None,
    user_id: UUID | None = None,
):
    """Apply basic word filters (language, tags, types, etc.)."""
    if params.languages:
        stmt = stmt.join(Language, isouter=False).where(
            Language.isocode.in_(params.languages)
        )
    if params.tags:
        stmt = stmt.join(Word.tags).where(Tag.name.in_(params.tags))
    if params.types:
        stmt = stmt.join(Word.types).where(
            or_(WordType.name_en.in_(params.types), WordType.name_ru.in_(params.types))
        )
    if params.activity_status:
        stmt = stmt.where(Word.activity_status.in_(params.activity_status))
    if params.is_problematic is not None:
        stmt = stmt.where(Word.is_problematic == params.is_problematic)
    if params.first_letter:
        stmt = stmt.where(Word.text.ilike(f'{params.first_letter}%'))
    if params.last_letter:
        stmt = stmt.where(Word.text.like(f'%{params.last_letter}'))
    if params.read_access:
        stmt = stmt.where(Word.read_access_level.in_(params.read_access))
    if params.add_access:
        stmt = stmt.where(Word.add_access_level.in_(params.add_access))
    if params.borrowed is not None:
        if params.borrowed:
            stmt = stmt.where(Word.source_word_id.isnot(None))
        else:
            stmt = stmt.where(Word.source_word_id.is_(None))
    if params.words:
        stmt = stmt.where(Word.id.in_(params.words))
    if params.words_exclude:
        stmt = stmt.where(~Word.id.in_(params.words_exclude))
    if params.favorite_only and FavoriteWord is not None and user_id is not None:
        stmt = stmt.join(FavoriteWord).where(FavoriteWord.user_id == user_id)
    return stmt


def apply_word_relation_filters(
    stmt,
    params: WordFilterParams,
    *,
    Word,
    WordTranslations,
    WordDefinitions,
    WordUsageExamples,
    WordImageAssociations,
    WordsInCollections,
    WordsSuggestedToCollections=None,
):
    """Apply filters based on related objects (translations, images, definitions, examples, collections)."""
    # Translations
    if params.translations:
        subq = select(WordTranslations.word_id).where(
            WordTranslations.translation_id.in_(params.translations)
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.translations_exclude:
        subq = select(WordTranslations.word_id).where(
            WordTranslations.translation_id.in_(params.translations_exclude)
        )
        stmt = stmt.where(~Word.id.in_(subq))

    # Images
    if params.images:
        subq = select(WordImageAssociations.word_id).where(
            WordImageAssociations.image_id.in_(params.images)
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.images_exclude:
        subq = select(WordImageAssociations.word_id).where(
            WordImageAssociations.image_id.in_(params.images_exclude)
        )
        stmt = stmt.where(~Word.id.in_(subq))

    # Definitions
    if params.definitions:
        subq = select(WordDefinitions.word_id).where(
            WordDefinitions.definition_id.in_(params.definitions)
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.definitions_exclude:
        subq = select(WordDefinitions.word_id).where(
            WordDefinitions.definition_id.in_(params.definitions_exclude)
        )
        stmt = stmt.where(~Word.id.in_(subq))

    # Examples
    if params.examples:
        subq = select(WordUsageExamples.word_id).where(
            WordUsageExamples.example_id.in_(params.examples)
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.examples_exclude:
        subq = select(WordUsageExamples.word_id).where(
            WordUsageExamples.example_id.in_(params.examples_exclude)
        )
        stmt = stmt.where(~Word.id.in_(subq))

    # Collections
    if params.collections:
        subq = select(WordsInCollections.word_id).where(
            WordsInCollections.collection_id.in_(params.collections)
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.collections_exclude:
        subq = select(WordsInCollections.word_id).where(
            WordsInCollections.collection_id.in_(params.collections_exclude)
        )
        stmt = stmt.where(~Word.id.in_(subq))

    # Suggested words exclude
    if params.suggested_words_exclude and WordsSuggestedToCollections is not None:
        subq = select(WordsSuggestedToCollections.word_id).where(
            WordsSuggestedToCollections.collection_id.in_(
                params.suggested_words_exclude
            )
        )
        stmt = stmt.where(~Word.id.in_(subq))

    return stmt


def apply_word_have_associations_filter(
    stmt,
    params: WordFilterParams,
    *,
    Word,
    WordImageAssociations,
    QuoteAssociation=None,
):
    """Apply filter for words having/not having associations."""
    if params.have_associations is None:
        return stmt

    img_subq = select(WordImageAssociations.word_id)

    if params.have_associations:
        # Words that have at least one image association
        stmt = stmt.where(Word.id.in_(img_subq))
    else:
        # Words that have no image associations
        stmt = stmt.where(~Word.id.in_(img_subq))

    return stmt


def apply_word_count_filters(
    stmt,
    params: WordFilterParams,
    *,
    Word,
    WordTranslations,
    WordDefinitions,
    WordUsageExamples,
    WordImageAssociations,
    Synonym=None,
    Antonym=None,
    WordForm=None,
    SimilarWord=None,
):
    """
    Apply count-based filters.
    Note: These require subqueries and may impact performance.
    """

    # Helper to build count subquery
    def count_subq(join_model, word_id_col, target_col, value, op):
        subq = (
            select(word_id_col)
            .group_by(word_id_col)
            .having(op(func.count(target_col.distinct()), value))
        )
        return subq

    # Translations count
    if params.translations_count is not None:
        subq = count_subq(
            WordTranslations,
            WordTranslations.word_id,
            WordTranslations.translation_id,
            params.translations_count,
            lambda a, b: a == b,
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.translations_count_gt is not None:
        subq = count_subq(
            WordTranslations,
            WordTranslations.word_id,
            WordTranslations.translation_id,
            params.translations_count_gt,
            lambda a, b: a > b,
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.translations_count_lt is not None:
        subq = count_subq(
            WordTranslations,
            WordTranslations.word_id,
            WordTranslations.translation_id,
            params.translations_count_lt,
            lambda a, b: a < b,
        )
        stmt = stmt.where(Word.id.in_(subq))

    # Definitions count
    if params.definitions_count is not None:
        subq = count_subq(
            WordDefinitions,
            WordDefinitions.word_id,
            WordDefinitions.definition_id,
            params.definitions_count,
            lambda a, b: a == b,
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.definitions_count_gt is not None:
        subq = count_subq(
            WordDefinitions,
            WordDefinitions.word_id,
            WordDefinitions.definition_id,
            params.definitions_count_gt,
            lambda a, b: a > b,
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.definitions_count_lt is not None:
        subq = count_subq(
            WordDefinitions,
            WordDefinitions.word_id,
            WordDefinitions.definition_id,
            params.definitions_count_lt,
            lambda a, b: a < b,
        )
        stmt = stmt.where(Word.id.in_(subq))

    # Examples count
    if params.examples_count is not None:
        subq = count_subq(
            WordUsageExamples,
            WordUsageExamples.word_id,
            WordUsageExamples.example_id,
            params.examples_count,
            lambda a, b: a == b,
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.examples_count_gt is not None:
        subq = count_subq(
            WordUsageExamples,
            WordUsageExamples.word_id,
            WordUsageExamples.example_id,
            params.examples_count_gt,
            lambda a, b: a > b,
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.examples_count_lt is not None:
        subq = count_subq(
            WordUsageExamples,
            WordUsageExamples.word_id,
            WordUsageExamples.example_id,
            params.examples_count_lt,
            lambda a, b: a < b,
        )
        stmt = stmt.where(Word.id.in_(subq))

    # Images count
    if params.images_count is not None:
        subq = count_subq(
            WordImageAssociations,
            WordImageAssociations.word_id,
            WordImageAssociations.image_id,
            params.images_count,
            lambda a, b: a == b,
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.images_count_gt is not None:
        subq = count_subq(
            WordImageAssociations,
            WordImageAssociations.word_id,
            WordImageAssociations.image_id,
            params.images_count_gt,
            lambda a, b: a > b,
        )
        stmt = stmt.where(Word.id.in_(subq))
    if params.images_count_lt is not None:
        subq = count_subq(
            WordImageAssociations,
            WordImageAssociations.word_id,
            WordImageAssociations.image_id,
            params.images_count_lt,
            lambda a, b: a < b,
        )
        stmt = stmt.where(Word.id.in_(subq))

    # Synonyms count (requires Synonym model)
    if Synonym is not None:
        if (
            params.synonyms_count is not None
            or params.synonyms_count_gt is not None
            or params.synonyms_count_lt is not None
        ):
            # Synonyms are bidirectional: from_word_id and to_word_id
            from sqlalchemy import union_all

            syn_from = select(Synonym.from_word_id.label('word_id'))
            syn_to = select(Synonym.to_word_id.label('word_id'))
            syn_union = union_all(syn_from, syn_to).subquery()

            if params.synonyms_count is not None:
                subq = (
                    select(syn_union.c.word_id)
                    .group_by(syn_union.c.word_id)
                    .having(func.count() == params.synonyms_count)
                )
                stmt = stmt.where(Word.id.in_(subq))
            if params.synonyms_count_gt is not None:
                subq = (
                    select(syn_union.c.word_id)
                    .group_by(syn_union.c.word_id)
                    .having(func.count() > params.synonyms_count_gt)
                )
                stmt = stmt.where(Word.id.in_(subq))
            if params.synonyms_count_lt is not None:
                subq = (
                    select(syn_union.c.word_id)
                    .group_by(syn_union.c.word_id)
                    .having(func.count() < params.synonyms_count_lt)
                )
                stmt = stmt.where(Word.id.in_(subq))

    return stmt


def apply_word_filters(
    stmt,
    params: WordFilterParams,
    *,
    models: dict,
    user_id: UUID | None = None,
):
    """
    Apply all word filters. Convenience function that combines all filter functions.
    """
    Word = models['Word']
    Language = models['Language']
    Tag = models['Tag']
    WordType = models['WordType']
    FavoriteWord = models.get('FavoriteWord')
    WordTranslations = models['WordTranslations']
    WordDefinitions = models['WordDefinitions']
    WordUsageExamples = models['WordUsageExamples']
    WordImageAssociations = models['WordImageAssociations']
    WordsInCollections = models['WordsInCollections']
    WordsSuggestedToCollections = models.get('WordsSuggestedToCollections')
    Synonym = models.get('Synonym')

    # Apply basic filters
    stmt = apply_word_basic_filters(
        stmt,
        params,
        Word=Word,
        Language=Language,
        Tag=Tag,
        WordType=WordType,
        FavoriteWord=FavoriteWord,
        user_id=user_id,
    )

    # Apply relation filters
    stmt = apply_word_relation_filters(
        stmt,
        params,
        Word=Word,
        WordTranslations=WordTranslations,
        WordDefinitions=WordDefinitions,
        WordUsageExamples=WordUsageExamples,
        WordImageAssociations=WordImageAssociations,
        WordsInCollections=WordsInCollections,
        WordsSuggestedToCollections=WordsSuggestedToCollections,
    )

    # Apply have_associations filter
    stmt = apply_word_have_associations_filter(
        stmt,
        params,
        Word=Word,
        WordImageAssociations=WordImageAssociations,
    )

    # Apply count filters
    stmt = apply_word_count_filters(
        stmt,
        params,
        Word=Word,
        WordTranslations=WordTranslations,
        WordDefinitions=WordDefinitions,
        WordUsageExamples=WordUsageExamples,
        WordImageAssociations=WordImageAssociations,
        Synonym=Synonym,
    )

    return stmt


# ================== Collection Filters ==================


@dataclass
class CollectionFilterParams:
    """Parameters for filtering collections."""

    # Basic filters
    languages: Optional[list[str]] = None  # filter by words__language__isocode
    words_count_gt: Optional[int] = None
    words_count_lt: Optional[int] = None
    read_access: Optional[list[str]] = None
    add_access: Optional[list[str]] = None
    borrowed: Optional[bool] = None

    # Related object filters
    words: Optional[list[str]] = None
    words_exclude: Optional[list[str]] = None
    collections: Optional[list[str]] = None  # filter by id
    collections_exclude: Optional[list[str]] = None

    # Tags
    tags: Optional[list[str]] = None

    # Favorite
    favorite_only: bool = False


def apply_collection_filters(
    stmt,
    params: CollectionFilterParams,
    *,
    Collection,
    WordsInCollections,
    Word=None,
    Language=None,
    FavoriteCollection=None,
    user_id: UUID | None = None,
):
    """Apply collection filters."""
    # Filter by words language
    if params.languages and Word is not None and Language is not None:
        subq = (
            select(WordsInCollections.collection_id)
            .join(Word, Word.id == WordsInCollections.word_id)
            .join(Language, Language.id == Word.language_id)
            .where(Language.isocode.in_(params.languages))
            .distinct()
        )
        stmt = stmt.where(Collection.id.in_(subq))

    # Words count filters
    if params.words_count_gt is not None or params.words_count_lt is not None:
        count_subq = (
            select(
                WordsInCollections.collection_id,
                func.count(WordsInCollections.word_id).label('cnt'),
            ).group_by(WordsInCollections.collection_id)
        ).subquery()

        stmt = stmt.join(
            count_subq, Collection.id == count_subq.c.collection_id, isouter=True
        )

        if params.words_count_gt is not None:
            stmt = stmt.where(
                func.coalesce(count_subq.c.cnt, 0) > params.words_count_gt
            )
        if params.words_count_lt is not None:
            stmt = stmt.where(
                func.coalesce(count_subq.c.cnt, 0) < params.words_count_lt
            )

    # Access level filters
    if params.read_access:
        stmt = stmt.where(Collection.read_access_level.in_(params.read_access))
    if params.add_access:
        stmt = stmt.where(Collection.add_access_level.in_(params.add_access))

    # Borrowed filter
    if params.borrowed is not None:
        if params.borrowed:
            stmt = stmt.where(Collection.source_collection_id.isnot(None))
        else:
            stmt = stmt.where(Collection.source_collection_id.is_(None))

    # Words filter
    if params.words:
        subq = select(WordsInCollections.collection_id).where(
            WordsInCollections.word_id.in_(params.words)
        )
        stmt = stmt.where(Collection.id.in_(subq))
    if params.words_exclude:
        subq = select(WordsInCollections.collection_id).where(
            WordsInCollections.word_id.in_(params.words_exclude)
        )
        stmt = stmt.where(~Collection.id.in_(subq))

    # Collections filter (by id)
    if params.collections:
        stmt = stmt.where(Collection.id.in_(params.collections))
    if params.collections_exclude:
        stmt = stmt.where(~Collection.id.in_(params.collections_exclude))

    # Favorite only
    if params.favorite_only and FavoriteCollection is not None and user_id is not None:
        stmt = stmt.join(FavoriteCollection).where(
            FavoriteCollection.user_id == user_id
        )

    return stmt


# ================== Customization Content Filters (Translations, Images, etc.) ==================


@dataclass
class ContentFilterParams:
    """Common parameters for filtering translations, images, definitions, examples."""

    languages: Optional[list[str]] = None
    activity_status: Optional[list[str]] = None  # filter by words__activity_status
    collections: Optional[list[str]] = None
    collections_exclude: Optional[list[str]] = None
    words: Optional[list[str]] = None
    words_exclude: Optional[list[str]] = None

    # Count filters
    words_count: Optional[int] = None
    words_count_gt: Optional[int] = None
    words_count_lt: Optional[int] = None


def apply_content_filters(
    stmt,
    params: ContentFilterParams,
    *,
    ContentModel,  # e.g., WordTranslation, ImageAssociation, Definition, UsageExample
    JoinModel,  # e.g., WordTranslations, WordImageAssociations, WordDefinitions, WordUsageExamples
    content_id_col,  # e.g., WordTranslations.translation_id
    Word,
    WordsInCollections,
    Language=None,
):
    """Apply common filters for customization content (translations, images, definitions, examples)."""
    # Language filter
    if params.languages and Language is not None:
        # Filter by content's own language or by words' language
        word_subq = (
            select(JoinModel.c[content_id_col.key.replace('_id', '')])
            .join(Word, Word.id == JoinModel.word_id)
            .join(Language, Language.id == Word.language_id)
            .where(Language.isocode.in_(params.languages))
        )
        if hasattr(ContentModel, 'language_id'):
            own_lang_subq = (
                select(ContentModel.id)
                .join(Language, Language.id == ContentModel.language_id)
                .where(Language.isocode.in_(params.languages))
            )
            stmt = stmt.where(
                or_(ContentModel.id.in_(word_subq), ContentModel.id.in_(own_lang_subq))
            )
        else:
            stmt = stmt.where(ContentModel.id.in_(word_subq))

    # Activity status filter (by words)
    if params.activity_status:
        subq = (
            select(content_id_col)
            .join(Word, Word.id == JoinModel.word_id)
            .where(Word.activity_status.in_(params.activity_status))
        )
        stmt = stmt.where(ContentModel.id.in_(subq))

    # Collections filter
    if params.collections:
        subq = (
            select(content_id_col)
            .join(Word, Word.id == JoinModel.word_id)
            .join(WordsInCollections, WordsInCollections.word_id == Word.id)
            .where(WordsInCollections.collection_id.in_(params.collections))
        )
        stmt = stmt.where(ContentModel.id.in_(subq))
    if params.collections_exclude:
        subq = (
            select(content_id_col)
            .join(Word, Word.id == JoinModel.word_id)
            .join(WordsInCollections, WordsInCollections.word_id == Word.id)
            .where(WordsInCollections.collection_id.in_(params.collections_exclude))
        )
        stmt = stmt.where(~ContentModel.id.in_(subq))

    # Words filter
    if params.words:
        subq = select(content_id_col).where(JoinModel.word_id.in_(params.words))
        stmt = stmt.where(ContentModel.id.in_(subq))
    if params.words_exclude:
        subq = select(content_id_col).where(JoinModel.word_id.in_(params.words_exclude))
        stmt = stmt.where(~ContentModel.id.in_(subq))

    # Words count filter
    if (
        params.words_count is not None
        or params.words_count_gt is not None
        or params.words_count_lt is not None
    ):
        count_subq = (
            select(
                content_id_col, func.count(JoinModel.word_id.distinct()).label('cnt')
            ).group_by(content_id_col)
        ).subquery()

        stmt = stmt.join(
            count_subq,
            ContentModel.id == count_subq.c[content_id_col.key],
            isouter=True,
        )

        if params.words_count is not None:
            stmt = stmt.where(func.coalesce(count_subq.c.cnt, 0) == params.words_count)
        if params.words_count_gt is not None:
            stmt = stmt.where(
                func.coalesce(count_subq.c.cnt, 0) > params.words_count_gt
            )
        if params.words_count_lt is not None:
            stmt = stmt.where(
                func.coalesce(count_subq.c.cnt, 0) < params.words_count_lt
            )

    return stmt
