"""Vocabulary request params."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

from api.v1.utils.pagination import normalize_pagination
from api.v1.utils.parsing import parse_csv


def build_list_params(paramscls, filters_fields_list: list[str], **kwargs) -> Any:
    page, limit, offset = normalize_pagination(kwargs['page'], kwargs['limit'])
    return paramscls(
        page=page,
        limit=limit,
        offset=offset,
        ordering=kwargs.get('ordering'),
        search=kwargs.get('search'),
        **{field: parse_csv(kwargs.get(field)) for field in filters_fields_list},
    )


# ================== Words List Params ==================


@dataclass
class WordsListParams:
    """Parameters for words list endpoint."""

    # Pagination
    page: int = 1
    limit: int = 32
    offset: int = 0
    ordering: Optional[str] = None
    search: Optional[str] = None

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

    # Favorites
    favorite_only: bool = False


# List of all filterable fields for words
WORDS_FILTER_FIELDS = [
    # Basic
    'languages',
    'tags',
    'types',
    'activity_status',
    'read_access',
    'add_access',
    # Include
    'words',
    'collections',
    'translations',
    'images',
    'definitions',
    'examples',
    # Exclude
    'words_exclude',
    'collections_exclude',
    'translations_exclude',
    'images_exclude',
    'definitions_exclude',
    'examples_exclude',
    'suggested_words_exclude',
]


def build_words_list_params(**kwargs) -> WordsListParams:
    """Build WordsListParams from request kwargs."""
    page, limit, offset = normalize_pagination(kwargs['page'], kwargs['limit'])

    # Parse CSV fields
    parsed = {fld: parse_csv(kwargs.get(fld)) for fld in WORDS_FILTER_FIELDS}

    return WordsListParams(
        page=page,
        limit=limit,
        offset=offset,
        ordering=kwargs.get('ordering'),
        search=kwargs.get('search'),
        # Basic filters
        languages=parsed.get('languages'),
        tags=parsed.get('tags'),
        types=parsed.get('types'),
        activity_status=parsed.get('activity_status'),
        is_problematic=kwargs.get('is_problematic'),
        first_letter=kwargs.get('first_letter'),
        last_letter=kwargs.get('last_letter'),
        have_associations=kwargs.get('have_associations'),
        read_access=parsed.get('read_access'),
        add_access=parsed.get('add_access'),
        borrowed=kwargs.get('borrowed'),
        # Include filters
        words=parsed.get('words'),
        collections=parsed.get('collections'),
        translations=parsed.get('translations'),
        images=parsed.get('images'),
        definitions=parsed.get('definitions'),
        examples=parsed.get('examples'),
        # Exclude filters
        words_exclude=parsed.get('words_exclude'),
        collections_exclude=parsed.get('collections_exclude'),
        translations_exclude=parsed.get('translations_exclude'),
        images_exclude=parsed.get('images_exclude'),
        definitions_exclude=parsed.get('definitions_exclude'),
        examples_exclude=parsed.get('examples_exclude'),
        suggested_words_exclude=parsed.get('suggested_words_exclude'),
        # Count filters
        translations_count=kwargs.get('translations_count'),
        translations_count_gt=kwargs.get('translations_count_gt'),
        translations_count_lt=kwargs.get('translations_count_lt'),
        examples_count=kwargs.get('examples_count'),
        examples_count_gt=kwargs.get('examples_count_gt'),
        examples_count_lt=kwargs.get('examples_count_lt'),
        definitions_count=kwargs.get('definitions_count'),
        definitions_count_gt=kwargs.get('definitions_count_gt'),
        definitions_count_lt=kwargs.get('definitions_count_lt'),
        images_count=kwargs.get('images_count'),
        images_count_gt=kwargs.get('images_count_gt'),
        images_count_lt=kwargs.get('images_count_lt'),
        synonyms_count=kwargs.get('synonyms_count'),
        synonyms_count_gt=kwargs.get('synonyms_count_gt'),
        synonyms_count_lt=kwargs.get('synonyms_count_lt'),
        antonyms_count=kwargs.get('antonyms_count'),
        antonyms_count_gt=kwargs.get('antonyms_count_gt'),
        antonyms_count_lt=kwargs.get('antonyms_count_lt'),
        forms_count=kwargs.get('forms_count'),
        forms_count_gt=kwargs.get('forms_count_gt'),
        forms_count_lt=kwargs.get('forms_count_lt'),
        similars_count=kwargs.get('similars_count'),
        similars_count_gt=kwargs.get('similars_count_gt'),
        similars_count_lt=kwargs.get('similars_count_lt'),
        tags_count=kwargs.get('tags_count'),
        tags_count_gt=kwargs.get('tags_count_gt'),
        tags_count_lt=kwargs.get('tags_count_lt'),
        types_count=kwargs.get('types_count'),
        types_count_gt=kwargs.get('types_count_gt'),
        types_count_lt=kwargs.get('types_count_lt'),
        # Favorite
        favorite_only=kwargs.get('favorite_only', False),
    )


# ================== Collections List Params ==================


@dataclass
class CollectionsListParams:
    """Parameters for collections list endpoint."""

    # Pagination
    page: int = 1
    limit: int = 32
    offset: int = 0
    ordering: Optional[str] = None
    search: Optional[str] = None

    # Basic filters
    languages: Optional[list[str]] = None  # filter by words__language__isocode
    tags: Optional[list[str]] = None
    read_access: Optional[list[str]] = None
    add_access: Optional[list[str]] = None
    borrowed: Optional[bool] = None

    # Count filters
    words_count_gt: Optional[int] = None
    words_count_lt: Optional[int] = None

    # Related object filters
    words: Optional[list[str]] = None
    words_exclude: Optional[list[str]] = None
    collections: Optional[list[str]] = None
    collections_exclude: Optional[list[str]] = None

    # Favorites
    favorite_only: bool = False


COLLECTIONS_FILTER_FIELDS = [
    'languages',
    'tags',
    'read_access',
    'add_access',
    'words',
    'words_exclude',
    'collections',
    'collections_exclude',
]


def build_collections_list_params(**kwargs) -> CollectionsListParams:
    """Build CollectionsListParams from request kwargs."""
    page, limit, offset = normalize_pagination(kwargs['page'], kwargs['limit'])

    # Parse CSV fields
    parsed = {fld: parse_csv(kwargs.get(fld)) for fld in COLLECTIONS_FILTER_FIELDS}

    return CollectionsListParams(
        page=page,
        limit=limit,
        offset=offset,
        ordering=kwargs.get('ordering'),
        search=kwargs.get('search'),
        # Basic filters
        languages=parsed.get('languages'),
        tags=parsed.get('tags'),
        read_access=parsed.get('read_access'),
        add_access=parsed.get('add_access'),
        borrowed=kwargs.get('borrowed'),
        # Count filters
        words_count_gt=kwargs.get('words_count_gt'),
        words_count_lt=kwargs.get('words_count_lt'),
        # Related object filters
        words=parsed.get('words'),
        words_exclude=parsed.get('words_exclude'),
        collections=parsed.get('collections'),
        collections_exclude=parsed.get('collections_exclude'),
        # Favorite
        favorite_only=kwargs.get('favorite_only', False),
    )


# ================== Content (Translations, Images, Definitions, Examples) Params ==================


@dataclass
class ContentListParams:
    """Common parameters for translations, images, definitions, examples list endpoints."""

    # Pagination
    page: int = 1
    limit: int = 32
    offset: int = 0
    ordering: Optional[str] = None
    search: Optional[str] = None

    # Filters
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


CONTENT_FILTER_FIELDS = [
    'languages',
    'activity_status',
    'collections',
    'collections_exclude',
    'words',
    'words_exclude',
]


def build_content_list_params(**kwargs) -> ContentListParams:
    """Build ContentListParams from request kwargs."""
    page, limit, offset = normalize_pagination(kwargs['page'], kwargs['limit'])

    # Parse CSV fields
    parsed = {fld: parse_csv(kwargs.get(fld)) for fld in CONTENT_FILTER_FIELDS}

    return ContentListParams(
        page=page,
        limit=limit,
        offset=offset,
        ordering=kwargs.get('ordering'),
        search=kwargs.get('search'),
        # Filters
        languages=parsed.get('languages'),
        activity_status=parsed.get('activity_status'),
        collections=parsed.get('collections'),
        collections_exclude=parsed.get('collections_exclude'),
        words=parsed.get('words'),
        words_exclude=parsed.get('words_exclude'),
        # Count filters
        words_count=kwargs.get('words_count'),
        words_count_gt=kwargs.get('words_count_gt'),
        words_count_lt=kwargs.get('words_count_lt'),
    )
