"""Published objects services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from asyncpg.exceptions import UniqueViolationError

from api.v1.utils.ordering import apply_ordering
from api.v1.utils.searching import apply_search
from api.v1.utils.pagination import normalize_pagination
from api.v1.vocabulary.mapping import map_word, map_word_read
from api.v1.vocabulary.params import WordsListParams, CollectionsListParams
from api.v1.vocabulary.filters import apply_word_filters
from api.v1.collections.mapping import map_collection
from api.v1.vocabulary.services import (
    word_favorite_toggle_service,
    _params_to_filter_params,
)
from api.v1.collections.services import (
    collection_favorite_toggle_service,
)
from api.v1.translations.schemas import TranslationOut
from api.v1.definitions.schemas import DefinitionOut
from api.v1.usage_examples.schemas import ExampleOut
from api.v1.image_associations.schemas import ImageOut
from api.v1.collections.schemas import (
    CollectionResolveOut,
    CollectionCommentOut,
    CollectionCommentsPageOut,
)
from api.v1.vocabulary.schemas import (
    WordReadOut,
    WordResolveOut,
    WordsWithAuthorPageOut,
    WordCommentOut,
    WordCommentsPageOut,
)
from api.v1.published.schemas import (
    WordListWithAuthorOut,
    WordPublishedProfileOut,
    CollectionPublishedProfileOut,
    CollectionSuggestedWordOut,
    CollectionSuggestedWordsPageOut,
)
from api.v1.vocabulary.models import VOCAB_MODELS
from core.constants import AccessLevelsEnum, RequestStatusEnum, ActivityStatusEnum
from apps.users.models import Friend, Subscription, User
from apps.vocabulary.models import (
    CollectionSubscription,
    CollectionComment,
    WordComment,
    WordsSuggestedToCollections,
)


def _can_view(
    access_level: str, user_id: UUID | None, author_id: UUID, friend_ids: set[UUID]
) -> bool:
    if access_level == AccessLevelsEnum.PUBLIC:
        return True
    if user_id is None:
        return False
    if user_id == author_id:
        return True
    if access_level in {
        AccessLevelsEnum.FRIENDS,
        AccessLevelsEnum.FRIENDS_AND_STUDY_GROUPS,
    }:
        return user_id in friend_ids
    return False


async def _get_friend_ids(session: AsyncSession, user_id: UUID) -> set[UUID]:
    rows1 = (
        (
            await session.execute(
                select(Friend.friend_id).where(Friend.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    rows2 = (
        (
            await session.execute(
                select(Friend.user_id).where(Friend.friend_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    return set(rows1 + rows2)


async def _get_subscription_author_ids(
    session: AsyncSession, user_id: UUID
) -> list[UUID]:
    return (
        (
            await session.execute(
                select(Subscription.user_id).where(
                    Subscription.subscriber_id == user_id
                )
            )
        )
        .scalars()
        .all()
    )


def _apply_common_word_filters(
    stmt,
    *,
    Word,
    Language,
    Tag,
    WordType,
    params: WordsListParams,
    favorite_only: bool,
    user_id: UUID | None,
):
    """Apply common word filters using the shared filters module."""
    # Convert params to filter params and set favorite_only
    filter_params = _params_to_filter_params(params)
    filter_params.favorite_only = favorite_only

    # Apply all filters
    return apply_word_filters(stmt, filter_params, models=VOCAB_MODELS, user_id=user_id)


async def published_words_list_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    params: WordsListParams,
    author_ids: Iterable[UUID] | None = None,
    favorite_only: bool = False,
    ordering_override: str | None = None,
    collections: Iterable[UUID] | None = None,
    models: dict = VOCAB_MODELS,
):
    Word = models['Word']
    Language = models['Language']
    Tag = models['Tag']
    WordType = models['WordType']
    FavoriteWord = models['FavoriteWord']
    WordsInCollections = models['WordsInCollections']

    allowed_levels = [
        AccessLevelsEnum.PUBLIC,
        AccessLevelsEnum.FRIENDS,
        AccessLevelsEnum.FRIENDS_AND_STUDY_GROUPS,
    ]

    stmt = select(Word).where(
        Word.read_access_level.in_(allowed_levels),
    )
    if author_ids is not None:
        author_ids = list(author_ids)
        if not author_ids:
            return params, 0, []
        stmt = stmt.where(Word.author_id.in_(author_ids))
    if collections is not None:
        collection_ids = list(collections)
        if not collection_ids:
            return params, 0, []
        stmt = stmt.join(WordsInCollections).where(
            WordsInCollections.collection_id.in_(collection_ids)
        )

    stmt = _apply_common_word_filters(
        stmt,
        Word=Word,
        Language=Language,
        Tag=Tag,
        WordType=WordType,
        params=params,
        favorite_only=favorite_only,
        user_id=user_id,
    )

    search_fields = ['text', 'note']
    stmt = apply_search(stmt, Word, params.search, search_fields)

    ordering_map = {
        'text': Word.text,
        'created': Word.created,
        'modified': Word.modified,
    }
    default_ordering = ordering_override or '-modified'
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default=default_ordering)

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    stmt = stmt.offset(params.offset).limit(params.limit)
    stmt = stmt.options(
        selectinload(Word.tags),
        selectinload(Word.types),
        selectinload(Word.language),
        selectinload(Word.author),
        selectinload(Word.wordtranslations).selectinload(
            VOCAB_MODELS['WordTranslations'].translation
        ),
        selectinload(Word.wordimageassociations).selectinload(
            VOCAB_MODELS['WordImageAssociations'].image
        ),
    )
    rows: Sequence = (await session.execute(stmt)).scalars().all()

    fav_ids: set[UUID] = set()
    if user_id and rows:
        fav_ids = set(
            (
                await session.execute(
                    select(FavoriteWord.word_id).where(
                        FavoriteWord.user_id == user_id,
                        FavoriteWord.word_id.in_([w.id for w in rows]),
                    )
                )
            ).scalars()
        )

    results = []
    for w in rows:
        w._favorite = w.id in fav_ids
        author = getattr(w, 'author', None)
        # Get images through the intermediate WordImageAssociations model
        word_image_assocs = getattr(w, 'wordimageassociations', []) or []
        images = [wia.image for wia in word_image_assocs if hasattr(wia, 'image')]

        # Get background_image_url from the first image association
        background_image_url = None
        if images:
            background_image_url = getattr(images[0], 'image_url', None)

        # Get base word fields
        base_dto = map_word(w)
        base_dict = base_dto.model_dump()

        # Add simplified author fields
        base_dict['author'] = (
            {
                'slug': getattr(author, 'slug', None),
                'username': getattr(author, 'username', None),
                'first_name': getattr(author, 'first_name', None),
                'profile_image_url': getattr(author, 'profile_image_url', None),
            }
            if author is not None
            else None
        )

        # Extract translation objects for the frontend
        word_translations = getattr(w, 'wordtranslations', []) or []
        translations_list = [
            {
                'text': t.translation.text,
                'language': getattr(t.translation.language, 'isocode', None)
                if hasattr(t.translation, 'language')
                else None,
            }
            for t in word_translations
            if hasattr(t, 'translation')
            and t.translation
            and hasattr(t.translation, 'text')
        ]
        base_dict['translations'] = translations_list
        base_dict['translations_count'] = len(translations_list)
        base_dict['background_image_url'] = background_image_url

        # Remove activity_status and activity_progress from published words
        base_dict.pop('activity_status', None)
        base_dict.pop('activity_progress', None)

        dto = WordListWithAuthorOut.model_validate(base_dict)
        results.append(dto)

    return params, total, results


async def published_word_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    word_id: UUID,
    models: dict = VOCAB_MODELS,
):
    Word = models['Word']
    WordTranslation = models['WordTranslation']
    WordTranslations = models['WordTranslations']
    Definition = models['Definition']
    WordDefinitions = models['WordDefinitions']
    UsageExample = models['UsageExample']
    WordUsageExamples = models['WordUsageExamples']
    ImageAssociation = models['ImageAssociation']
    WordImageAssociations = models['WordImageAssociations']
    FavoriteWord = models['FavoriteWord']
    Collection = models['Collection']
    WordsInCollections = models['WordsInCollections']
    Synonym = models['Synonym']

    stmt = (
        select(Word)
        .where(Word.id == word_id)
        .options(
            selectinload(Word.tags),
            selectinload(Word.types),
            selectinload(Word.language),
            selectinload(Word.author).selectinload(User.settings),
            selectinload(Word.source_word).selectinload(Word.author),
        )
    )
    word = (await session.execute(stmt)).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')

    friend_ids: set[UUID] = set()
    if user_id:
        friend_ids = await _get_friend_ids(session, user_id)

    if not _can_view(word.read_access_level, user_id, word.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Word not available')

    # Load translations manually via join table
    translations = (
        (
            await session.execute(
                select(WordTranslation)
                .join(
                    WordTranslations,
                    WordTranslations.translation_id == WordTranslation.id,
                )
                .where(WordTranslations.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )
    definitions = (
        (
            await session.execute(
                select(Definition)
                .join(WordDefinitions, WordDefinitions.definition_id == Definition.id)
                .where(WordDefinitions.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )
    examples = (
        (
            await session.execute(
                select(UsageExample)
                .join(
                    WordUsageExamples, WordUsageExamples.example_id == UsageExample.id
                )
                .where(WordUsageExamples.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )
    images = (
        (
            await session.execute(
                select(ImageAssociation)
                .join(
                    WordImageAssociations,
                    WordImageAssociations.image_id == ImageAssociation.id,
                )
                .where(WordImageAssociations.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )

    word.translations = translations
    word.definitions = definitions
    word.examples = examples
    word.image_associations = images

    if not _can_view(word.read_access_level, user_id, word.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Word not available')

    if user_id:
        fav = (
            await session.execute(
                select(FavoriteWord).where(
                    FavoriteWord.user_id == user_id, FavoriteWord.word_id == word.id
                )
            )
        ).scalar_one_or_none()
        word._favorite = bool(fav)
    else:
        word._favorite = False

    # Build author payload
    author = getattr(word, 'author', None)
    author_payload = None
    if author is not None:
        # allow_subscriptions from settings
        allow_subscriptions = True
        if getattr(author, 'settings', None) is not None:
            allow_subscriptions = bool(author.settings.allow_subscriptions)

        subscribers_count = (
            await session.execute(
                select(func.count())
                .select_from(Subscription)
                .where(Subscription.user_id == author.id)
            )
        ).scalar_one()

        is_subscribed = False
        enable_notifications = False
        if user_id:
            sub = (
                await session.execute(
                    select(Subscription).where(
                        Subscription.subscriber_id == user_id,
                        Subscription.user_id == author.id,
                    )
                )
            ).scalar_one_or_none()
            if sub:
                is_subscribed = True
                enable_notifications = bool(sub.enable_notifications)

        author_payload = {
            'id': author.id,
            'slug': author.slug,
            'username': author.username,
            'first_name': author.first_name,
            'profile_image_url': author.profile_image_url,
            'profile_header_image_url': author.profile_header_image_url,
            'is_official': bool(getattr(author, 'is_official', False)),
            'allow_subscriptions': allow_subscriptions,
            'subscribers_count': subscribers_count,
            'is_subscribed': is_subscribed,
            'enable_notifications': enable_notifications,
        }

    # Collections containing this word
    collections_rows = (
        (
            await session.execute(
                select(Collection)
                .join(
                    WordsInCollections,
                    WordsInCollections.collection_id == Collection.id,
                )
                .where(
                    WordsInCollections.word_id == word.id,
                    Collection.read_access_level.in_(_allowed_levels()),
                )
                .options(selectinload(Collection.author))
            )
        )
        .scalars()
        .all()
    )

    # Collection word counts
    counts = {}
    if collections_rows:
        counts = dict(
            (
                await session.execute(
                    select(WordsInCollections.collection_id, func.count())
                    .where(
                        WordsInCollections.collection_id.in_(
                            [c.id for c in collections_rows]
                        )
                    )
                    .group_by(WordsInCollections.collection_id)
                )
            ).all()
        )

    # Collection languages
    languages_map = {}
    if collections_rows:
        langs_result = await session.execute(
            select(
                WordsInCollections.collection_id,
                func.array_agg(func.distinct(models['Language'].isocode)),
            )
            .join(models['Word'], WordsInCollections.word_id == models['Word'].id)
            .join(
                models['Language'],
                models['Word'].language_id == models['Language'].id,
            )
            .where(
                WordsInCollections.collection_id.in_([c.id for c in collections_rows])
            )
            .group_by(WordsInCollections.collection_id)
        )
        for coll_id, langs in langs_result.all():
            languages_map[coll_id] = [lang for lang in langs if lang]

    # Collection last 4 words
    last_words_map = {}
    if collections_rows:
        from core.utils.urls import get_full_media_url

        for coll_id in [c.id for c in collections_rows]:
            words_stmt = (
                select(models['Word'])
                .join(
                    WordsInCollections,
                    WordsInCollections.word_id == models['Word'].id,
                )
                .where(WordsInCollections.collection_id == coll_id)
                .options(
                    selectinload(models['Word'].wordimageassociations).selectinload(
                        models['WordImageAssociations'].image
                    )
                )
                .order_by(WordsInCollections.created.desc())
                .limit(4)
            )
            words_result = (await session.execute(words_stmt)).scalars().all()
            last_words = []
            for w in words_result:
                word_image_assocs = getattr(w, 'wordimageassociations', []) or []
                image_url = None
                if word_image_assocs:
                    first_assoc = word_image_assocs[0]
                    if hasattr(first_assoc, 'image') and first_assoc.image:
                        image_url = getattr(first_assoc.image, 'image_url', None)
                        if image_url:
                            image_url = get_full_media_url(image_url)
                last_words.append(
                    {
                        'slug': w.slug,
                        'text': w.text,
                        'image': image_url,
                    }
                )
            last_words_map[coll_id] = last_words

    collections = []
    for c in collections_rows:
        c._favorite = False
        c._words_count = counts.get(c.id, 0)
        c._words_languages = languages_map.get(c.id, [])
        c._last_4_words = last_words_map.get(c.id, [])
        collections.append(map_collection(c, for_published=True))

    collections_count = len(collections)

    # Synonyms count (relations)
    synonyms_count = (
        await session.execute(
            select(func.count())
            .select_from(Synonym)
            .where(or_(Synonym.from_word_id == word.id, Synonym.to_word_id == word.id))
        )
    ).scalar_one()

    favorite_for_amount = (
        await session.execute(
            select(func.count())
            .select_from(FavoriteWord)
            .where(FavoriteWord.word_id == word.id)
        )
    ).scalar_one()

    # Comments count
    WordComment = models['WordComment']
    comments_count = (
        await session.execute(
            select(func.count())
            .select_from(WordComment)
            .where(WordComment.word_id == word.id)
        )
    ).scalar_one()

    # Fetch a few comments for the profile (up to 3)
    comments = []
    if comments_count > 0:
        comments_stmt = (
            select(WordComment)
            .where(WordComment.word_id == word.id)
            .order_by(WordComment.created.desc())
            .limit(3)
            .options(
                selectinload(WordComment.likes),
                selectinload(WordComment.dislikes),
                selectinload(WordComment.answers),
                selectinload(WordComment.author),
                selectinload(WordComment.word),
            )
        )
        comments_rows = (await session.execute(comments_stmt)).scalars().all()
        comments = [_map_word_comment(c, user_id) for c in comments_rows]

    base = map_word_read(word).model_dump()
    # Published profile should not expose activity_status or the simple author string,
    # and we override collections/collections_count, synonyms/synonyms_count, and comments/comments_count explicitly below.
    base.pop('activity_status', None)
    base.pop('author', None)
    base.pop('collections', None)
    base.pop('collections_count', None)
    base.pop('synonyms', None)
    base.pop('synonyms_count', None)
    base.pop('comments', None)
    base.pop('comments_count', None)
    # source_word is already included in map_word_read, so keep it
    return WordPublishedProfileOut(
        **base,
        author=author_payload,
        collections=collections,
        collections_count=collections_count,
        synonyms=[],
        synonyms_count=synonyms_count,
        comments_count=comments_count,
        comments=comments,
        favorite_for_amount=favorite_for_amount,
        borrowings_amount=0,
    )


async def published_collections_list_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    params: CollectionsListParams,
    author_ids: Iterable[UUID] | None = None,
    favorite_only: bool = False,
    ordering_override: str | None = None,
    models: dict = VOCAB_MODELS,
):
    Collection = models['Collection']
    Tag = models['Tag']
    WordsInCollections = models['WordsInCollections']
    FavoriteCollection = models['FavoriteCollection']

    allowed_levels = [
        AccessLevelsEnum.PUBLIC,
        AccessLevelsEnum.FRIENDS,
        AccessLevelsEnum.FRIENDS_AND_STUDY_GROUPS,
    ]

    stmt = select(Collection).where(Collection.read_access_level.in_(allowed_levels))
    if author_ids is not None:
        author_ids = list(author_ids)
        if not author_ids:
            return params, 0, []
        stmt = stmt.where(Collection.author_id.in_(author_ids))

    if params.tags:
        stmt = stmt.join(Collection.tags).where(Tag.name.in_(params.tags))
    if favorite_only and user_id:
        stmt = stmt.join(FavoriteCollection).where(
            FavoriteCollection.user_id == user_id
        )

    search_fields = ['title', 'description']
    stmt = apply_search(stmt, Collection, params.search, search_fields)

    ordering_map = {
        'title': Collection.title,
        'created': Collection.created,
        'modified': Collection.modified,
    }
    default_ordering = ordering_override or '-modified'
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default=default_ordering)

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    stmt = stmt.offset(params.offset).limit(params.limit)
    stmt = stmt.options(
        selectinload(Collection.tags),
        selectinload(Collection.author),
    )
    rows: Sequence = (await session.execute(stmt)).scalars().all()

    fav_ids: set[UUID] = set()
    if user_id and rows:
        fav_ids = set(
            (
                await session.execute(
                    select(FavoriteCollection.collection_id).where(
                        FavoriteCollection.user_id == user_id,
                        FavoriteCollection.collection_id.in_([c.id for c in rows]),
                    )
                )
            ).scalars()
        )

    # Get word counts per collection
    counts = {}
    if rows:
        counts = dict(
            (
                await session.execute(
                    select(WordsInCollections.collection_id, func.count())
                    .where(WordsInCollections.collection_id.in_([c.id for c in rows]))
                    .group_by(WordsInCollections.collection_id)
                )
            ).all()
        )

    # Get unique languages per collection
    Word = models['Word']
    Language = models['Language']
    WordImageAssociations = models['WordImageAssociations']

    languages_map = {}
    if rows:
        langs_result = await session.execute(
            select(
                WordsInCollections.collection_id,
                func.array_agg(func.distinct(Language.isocode)),
            )
            .join(Word, WordsInCollections.word_id == Word.id)
            .join(Language, Word.language_id == Language.id)
            .where(WordsInCollections.collection_id.in_([c.id for c in rows]))
            .group_by(WordsInCollections.collection_id)
        )
        for coll_id, langs in langs_result.all():
            languages_map[coll_id] = [lang for lang in langs if lang]

    # Get last 4 words per collection with images
    last_words_map = {}
    if rows:
        from core.utils.urls import get_full_media_url

        for coll_id in [c.id for c in rows]:
            # Get last 4 words for this collection
            words_stmt = (
                select(Word)
                .join(WordsInCollections, WordsInCollections.word_id == Word.id)
                .where(WordsInCollections.collection_id == coll_id)
                .options(
                    selectinload(Word.wordimageassociations).selectinload(
                        WordImageAssociations.image
                    )
                )
                .order_by(WordsInCollections.created.desc())
                .limit(4)
            )
            words_result = (await session.execute(words_stmt)).scalars().all()

            last_words = []
            for word in words_result:
                # Get first image if available
                word_image_assocs = getattr(word, 'wordimageassociations', []) or []
                image_url = None
                if word_image_assocs:
                    first_assoc = word_image_assocs[0]
                    if hasattr(first_assoc, 'image') and first_assoc.image:
                        image_url = getattr(first_assoc.image, 'image_url', None)
                        # Convert to full URL
                        if image_url:
                            image_url = get_full_media_url(image_url)

                last_words.append(
                    {'slug': word.slug, 'text': word.text, 'image': image_url}
                )

            last_words_map[coll_id] = last_words

    results = []
    for c in rows:
        c._favorite = c.id in fav_ids
        c._words_count = counts.get(c.id, 0)
        c._words_languages = languages_map.get(c.id, [])
        c._last_4_words = last_words_map.get(c.id, [])
        results.append(map_collection(c, for_published=True))

    return params, total, results


async def published_collection_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    collection_id: UUID,
    models: dict = VOCAB_MODELS,
) -> CollectionPublishedProfileOut:
    Collection = models['Collection']
    FavoriteCollection = models['FavoriteCollection']
    WordsInCollections = models['WordsInCollections']
    Word = models['Word']
    WordTranslations = models['WordTranslations']
    WordTranslation = models['WordTranslation']
    WordDefinitions = models['WordDefinitions']
    WordUsageExamples = models['WordUsageExamples']
    WordImageAssociations = models['WordImageAssociations']
    CollectionSubscription = models['CollectionSubscription']

    stmt = (
        select(Collection)
        .where(Collection.id == collection_id)
        .options(
            selectinload(Collection.tags),
            selectinload(Collection.author).selectinload(User.settings),
            selectinload(Collection.source_collection).selectinload(Collection.author),
            selectinload(Collection.words_in_collections)
            .selectinload(WordsInCollections.word)
            .selectinload(Word.tags),
            selectinload(Collection.words_in_collections)
            .selectinload(WordsInCollections.word)
            .selectinload(Word.types),
            selectinload(Collection.words_in_collections)
            .selectinload(WordsInCollections.word)
            .selectinload(Word.language),
            selectinload(Collection.words_in_collections)
            .selectinload(WordsInCollections.word)
            .selectinload(Word.wordimageassociations)
            .selectinload(WordImageAssociations.image),
        )
    )
    coll = (await session.execute(stmt)).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    friend_ids: set[UUID] = set()
    if user_id:
        friend_ids = await _get_friend_ids(session, user_id)

    if not _can_view(coll.read_access_level, user_id, coll.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Collection not available')

    if user_id:
        fav = (
            await session.execute(
                select(FavoriteCollection).where(
                    FavoriteCollection.user_id == user_id,
                    FavoriteCollection.collection_id == coll.id,
                )
            )
        ).scalar_one_or_none()
        coll._favorite = bool(fav)
    else:
        coll._favorite = False

    # Build author payload
    author = getattr(coll, 'author', None)
    author_payload = None
    if author is not None:
        allow_subscriptions = True
        if getattr(author, 'settings', None) is not None:
            allow_subscriptions = bool(author.settings.allow_subscriptions)

        subscribers_count = (
            await session.execute(
                select(func.count())
                .select_from(CollectionSubscription)
                .where(CollectionSubscription.collection_id == coll.id)
            )
        ).scalar_one()

        subscribed = False
        enable_notifications = False
        # new_words = []
        # updated_words = []
        if user_id:
            sub = (
                await session.execute(
                    select(CollectionSubscription).where(
                        CollectionSubscription.subscriber_id == user_id,
                        CollectionSubscription.collection_id == coll.id,
                    )
                )
            ).scalar_one_or_none()
            if sub:
                subscribed = True
                enable_notifications = bool(sub.enable_notifications)
                # new_words/updated_words are stored as text, keep empty if not parsable
                # new_words = []
                # updated_words = []

        author_payload = {
            'id': author.id,
            'slug': author.slug,
            'username': author.username,
            'first_name': author.first_name,
            'profile_image_url': author.profile_image_url,
            'profile_header_image_url': author.profile_header_image_url,
            'is_official': bool(getattr(author, 'is_official', False)),
            'allow_subscriptions': allow_subscriptions,
            'subscribers_count': subscribers_count,
            'is_subscribed': subscribed,
            'enable_notifications': enable_notifications,
        }

    # Word IDs in collection
    words_in_coll = getattr(coll, 'words_in_collections', []) or []
    word_ids = [w.word_id for w in words_in_coll]

    # Words count and languages
    words_count = len(words_in_coll)
    words_languages = []
    if words_in_coll:
        words_languages = list(
            {
                w.word.language.isocode
                for w in words_in_coll
                if getattr(w.word, 'language', None) is not None
            }
        )

    # Translations per word
    translations_map: dict[UUID, list[str]] = {}
    if word_ids:
        rows = (
            await session.execute(
                select(WordTranslations.word_id, WordTranslation.text)
                .join(
                    WordTranslation,
                    WordTranslations.translation_id == WordTranslation.id,
                )
                .where(WordTranslations.word_id.in_(word_ids))
            )
        ).all()
        for word_id, text in rows:
            translations_map.setdefault(word_id, []).append(text)

    # Words texts mapping
    words_texts: dict[str, list[str]] = {}
    for w in words_in_coll:
        words_texts[w.word.text] = translations_map.get(w.word_id, [])

    # Words images (first image per word)
    words_images: list[str] = []
    from core.utils.urls import get_full_media_url

    for w in words_in_coll:
        word_image_assocs = getattr(w.word, 'wordimageassociations', []) or []
        if word_image_assocs:
            first_assoc = word_image_assocs[0]
            if hasattr(first_assoc, 'image') and first_assoc.image:
                image_url = getattr(first_assoc.image, 'image_url', None)
                if image_url:
                    words_images.append(get_full_media_url(image_url))

    words_images_count = len(words_images)
    words_translations_count = sum(len(v) for v in translations_map.values())

    # Definitions / examples count
    words_definitions_count = 0
    words_examples_count = 0
    if word_ids:
        words_definitions_count = (
            await session.execute(
                select(func.count())
                .select_from(WordDefinitions)
                .where(WordDefinitions.word_id.in_(word_ids))
            )
        ).scalar_one()
        words_examples_count = (
            await session.execute(
                select(func.count())
                .select_from(WordUsageExamples)
                .where(WordUsageExamples.word_id.in_(word_ids))
            )
        ).scalar_one()

    # Favorite count for collection
    favorite_for_amount = (
        await session.execute(
            select(func.count())
            .select_from(FavoriteCollection)
            .where(FavoriteCollection.collection_id == coll.id)
        )
    ).scalar_one()

    # Borrowings count
    borrowings_amount = (
        await session.execute(
            select(func.count())
            .select_from(Collection)
            .where(Collection.source_collection_id == coll.id)
        )
    ).scalar_one()

    # Comments count
    comments_count = (
        await session.execute(
            select(func.count())
            .select_from(CollectionComment)
            .where(CollectionComment.collection_id == coll.id)
        )
    ).scalar_one()

    # Fetch a few comments for the profile (up to 3)
    comments = []
    if comments_count > 0:
        comments_stmt = (
            select(CollectionComment)
            .where(CollectionComment.collection_id == coll.id)
            .order_by(CollectionComment.created.desc())
            .limit(3)
            .options(
                selectinload(CollectionComment.likes),
                selectinload(CollectionComment.dislikes),
                selectinload(CollectionComment.answers),
                selectinload(CollectionComment.author),
                selectinload(CollectionComment.collection),
            )
        )
        comments_rows = (await session.execute(comments_stmt)).scalars().all()
        comments = [_map_comment(c, user_id) for c in comments_rows]

    # Suggestions count (only PENDING)
    Suggested = models['WordsSuggestedToCollections']
    suggestions_count = (
        await session.execute(
            select(func.count())
            .select_from(Suggested)
            .where(
                Suggested.collection_id == coll.id,
                Suggested.status == RequestStatusEnum.PENDING,
            )
        )
    ).scalar_one()

    # Suggestions approved/rejected counts (for author)
    suggestions_approved_count = 0
    suggestions_rejected_count = 0
    if user_id and coll.author_id == user_id:
        suggestions_approved_count = (
            await session.execute(
                select(func.count())
                .select_from(Suggested)
                .where(
                    Suggested.collection_id == coll.id,
                    Suggested.status == RequestStatusEnum.APPROVED,
                )
            )
        ).scalar_one()
        suggestions_rejected_count = (
            await session.execute(
                select(func.count())
                .select_from(Suggested)
                .where(
                    Suggested.collection_id == coll.id,
                    Suggested.status == RequestStatusEnum.REJECTED,
                )
            )
        ).scalar_one()

    # Build source_collection payload if collection is borrowed
    source_collection_payload = None
    source_collection_obj = getattr(coll, 'source_collection', None)
    if source_collection_obj is not None:
        from api.v1.published.schemas import SourceCollectionOut

        source_collection_author_obj = getattr(source_collection_obj, 'author', None)
        source_collection_author_payload = None
        if source_collection_author_obj is not None:
            source_collection_author_payload = {
                'id': source_collection_author_obj.id,
                'slug': source_collection_author_obj.slug,
                'username': source_collection_author_obj.username,
                'first_name': source_collection_author_obj.first_name,
                'profile_image_url': source_collection_author_obj.profile_image_url,
                'profile_header_image_url': source_collection_author_obj.profile_header_image_url,
                'is_official': bool(
                    getattr(source_collection_author_obj, 'is_official', False)
                ),
            }
        source_collection_payload = SourceCollectionOut(
            id=source_collection_obj.id,
            slug=source_collection_obj.slug,
            title=source_collection_obj.title,
            author=source_collection_author_payload,
        )

    return CollectionPublishedProfileOut(
        id=coll.id,
        slug=coll.slug,
        author=author_payload,
        title=coll.title,
        description=coll.description,
        favorite=coll._favorite,
        created=coll.created,
        modified=coll.modified,
        source_collection=source_collection_payload,
        words_languages=words_languages,
        words_count=words_count,
        words_texts=words_texts,
        words_images=words_images,
        words_images_count=words_images_count,
        words_translations_count=words_translations_count,
        words_definitions_count=words_definitions_count,
        words_examples_count=words_examples_count,
        translations=None,
        image_associations=None,
        definitions=None,
        examples=None,
        read_access_level=coll.read_access_level,
        add_access_level=coll.add_access_level,
        borrowings_amount=borrowings_amount,
        favorite_for_amount=favorite_for_amount,
        views_amount=0,
        last_viewed=None,
        borrowed=bool(coll.source_collection_id),
        borrow_new_words_count=0,
        subscribers_count=author_payload['subscribers_count'] if author_payload else 0,
        subscribed=author_payload['is_subscribed'] if author_payload else False,
        enable_notifications=author_payload['enable_notifications']
        if author_payload
        else False,
        new_words=[],
        updated_words=[],
        last_word_added=None,
        allow_comments=bool(coll.allow_comments),
        comments_count=comments_count,
        comments=comments,
        allow_suggestions=bool(coll.allow_suggestions),
        allow_suggestions_notifications=bool(coll.allow_suggestions_notifications),
        suggestions_count=suggestions_count,
        suggestions_approved_count=suggestions_approved_count,
        suggestions_rejected_count=suggestions_rejected_count,
        disallow_suggestions_for=False,
        suggestions=[],  # Empty - fetch separately via suggested-words endpoint
    )


def _allowed_levels():
    return [
        AccessLevelsEnum.PUBLIC,
        AccessLevelsEnum.FRIENDS,
        AccessLevelsEnum.FRIENDS_AND_STUDY_GROUPS,
    ]


async def published_word_resolve_slug_service(
    *,
    session: AsyncSession,
    slug: str,
    models: dict = VOCAB_MODELS,
) -> WordResolveOut:
    Word = models['Word']
    row = (
        await session.execute(
            select(Word.id, Word.slug).where(
                Word.slug == slug,
                Word.read_access_level.in_(_allowed_levels()),
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Word not found')
    return WordResolveOut(id=row.id, slug=row.slug)


async def published_collection_resolve_slug_service(
    *,
    session: AsyncSession,
    slug: str,
    models: dict = VOCAB_MODELS,
) -> CollectionResolveOut:
    Collection = models['Collection']
    row = (
        await session.execute(
            select(Collection.id, Collection.slug).where(
                Collection.slug == slug,
                Collection.read_access_level.in_(_allowed_levels()),
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Collection not found')
    return CollectionResolveOut(id=row.id, slug=row.slug)


async def published_collection_words_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    collection_id: UUID,
    page: int,
    limit: int,
    models: dict = VOCAB_MODELS,
) -> WordsWithAuthorPageOut:
    Collection = models['Collection']
    Word = models['Word']
    WordsInCollections = models['WordsInCollections']
    FavoriteWord = models['FavoriteWord']

    coll = (
        await session.execute(
            select(Collection)
            .options(selectinload(Collection.words_in_collections))
            .where(Collection.id == collection_id)
        )
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    friend_ids: set[UUID] = set()
    if user_id:
        friend_ids = await _get_friend_ids(session, user_id)

    if not _can_view(coll.read_access_level, user_id, coll.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Collection not available')

    page, limit, offset = normalize_pagination(page, limit)

    stmt = (
        select(Word)
        .join(WordsInCollections, WordsInCollections.word_id == Word.id)
        .where(
            WordsInCollections.collection_id == coll.id,
            Word.read_access_level.in_(_allowed_levels()),
        )
        .order_by(WordsInCollections.created.desc())
    )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    stmt = (
        stmt.offset(offset)
        .limit(limit)
        .options(
            selectinload(Word.tags),
            selectinload(Word.types),
            selectinload(Word.language),
            selectinload(Word.translations),
        )
    )
    rows: Sequence = (await session.execute(stmt)).scalars().all()

    fav_ids: set[UUID] = set()
    if user_id and rows:
        fav_ids = set(
            (
                await session.execute(
                    select(FavoriteWord.word_id).where(
                        FavoriteWord.user_id == user_id,
                        FavoriteWord.word_id.in_([w.id for w in rows]),
                    )
                )
            ).scalars()
        )

    results = []
    for w in rows:
        w._favorite = w.id in fav_ids
        results.append(map_word(w))

    return WordsWithAuthorPageOut(page=page, limit=limit, count=total, results=results)


async def published_word_borrow_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    models: dict = VOCAB_MODELS,
) -> dict:
    Word = models['Word']
    WordTranslations = models['WordTranslations']
    WordDefinitions = models['WordDefinitions']
    WordUsageExamples = models['WordUsageExamples']
    WordImageAssociations = models['WordImageAssociations']

    # Load source word with language; we only need primitive values for copy
    src = (
        await session.execute(
            select(Word).options(selectinload(Word.language)).where(Word.id == word_id)
        )
    ).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail='Word not found')

    # Cache primitive fields BEFORE we start transaction work, so we don't
    # trigger lazy loads on an expired `src` inside exception handlers.
    src_text = src.text
    src_language_id = src.language_id

    # Create a "borrowed" copy of the word, similar to save_word_copy in DRF:
    # - keep text/language
    # - set new author
    # - link to source_word
    # - reset activity fields
    # - make it private and disallow access change
    new_word = Word(
        text=src_text,
        language_id=src_language_id,
        author_id=user_id,
        source_word_id=src.id,
        is_premium=False,
        activity_status=ActivityStatusEnum.INACTIVE,
        activity_progress=ActivityStatusEnum.activity_progress_default,
        read_access_level=AccessLevelsEnum.PRIVATE,
        add_access_level=AccessLevelsEnum.PRIVATE,
        allow_access_change=False,
    )

    try:
        session.add(new_word)
        # Flush so new_word gets an ID but stay in the same transaction
        try:
            await session.flush()
        except IntegrityError as flush_exc:
            await session.rollback()
            # In borrow context, any IntegrityError here is from the unique
            # index (unique_words_in_user_voc). Treat it as "already_exist".
            error_msg = (
                str(flush_exc.orig) if hasattr(flush_exc, 'orig') else str(flush_exc)
            )
            is_unique_violation = (
                'unique_words_in_user_voc' in error_msg
                or 'unique' in error_msg.lower()
                or 'duplicate' in error_msg.lower()
                or (
                    hasattr(flush_exc, 'orig')
                    and isinstance(flush_exc.orig, UniqueViolationError)
                )
            )

            if not is_unique_violation:
                raise

            # Find the existing word and raise HTTPException
            existing_word = (
                await session.execute(
                    select(Word)
                    .options(selectinload(Word.language))
                    .where(
                        Word.text == src_text,
                        Word.author_id == user_id,
                        Word.language_id == src_language_id,
                    )
                )
            ).scalar_one_or_none()

            if existing_word:
                existing_word_dto = map_word_read(existing_word)
                raise HTTPException(
                    status_code=409,
                    detail={
                        'exception_code': 'already_exist',
                        'detail': 'Word already exists in your vocabulary',
                        'existing_object': existing_word_dto.model_dump(mode='json'),
                    },
                ) from flush_exc
            else:
                raise HTTPException(
                    status_code=409,
                    detail={
                        'exception_code': 'already_exist',
                        'detail': 'Word already exists in your vocabulary',
                    },
                ) from flush_exc

        # Copy translations associations
        src_translations = (
            await session.execute(
                select(WordTranslations.translation_id).where(
                    WordTranslations.word_id == src.id
                )
            )
        ).scalars()
        for tr_id in src_translations:
            session.add(WordTranslations(word_id=new_word.id, translation_id=tr_id))

        # Copy definitions associations
        src_definitions = (
            await session.execute(
                select(WordDefinitions.definition_id).where(
                    WordDefinitions.word_id == src.id
                )
            )
        ).scalars()
        for def_id in src_definitions:
            session.add(WordDefinitions(word_id=new_word.id, definition_id=def_id))

        # Copy usage examples associations
        src_examples = (
            await session.execute(
                select(WordUsageExamples.example_id).where(
                    WordUsageExamples.word_id == src.id
                )
            )
        ).scalars()
        for ex_id in src_examples:
            session.add(WordUsageExamples(word_id=new_word.id, example_id=ex_id))

        # Copy image associations
        src_images = (
            await session.execute(
                select(WordImageAssociations.image_id).where(
                    WordImageAssociations.word_id == src.id
                )
            )
        ).scalars()
        for img_id in src_images:
            session.add(WordImageAssociations(word_id=new_word.id, image_id=img_id))

        await session.commit()
    except IntegrityError as exc:
        # Any integrity error here means the word already exists in user's vocabulary
        await session.rollback()

        error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
        is_unique_violation = (
            'unique_words_in_user_voc' in error_msg
            or 'unique' in error_msg.lower()
            or 'duplicate' in error_msg.lower()
            or (hasattr(exc, 'orig') and isinstance(exc.orig, UniqueViolationError))
        )

        if not is_unique_violation:
            raise

        # Find the existing word with same text, author, and language
        existing_word = (
            await session.execute(
                select(Word)
                .options(
                    selectinload(Word.language),
                    selectinload(Word.source_word).selectinload(Word.author),
                )
                .where(
                    Word.text == src_text,
                    Word.author_id == user_id,
                    Word.language_id == src_language_id,
                )
            )
        ).scalar_one_or_none()

        if existing_word:
            existing_word_dto = map_word_read(existing_word)
            raise HTTPException(
                status_code=409,
                detail={
                    'exception_code': 'already_exist',
                    'detail': 'Word already exists in your vocabulary',
                    'existing_object': existing_word_dto.model_dump(mode='json'),
                },
            ) from exc
        else:
            raise HTTPException(
                status_code=409,
                detail={
                    'exception_code': 'already_exist',
                    'detail': 'Word already exists in your vocabulary',
                },
            ) from exc

    await session.refresh(new_word)
    # Reload word with all relationships including source_word
    new_word = (
        await session.execute(
            select(Word)
            .where(Word.id == new_word.id)
            .options(
                selectinload(Word.tags),
                selectinload(Word.types),
                selectinload(Word.language),
                selectinload(Word.author),
                selectinload(Word.source_word).selectinload(Word.author),
            )
        )
    ).scalar_one()
    return map_word_read(new_word)


async def published_word_favorite_toggle_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
) -> dict:
    Word = VOCAB_MODELS['Word']
    src = (
        await session.execute(select(Word).where(Word.id == word_id))
    ).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail='Word not found')
    return await word_favorite_toggle_service(
        session=session, word_id=src.id, user_id=user_id, author_only=False
    )


async def published_translation_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    translation_id: UUID,
    models: dict = VOCAB_MODELS,
) -> TranslationOut:
    WordTranslation = models['WordTranslation']
    Word = models['Word']
    WordTranslations = models['WordTranslations']

    row = (
        await session.execute(
            select(WordTranslation, Word)
            .join(
                WordTranslations, WordTranslations.translation_id == WordTranslation.id
            )
            .join(Word, Word.id == WordTranslations.word_id)
            .where(WordTranslation.id == translation_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Translation not found')
    translation, word = row

    friend_ids: set[UUID] = set()
    if user_id:
        friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(word.read_access_level, user_id, word.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Translation not available')

    return TranslationOut(
        id=translation.id,
        slug=translation.slug,
        text=translation.text,
        language=getattr(translation.language, 'isocode', None)
        if hasattr(translation, 'language')
        else None,
        created=translation.created,
        modified=translation.modified,
    )


async def published_definition_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    definition_id: UUID,
    models: dict = VOCAB_MODELS,
) -> DefinitionOut:
    Definition = models['Definition']
    Word = models['Word']
    WordDefinitions = models['WordDefinitions']

    row = (
        await session.execute(
            select(Definition, Word)
            .join(WordDefinitions, WordDefinitions.definition_id == Definition.id)
            .join(Word, Word.id == WordDefinitions.word_id)
            .where(Definition.id == definition_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Definition not found')
    definition, word = row

    friend_ids: set[UUID] = set()
    if user_id:
        friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(word.read_access_level, user_id, word.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Definition not available')

    return DefinitionOut.model_validate(definition)


async def published_example_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    example_id: UUID,
    models: dict = VOCAB_MODELS,
) -> ExampleOut:
    UsageExample = models['UsageExample']
    Word = models['Word']
    WordUsageExamples = models['WordUsageExamples']

    row = (
        await session.execute(
            select(UsageExample, Word)
            .join(WordUsageExamples, WordUsageExamples.example_id == UsageExample.id)
            .join(Word, Word.id == WordUsageExamples.word_id)
            .where(UsageExample.id == example_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Example not found')
    example, word = row

    friend_ids: set[UUID] = set()
    if user_id:
        friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(word.read_access_level, user_id, word.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Example not available')

    return ExampleOut.model_validate(example)


async def published_image_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    image_id: UUID,
    models: dict = VOCAB_MODELS,
) -> ImageOut:
    ImageAssociation = models['ImageAssociation']
    Word = models['Word']
    WordImageAssociations = models['WordImageAssociations']

    row = (
        await session.execute(
            select(ImageAssociation, Word)
            .join(
                WordImageAssociations,
                WordImageAssociations.image_id == ImageAssociation.id,
            )
            .join(Word, Word.id == WordImageAssociations.word_id)
            .where(ImageAssociation.id == image_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Image not found')
    image, word = row

    friend_ids: set[UUID] = set()
    if user_id:
        friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(word.read_access_level, user_id, word.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Image not available')

    return ImageOut.model_validate(image)


async def published_synonyms_list_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    page: int,
    limit: int,
) -> WordsWithAuthorPageOut:
    # Not enough data to expose synonyms separately; return empty list to keep endpoint functional.
    page, limit, _ = normalize_pagination(page, limit)
    return WordsWithAuthorPageOut(page=page, limit=limit, count=0, results=[])


async def published_synonym_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    word_id: UUID,
) -> WordReadOut:
    # Synonym detail not implemented; mirror empty response with not found.
    raise HTTPException(status_code=404, detail='Synonym not found')


async def published_collection_subscribe_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    notifications: bool | None = None,
    models: dict = VOCAB_MODELS,
) -> CollectionPublishedProfileOut:
    Collection = models['Collection']

    # Load collection minimally for access check
    coll = (
        await session.execute(select(Collection).where(Collection.id == collection_id))
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    # access check
    friend_ids: set[UUID] = set()
    friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(coll.read_access_level, user_id, coll.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Collection not available')

    sub = (
        await session.execute(
            select(CollectionSubscription).where(
                CollectionSubscription.collection_id == coll.id,
                CollectionSubscription.subscriber_id == user_id,
            )
        )
    ).scalar_one_or_none()

    # DRF behavior:
    # - If "notifications" query param is present, only toggle enable_notifications
    #   on an existing subscription (do not subscribe/unsubscribe).
    # - Otherwise, toggle the subscription itself (create/delete).
    if notifications is not None:
        if not sub:
            # Mirror DRF get_object_or_404 behavior when trying to toggle
            # notifications without an existing subscription.
            raise HTTPException(status_code=404, detail='Subscription not found')

        sub.enable_notifications = not bool(sub.enable_notifications)
        await session.commit()
    else:
        if sub:
            # Toggle off subscription
            await session.delete(sub)
            await session.commit()
        else:
            # Create subscription with notifications enabled by default
            sub = CollectionSubscription(
                subscriber_id=user_id,
                collection_id=coll.id,
                enable_notifications=True,
            )
            session.add(sub)
            await session.commit()

    # After any change, reuse the published collection detail service
    # to return a fully populated published collection profile.
    return await published_collection_detail_service(
        session=session, user_id=user_id, collection_id=collection_id, models=models
    )


def _format_relative_time(dt: datetime | None) -> str:
    """Format datetime as relative time string (e.g., '2 hours ago')."""
    if not dt:
        return ''

    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = now - dt

    if delta.total_seconds() < 60:
        return 'just now'
    elif delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() / 60)
        return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    elif delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() / 3600)
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    elif delta.total_seconds() < 604800:
        days = int(delta.total_seconds() / 86400)
        return f'{days} day{"s" if days != 1 else ""} ago'
    elif delta.total_seconds() < 2592000:
        weeks = int(delta.total_seconds() / 604800)
        return f'{weeks} week{"s" if weeks != 1 else ""} ago'
    elif delta.total_seconds() < 31536000:
        months = int(delta.total_seconds() / 2592000)
        return f'{months} month{"s" if months != 1 else ""} ago'
    else:
        years = int(delta.total_seconds() / 31536000)
        return f'{years} year{"s" if years != 1 else ""} ago'


def _map_comment(
    comment: CollectionComment, user_id: UUID | None = None
) -> CollectionCommentOut:
    likes = getattr(comment, 'likes', []) or []
    dislikes = getattr(comment, 'dislikes', []) or []
    answers = getattr(comment, 'answers', []) or []

    author = getattr(comment, 'author', None)
    collection = getattr(comment, 'collection', None)

    liked_by_user = False
    disliked_by_user = False
    if user_id:
        liked_by_user = any(u.id == user_id for u in likes)
        disliked_by_user = any(u.id == user_id for u in dislikes)

    author_dict = None
    if author:
        # Build a plain dict so that the target CollectionCommentOut schema
        # (which uses its own AuthorShortOut from collections.schemas)
        # can construct the proper model instance without class mismatch.
        author_dict = {
            'slug': getattr(author, 'slug', ''),
            'username': getattr(author, 'username', ''),
            'first_name': getattr(author, 'first_name', None),
            'profile_image_url': getattr(author, 'profile_image_url', None),
        }

    return CollectionCommentOut(
        id=comment.id,
        collection=getattr(collection, 'slug', '') if collection else '',
        author=author_dict,
        text=comment.text,
        author_liked=bool(comment.author_liked),
        liked_by_user=liked_by_user,
        disliked_by_user=disliked_by_user,
        likes_count=len(likes),
        dislikes_count=len(dislikes),
        answers_count=len(answers),
        modified_relative=_format_relative_time(comment.modified or comment.created),
        text_modified=bool(comment.text_modified),
    )


def _map_word_comment(
    comment: WordComment, user_id: UUID | None = None
) -> WordCommentOut:
    likes = getattr(comment, 'likes', []) or []
    dislikes = getattr(comment, 'dislikes', []) or []
    answers = getattr(comment, 'answers', []) or []

    author = getattr(comment, 'author', None)
    word = getattr(comment, 'word', None)

    liked_by_user = False
    disliked_by_user = False
    if user_id:
        liked_by_user = any(u.id == user_id for u in likes)
        disliked_by_user = any(u.id == user_id for u in dislikes)

    author_dict = None
    if author:
        # Same as in _map_comment: build a plain dict so that the
        # WordCommentOut schema (imported from vocabulary.schemas)
        # can construct its own AuthorShortOut instance correctly.
        author_dict = {
            'slug': getattr(author, 'slug', ''),
            'username': getattr(author, 'username', ''),
            'first_name': getattr(author, 'first_name', None),
            'profile_image_url': getattr(author, 'profile_image_url', None),
        }

    return WordCommentOut(
        id=comment.id,
        word_id=getattr(comment, 'word_id', None) or (word.id if word else None),
        author_id=getattr(comment, 'author_id', None)
        or (author.id if author else None),
        author=author_dict,
        text=comment.text,
        author_liked=bool(comment.author_liked),
        liked_by_user=liked_by_user,
        disliked_by_user=disliked_by_user,
        likes_count=len(likes),
        dislikes_count=len(dislikes),
        answers_count=len(answers),
        created=getattr(comment, 'created', None),
        modified=getattr(comment, 'modified', None),
        modified_relative=_format_relative_time(comment.modified or comment.created),
        text_modified=bool(comment.text_modified),
    )


async def published_collection_comments_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    page: int,
    limit: int,
    models: dict = VOCAB_MODELS,
) -> CollectionCommentsPageOut:
    Collection = models['Collection']
    CollectionComment = models['CollectionComment']

    coll = (
        await session.execute(select(Collection).where(Collection.id == collection_id))
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(coll.read_access_level, user_id, coll.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Collection not available')

    page, limit, offset = normalize_pagination(page, limit)
    stmt = (
        select(CollectionComment)
        .where(CollectionComment.collection_id == collection_id)
        .order_by(CollectionComment.created.desc())
        .options(
            selectinload(CollectionComment.likes),
            selectinload(CollectionComment.dislikes),
            selectinload(CollectionComment.answers),
            selectinload(CollectionComment.author),
            selectinload(CollectionComment.collection),
        )
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows: Sequence = (
        (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    )
    results = [_map_comment(c, user_id) for c in rows]

    # Build pagination links
    from api.v1.utils.pagination import build_pagination_links

    next_link, previous_link = build_pagination_links(
        base_url=f'/published/collections/{collection_id}/comments',
        page=page,
        limit=limit,
        total=total,
    )

    return CollectionCommentsPageOut(
        count=total, next=next_link, previous=previous_link, results=results
    )


async def published_collection_comment_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    text: str,
    page: int = 1,
    limit: int = 32,
    models: dict = VOCAB_MODELS,
) -> CollectionCommentsPageOut:
    Collection = models['Collection']
    CollectionComment = models['CollectionComment']

    coll = (
        await session.execute(select(Collection).where(Collection.id == collection_id))
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(coll.read_access_level, user_id, coll.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Collection not available')

    comment = CollectionComment(
        collection_id=collection_id, author_id=user_id, text=text
    )
    session.add(comment)
    await session.commit()

    # Return paginated comments list
    page, limit, offset = normalize_pagination(page, limit)
    stmt = (
        select(CollectionComment)
        .where(CollectionComment.collection_id == collection_id)
        .order_by(CollectionComment.created.desc())
        .options(
            selectinload(CollectionComment.likes),
            selectinload(CollectionComment.dislikes),
            selectinload(CollectionComment.answers),
            selectinload(CollectionComment.author),
            selectinload(CollectionComment.collection),
        )
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows: Sequence = (
        (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    )
    results = [_map_comment(c, user_id) for c in rows]

    # Build pagination links
    from api.v1.utils.pagination import build_pagination_links

    next_link, previous_link = build_pagination_links(
        base_url=f'/published/collections/{collection_id}/comments',
        page=page,
        limit=limit,
        total=total,
    )

    return CollectionCommentsPageOut(
        count=total, next=next_link, previous=previous_link, results=results
    )


async def published_collection_comment_patch_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    text: str,
    models: dict = VOCAB_MODELS,
) -> CollectionCommentOut:
    CollectionComment = models['CollectionComment']

    comment = (
        await session.execute(
            select(CollectionComment)
            .options(
                selectinload(CollectionComment.likes),
                selectinload(CollectionComment.dislikes),
                selectinload(CollectionComment.answers),
            )
            .where(CollectionComment.id == comment_id)
        )
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail='Comment not found')
    if comment.author_id != user_id:
        raise HTTPException(status_code=403, detail='Forbidden')

    comment.text = text
    comment.text_modified = True
    await session.commit()
    await session.refresh(comment)
    # Reload with relationships
    comment = (
        await session.execute(
            select(CollectionComment)
            .options(
                selectinload(CollectionComment.likes),
                selectinload(CollectionComment.dislikes),
                selectinload(CollectionComment.answers),
                selectinload(CollectionComment.author),
                selectinload(CollectionComment.collection),
            )
            .where(CollectionComment.id == comment.id)
        )
    ).scalar_one()
    return _map_comment(comment, user_id)


async def published_collection_comment_delete_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    models: dict = VOCAB_MODELS,
) -> None:
    CollectionComment = models['CollectionComment']
    comment = (
        await session.execute(
            select(CollectionComment).where(CollectionComment.id == comment_id)
        )
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail='Comment not found')
    if comment.author_id != user_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    await session.delete(comment)
    await session.commit()


async def _toggle_reaction(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    reaction: str,
    models: dict = VOCAB_MODELS,
) -> CollectionCommentOut:
    CollectionComment = models['CollectionComment']
    Collection = models['Collection']
    comment = (
        await session.execute(
            select(CollectionComment)
            .options(
                selectinload(CollectionComment.likes),
                selectinload(CollectionComment.dislikes),
                selectinload(CollectionComment.answers),
                selectinload(CollectionComment.collection),
            )
            .where(CollectionComment.id == comment_id)
        )
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail='Comment not found')

    # Check if user has access to the collection
    coll = (
        comment.collection
        or (
            await session.execute(
                select(Collection).where(Collection.id == comment.collection_id)
            )
        ).scalar_one_or_none()
    )
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(coll.read_access_level, user_id, coll.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Collection not available')

    # Fetch the user to add to likes/dislikes
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')

    # remove opposite reaction
    if reaction == 'like':
        comment.dislikes = [u for u in comment.dislikes if u.id != user_id]
        if any(u.id == user_id for u in comment.likes):
            comment.likes = [u for u in comment.likes if u.id != user_id]
        else:
            comment.likes.append(user)
    elif reaction == 'dislike':
        comment.likes = [u for u in comment.likes if u.id != user_id]
        if any(u.id == user_id for u in comment.dislikes):
            comment.dislikes = [u for u in comment.dislikes if u.id != user_id]
        else:
            comment.dislikes.append(user)

    await session.commit()
    await session.refresh(comment)
    # Reload with relationships
    comment = (
        await session.execute(
            select(CollectionComment)
            .options(
                selectinload(CollectionComment.likes),
                selectinload(CollectionComment.dislikes),
                selectinload(CollectionComment.answers),
                selectinload(CollectionComment.author),
                selectinload(CollectionComment.collection),
            )
            .where(CollectionComment.id == comment.id)
        )
    ).scalar_one()
    return _map_comment(comment, user_id)


async def published_collection_comment_like_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    models: dict = VOCAB_MODELS,
) -> CollectionCommentOut:
    return await _toggle_reaction(
        session=session,
        user_id=user_id,
        comment_id=comment_id,
        reaction='like',
        models=models,
    )


async def published_collection_comment_dislike_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    models: dict = VOCAB_MODELS,
) -> CollectionCommentOut:
    return await _toggle_reaction(
        session=session,
        user_id=user_id,
        comment_id=comment_id,
        reaction='dislike',
        models=models,
    )


async def published_collection_comment_author_like_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    models: dict = VOCAB_MODELS,
) -> CollectionCommentOut:
    CollectionComment = models['CollectionComment']
    Collection = models['Collection']

    comment = (
        await session.execute(
            select(CollectionComment)
            .options(selectinload(CollectionComment.collection))
            .where(CollectionComment.id == comment_id)
        )
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail='Comment not found')
    coll = (
        comment.collection
        or (
            await session.execute(
                select(Collection).where(Collection.id == comment.collection_id)
            )
        ).scalar_one()
    )
    if coll.author_id != user_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    comment.author_liked = not bool(comment.author_liked)
    await session.commit()
    await session.refresh(comment)
    # Reload with relationships
    comment = (
        await session.execute(
            select(CollectionComment)
            .options(
                selectinload(CollectionComment.likes),
                selectinload(CollectionComment.dislikes),
                selectinload(CollectionComment.answers),
                selectinload(CollectionComment.author),
                selectinload(CollectionComment.collection),
            )
            .where(CollectionComment.id == comment.id)
        )
    ).scalar_one()
    return _map_comment(comment, user_id)


async def published_collection_comment_answers_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    page: int,
    limit: int,
    models: dict = VOCAB_MODELS,
) -> CollectionCommentsPageOut:
    CollectionComment = models['CollectionComment']

    parent = (
        await session.execute(
            select(CollectionComment)
            .options(selectinload(CollectionComment.answers))
            .where(CollectionComment.id == comment_id)
        )
    ).scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail='Comment not found')

    page, limit, offset = normalize_pagination(page, limit)
    answers = parent.answers or []
    total = len(answers)
    sliced = answers[offset : offset + limit]
    results = [_map_comment(a, user_id) for a in sliced]
    # Answers list doesn't need pagination links (it's a simple list)
    return CollectionCommentsPageOut(
        count=total, next=None, previous=None, results=results
    )


async def published_collection_comment_answer_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    text: str,
    models: dict = VOCAB_MODELS,
) -> CollectionCommentOut:
    CollectionComment = models['CollectionComment']

    parent = (
        await session.execute(
            select(CollectionComment).where(CollectionComment.id == comment_id)
        )
    ).scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail='Comment not found')

    reply = CollectionComment(
        collection_id=parent.collection_id,
        author_id=user_id,
        text=text,
    )
    session.add(reply)
    await session.flush()
    parent.answers.append(reply)
    await session.commit()
    await session.refresh(reply)
    # Reload with relationships
    reply = (
        await session.execute(
            select(CollectionComment)
            .options(
                selectinload(CollectionComment.likes),
                selectinload(CollectionComment.dislikes),
                selectinload(CollectionComment.answers),
                selectinload(CollectionComment.author),
                selectinload(CollectionComment.collection),
            )
            .where(CollectionComment.id == reply.id)
        )
    ).scalar_one()
    return _map_comment(reply, user_id)


# ----------------------------
# Word comments (published)
# ----------------------------


async def published_word_comments_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    page: int,
    limit: int,
    models: dict = VOCAB_MODELS,
) -> WordCommentsPageOut:
    Word = models['Word']
    WordComment = models['WordComment']

    word = (
        await session.execute(select(Word).where(Word.id == word_id))
    ).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')
    friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(word.read_access_level, user_id, word.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Word not available')

    page, limit, offset = normalize_pagination(page, limit)
    stmt = (
        select(WordComment)
        .where(WordComment.word_id == word_id)
        .order_by(WordComment.created.desc())
        .options(
            selectinload(WordComment.likes),
            selectinload(WordComment.dislikes),
            selectinload(WordComment.answers),
            selectinload(WordComment.author),
            selectinload(WordComment.word),
        )
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows: Sequence = (
        (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    )
    results = [_map_word_comment(c, user_id) for c in rows]

    # Build pagination links
    from api.v1.utils.pagination import build_pagination_links

    next_link, previous_link = build_pagination_links(
        base_url=f'/published/words/{word_id}/comments',
        page=page,
        limit=limit,
        total=total,
    )

    return WordCommentsPageOut(
        count=total, next=next_link, previous=previous_link, results=results
    )


async def published_word_comment_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    text: str,
    page: int = 1,
    limit: int = 32,
    models: dict = VOCAB_MODELS,
) -> WordCommentsPageOut:
    Word = models['Word']
    WordComment = models['WordComment']

    word = (
        await session.execute(select(Word).where(Word.id == word_id))
    ).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')
    friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(word.read_access_level, user_id, word.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Word not available')

    comment = WordComment(word_id=word_id, author_id=user_id, text=text)
    session.add(comment)
    await session.commit()

    # Return paginated comments list
    page, limit, offset = normalize_pagination(page, limit)
    stmt = (
        select(WordComment)
        .where(WordComment.word_id == word_id)
        .order_by(WordComment.created.desc())
        .options(
            selectinload(WordComment.likes),
            selectinload(WordComment.dislikes),
            selectinload(WordComment.answers),
            selectinload(WordComment.author),
            selectinload(WordComment.word),
        )
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows: Sequence = (
        (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    )
    results = [_map_word_comment(c, user_id) for c in rows]

    # Build pagination links
    from api.v1.utils.pagination import build_pagination_links

    next_link, previous_link = build_pagination_links(
        base_url=f'/published/words/{word_id}/comments',
        page=page,
        limit=limit,
        total=total,
    )

    return WordCommentsPageOut(
        count=total, next=next_link, previous=previous_link, results=results
    )


async def published_word_comment_patch_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    text: str,
    models: dict = VOCAB_MODELS,
) -> WordCommentOut:
    WordComment = models['WordComment']
    comment = (
        await session.execute(
            select(WordComment)
            .options(
                selectinload(WordComment.likes),
                selectinload(WordComment.dislikes),
                selectinload(WordComment.answers),
            )
            .where(WordComment.id == comment_id)
        )
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail='Comment not found')
    if comment.author_id != user_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    comment.text = text
    comment.text_modified = True
    await session.commit()
    await session.refresh(comment)
    # Reload with relationships
    comment = (
        await session.execute(
            select(WordComment)
            .options(
                selectinload(WordComment.likes),
                selectinload(WordComment.dislikes),
                selectinload(WordComment.answers),
                selectinload(WordComment.author),
                selectinload(WordComment.word),
            )
            .where(WordComment.id == comment.id)
        )
    ).scalar_one()
    return _map_word_comment(comment, user_id)


async def published_word_comment_delete_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    models: dict = VOCAB_MODELS,
) -> None:
    WordComment = models['WordComment']
    comment = (
        await session.execute(select(WordComment).where(WordComment.id == comment_id))
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail='Comment not found')
    if comment.author_id != user_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    await session.delete(comment)
    await session.commit()


async def _toggle_word_reaction(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    reaction: str,
    models: dict = VOCAB_MODELS,
) -> WordCommentOut:
    WordComment = models['WordComment']
    Word = models['Word']
    comment = (
        await session.execute(
            select(WordComment)
            .options(
                selectinload(WordComment.likes),
                selectinload(WordComment.dislikes),
                selectinload(WordComment.answers),
                selectinload(WordComment.word),
            )
            .where(WordComment.id == comment_id)
        )
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail='Comment not found')

    # Check if user has access to the word
    word = (
        comment.word
        or (
            await session.execute(select(Word).where(Word.id == comment.word_id))
        ).scalar_one_or_none()
    )
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')

    friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(word.read_access_level, user_id, word.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Word not available')

    # Fetch the user to add to likes/dislikes
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')

    # remove opposite reaction
    if reaction == 'like':
        comment.dislikes = [u for u in comment.dislikes if u.id != user_id]
        if any(u.id == user_id for u in comment.likes):
            comment.likes = [u for u in comment.likes if u.id != user_id]
        else:
            comment.likes.append(user)
    elif reaction == 'dislike':
        comment.likes = [u for u in comment.likes if u.id != user_id]
        if any(u.id == user_id for u in comment.dislikes):
            comment.dislikes = [u for u in comment.dislikes if u.id != user_id]
        else:
            comment.dislikes.append(user)

    await session.commit()
    await session.refresh(comment)
    # Reload with relationships
    comment = (
        await session.execute(
            select(WordComment)
            .options(
                selectinload(WordComment.likes),
                selectinload(WordComment.dislikes),
                selectinload(WordComment.answers),
                selectinload(WordComment.author),
                selectinload(WordComment.word),
            )
            .where(WordComment.id == comment.id)
        )
    ).scalar_one()
    return _map_word_comment(comment, user_id)


async def published_word_comment_like_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    models: dict = VOCAB_MODELS,
) -> WordCommentOut:
    return await _toggle_word_reaction(
        session=session,
        user_id=user_id,
        comment_id=comment_id,
        reaction='like',
        models=models,
    )


async def published_word_comment_dislike_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    models: dict = VOCAB_MODELS,
) -> WordCommentOut:
    return await _toggle_word_reaction(
        session=session,
        user_id=user_id,
        comment_id=comment_id,
        reaction='dislike',
        models=models,
    )


async def published_word_comment_author_like_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    models: dict = VOCAB_MODELS,
) -> WordCommentOut:
    WordComment = models['WordComment']
    Word = models['Word']

    comment = (
        await session.execute(
            select(WordComment)
            .options(selectinload(WordComment.word))
            .where(WordComment.id == comment_id)
        )
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail='Comment not found')
    word = (
        comment.word
        or (
            await session.execute(select(Word).where(Word.id == comment.word_id))
        ).scalar_one()
    )
    if word.author_id != user_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    comment.author_liked = not bool(comment.author_liked)
    await session.commit()
    await session.refresh(comment)
    # Reload with relationships
    comment = (
        await session.execute(
            select(WordComment)
            .options(
                selectinload(WordComment.likes),
                selectinload(WordComment.dislikes),
                selectinload(WordComment.answers),
                selectinload(WordComment.author),
                selectinload(WordComment.word),
            )
            .where(WordComment.id == comment.id)
        )
    ).scalar_one()
    return _map_word_comment(comment, user_id)


async def published_word_comment_answers_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    page: int,
    limit: int,
    models: dict = VOCAB_MODELS,
) -> WordCommentsPageOut:
    WordComment = models['WordComment']

    parent = (
        await session.execute(
            select(WordComment)
            .options(selectinload(WordComment.answers))
            .where(WordComment.id == comment_id)
        )
    ).scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail='Comment not found')

    page, limit, offset = normalize_pagination(page, limit)
    answers = parent.answers or []
    total = len(answers)
    sliced = answers[offset : offset + limit]
    results = [_map_word_comment(a, user_id) for a in sliced]
    # Answers list doesn't need pagination links (it's a simple list)
    return WordCommentsPageOut(count=total, next=None, previous=None, results=results)


async def published_word_comment_answer_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    comment_id: UUID,
    text: str,
    models: dict = VOCAB_MODELS,
) -> WordCommentOut:
    WordComment = models['WordComment']

    parent = (
        await session.execute(select(WordComment).where(WordComment.id == comment_id))
    ).scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail='Comment not found')

    reply = WordComment(
        word_id=parent.word_id,
        author_id=user_id,
        text=text,
    )
    session.add(reply)
    await session.flush()
    parent.answers.append(reply)
    await session.commit()
    await session.refresh(reply)
    # Reload with relationships
    reply = (
        await session.execute(
            select(WordComment)
            .options(
                selectinload(WordComment.likes),
                selectinload(WordComment.dislikes),
                selectinload(WordComment.answers),
                selectinload(WordComment.author),
                selectinload(WordComment.word),
            )
            .where(WordComment.id == reply.id)
        )
    ).scalar_one()
    return _map_word_comment(reply, user_id)


def _map_word_to_word_list_with_author(
    w, user_id: UUID | None = None
) -> WordListWithAuthorOut:
    """Map a Word ORM object to WordListWithAuthorOut."""
    from api.v1.published.schemas import WordListWithAuthorOut

    author = getattr(w, 'author', None)
    # Get images through the intermediate WordImageAssociations model
    word_image_assocs = getattr(w, 'wordimageassociations', []) or []
    images = [wia.image for wia in word_image_assocs if hasattr(wia, 'image')]

    # Get background_image_url from the first image association
    background_image_url = None
    if images:
        background_image_url = getattr(images[0], 'image_url', None)

    # Get base word fields
    base_dto = map_word(w)
    base_dict = base_dto.model_dump()

    # Add simplified author fields
    base_dict['author'] = (
        {
            'slug': getattr(author, 'slug', None),
            'username': getattr(author, 'username', None),
            'first_name': getattr(author, 'first_name', None),
            'profile_image_url': getattr(author, 'profile_image_url', None),
        }
        if author is not None
        else None
    )

    # Extract translation objects for the frontend
    word_translations = getattr(w, 'wordtranslations', []) or []
    translations_list = [
        {
            'text': t.translation.text,
            'language': getattr(t.translation.language, 'isocode', None)
            if hasattr(t.translation, 'language')
            else None,
        }
        for t in word_translations
        if hasattr(t, 'translation')
        and t.translation
        and hasattr(t.translation, 'text')
    ]
    base_dict['translations'] = translations_list
    base_dict['translations_count'] = len(translations_list)
    base_dict['background_image_url'] = background_image_url

    # Remove activity_status and activity_progress from published words
    base_dict.pop('activity_status', None)
    base_dict.pop('activity_progress', None)

    # Set favorite (always set, defaulting to False)
    base_dict['favorite'] = getattr(w, '_favorite', False)

    return WordListWithAuthorOut.model_validate(base_dict)


def _map_suggested_word(
    s: WordsSuggestedToCollections, user_id: UUID | None = None
) -> CollectionSuggestedWordOut:
    """Map a WordsSuggestedToCollections ORM object to CollectionSuggestedWordOut."""
    # Format created_relative in DRF-style format (months:days:hours:minutes)
    created_relative = '0:0:0:0'
    if s.created:
        now = datetime.now(timezone.utc)
        created = s.created
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        difference = now - created
        days = difference.days
        months = days // 30
        rem_days = days % 30
        total_seconds = int(difference.total_seconds())
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        created_relative = f'{months}:{rem_days}:{hours}:{minutes}'

    # Map the word object
    word_obj = getattr(s, 'word', None)
    if not word_obj:
        raise ValueError(f'Word not loaded for suggestion {s.id}')

    word_dto = _map_word_to_word_list_with_author(word_obj, user_id)

    return CollectionSuggestedWordOut(
        id=s.id,
        word=word_dto,
        status=s.status,
        created=s.created,
        created_relative=created_relative,
    )


async def published_collection_suggested_words_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    page: int,
    limit: int,
    models: dict = VOCAB_MODELS,
) -> CollectionSuggestedWordsPageOut:
    Collection = models['Collection']
    Suggested = models['WordsSuggestedToCollections']

    coll = (
        await session.execute(select(Collection).where(Collection.id == collection_id))
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(coll.read_access_level, user_id, coll.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Collection not available')

    # Only return PENDING suggestions (for the author)
    page, limit, offset = normalize_pagination(page, limit)
    Word = models['Word']
    FavoriteWord = models['FavoriteWord']
    WordTranslations = models['WordTranslations']
    WordImageAssociations = models['WordImageAssociations']

    stmt = (
        select(Suggested)
        .where(
            Suggested.collection_id == collection_id,
            Suggested.status == RequestStatusEnum.PENDING,
        )
        .order_by(Suggested.created.desc())
        .options(
            selectinload(Suggested.word).selectinload(Word.tags),
            selectinload(Suggested.word).selectinload(Word.types),
            selectinload(Suggested.word).selectinload(Word.language),
            selectinload(Suggested.word).selectinload(Word.author),
            selectinload(Suggested.word)
            .selectinload(Word.wordtranslations)
            .selectinload(WordTranslations.translation),
            selectinload(Suggested.word)
            .selectinload(Word.wordimageassociations)
            .selectinload(WordImageAssociations.image),
        )
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows: Sequence = (
        (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    )

    # Get favorite word IDs for the user
    fav_ids: set[UUID] = set()
    if rows:
        word_ids = [s.word_id for s in rows if hasattr(s, 'word') and s.word]
        if word_ids:
            fav_ids = set(
                (
                    await session.execute(
                        select(FavoriteWord.word_id).where(
                            FavoriteWord.user_id == user_id,
                            FavoriteWord.word_id.in_(word_ids),
                        )
                    )
                ).scalars()
            )

    # Set favorite flag on words
    for s in rows:
        if hasattr(s, 'word') and s.word:
            s.word._favorite = s.word.id in fav_ids

    results = [_map_suggested_word(s, user_id) for s in rows]

    # Build pagination links
    from api.v1.utils.pagination import build_pagination_links

    next_link, previous_link = build_pagination_links(
        base_url=f'/published/collections/{collection_id}/suggested-words',
        page=page,
        limit=limit,
        total=total,
    )

    return CollectionSuggestedWordsPageOut(
        count=total, next=next_link, previous=previous_link, results=results
    )


async def published_collection_suggested_words_add_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    word_ids: list[UUID],
    models: dict = VOCAB_MODELS,
) -> CollectionSuggestedWordsPageOut:
    Collection = models['Collection']
    Suggested = models['WordsSuggestedToCollections']
    Word = models['Word']

    coll = (
        await session.execute(select(Collection).where(Collection.id == collection_id))
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    friend_ids = await _get_friend_ids(session, user_id)
    if not _can_view(coll.read_access_level, user_id, coll.author_id, friend_ids):
        raise HTTPException(status_code=404, detail='Collection not available')

    words = (
        (await session.execute(select(Word.id).where(Word.id.in_(word_ids))))
        .scalars()
        .all()
    )
    if not words:
        raise HTTPException(status_code=400, detail='No words found')

    existing = set(
        (
            await session.execute(
                select(Suggested.word_id).where(
                    Suggested.collection_id == collection_id,
                    Suggested.word_id.in_(words),
                    Suggested.user_id == user_id,
                )
            )
        ).scalars()
    )

    for wid in words:
        if wid in existing:
            continue
        session.add(
            Suggested(
                collection_id=collection_id,
                word_id=wid,
                user_id=user_id,
                status=RequestStatusEnum.PENDING,
            )
        )
    await session.commit()

    return await published_collection_suggested_words_list_service(
        session=session, user_id=user_id, collection_id=collection_id, page=1, limit=100
    )


async def _update_suggestions_status(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    word_ids: list[UUID],
    new_status: str,
    models: dict = VOCAB_MODELS,
) -> CollectionSuggestedWordsPageOut:
    Collection = models['Collection']
    Suggested = models['WordsSuggestedToCollections']
    WordsInCollections = models['WordsInCollections']

    coll = (
        await session.execute(select(Collection).where(Collection.id == collection_id))
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')
    if coll.author_id != user_id:
        raise HTTPException(status_code=403, detail='Forbidden')

    # Update status
    await session.execute(
        Suggested.__table__.update()
        .where(
            Suggested.collection_id == collection_id,
            Suggested.word_id.in_(word_ids),
        )
        .values(status=new_status)
    )

    # If accepting, add words to the collection
    if new_status == RequestStatusEnum.APPROVED:
        # Check which words are not already in the collection
        existing_pairs = set(
            (
                await session.execute(
                    select(
                        WordsInCollections.word_id, WordsInCollections.collection_id
                    ).where(
                        WordsInCollections.collection_id == collection_id,
                        WordsInCollections.word_id.in_(word_ids),
                    )
                )
            ).all()
        )

        for wid in word_ids:
            if (wid, collection_id) not in existing_pairs:
                session.add(
                    WordsInCollections(word_id=wid, collection_id=collection_id)
                )

        # Send Celery task for subscription updates
        from core.celery.app import celery_app
        from tasks.constants import UPDATE_COLLECTION_SUBSCRIPTION_INFO

        celery_app.send_task(
            UPDATE_COLLECTION_SUBSCRIPTION_INFO,
            args=[
                str(collection_id),
                {'new_words': [str(wid) for wid in word_ids]},
                None,
            ],
        )

    await session.commit()
    return await published_collection_suggested_words_list_service(
        session=session, user_id=user_id, collection_id=collection_id, page=1, limit=100
    )


async def published_collection_suggested_words_accept_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    word_ids: list[UUID],
    models: dict = VOCAB_MODELS,
) -> CollectionSuggestedWordsPageOut:
    return await _update_suggestions_status(
        session=session,
        user_id=user_id,
        collection_id=collection_id,
        word_ids=word_ids,
        new_status=RequestStatusEnum.APPROVED,
        models=models,
    )


async def published_collection_suggested_words_reject_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    word_ids: list[UUID],
    models: dict = VOCAB_MODELS,
) -> CollectionSuggestedWordsPageOut:
    return await _update_suggestions_status(
        session=session,
        user_id=user_id,
        collection_id=collection_id,
        word_ids=word_ids,
        new_status=RequestStatusEnum.REJECTED,
        models=models,
    )


async def published_collection_suggested_words_destroy_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    word_ids: list[UUID],
    models: dict = VOCAB_MODELS,
) -> CollectionSuggestedWordsPageOut:
    Suggested = models['WordsSuggestedToCollections']
    Collection = models['Collection']

    coll = (
        await session.execute(select(Collection).where(Collection.id == collection_id))
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    # In DRF: collection author cannot delete suggestions, only the user who suggested can
    if coll.author_id == user_id:
        raise HTTPException(
            status_code=403, detail='Collection author cannot delete suggestions'
        )

    # Only delete suggestions that belong to this user
    await session.execute(
        Suggested.__table__.delete().where(
            Suggested.collection_id == collection_id,
            Suggested.word_id.in_(word_ids),
            Suggested.user_id == user_id,  # Only delete user's own suggestions
        )
    )
    await session.commit()
    return await published_collection_suggested_words_list_service(
        session=session, user_id=user_id, collection_id=collection_id, page=1, limit=100
    )


async def published_collections_subscribed_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    params: CollectionsListParams,
    models: dict = VOCAB_MODELS,
) -> tuple[CollectionsListParams, int, list]:
    Collection = models['Collection']
    CollectionSubscription = models['CollectionSubscription']

    stmt = (
        select(Collection)
        .join(
            CollectionSubscription,
            CollectionSubscription.collection_id == Collection.id,
        )
        .where(CollectionSubscription.subscriber_id == user_id)
    )

    search_fields = ['title', 'description']
    stmt = apply_search(stmt, Collection, params.search, search_fields)

    ordering_map = {
        'title': Collection.title,
        'created': Collection.created,
        'modified': Collection.modified,
    }
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default='-modified')

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    stmt = stmt.offset(params.offset).limit(params.limit)
    rows: Sequence = (await session.execute(stmt)).scalars().all()

    results = [map_collection(c, include_words=False) for c in rows]
    return params, total, results


async def published_collection_borrow_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    models: dict = VOCAB_MODELS,
) -> dict:
    Collection = models['Collection']
    Word = models['Word']
    WordsInCollections = models['WordsInCollections']
    WordTranslations = models['WordTranslations']
    WordDefinitions = models['WordDefinitions']
    WordUsageExamples = models['WordUsageExamples']
    WordImageAssociations = models['WordImageAssociations']

    # Load source collection with words
    src = (
        await session.execute(
            select(Collection)
            .options(
                selectinload(Collection.words_in_collections).selectinload(
                    WordsInCollections.word
                )
            )
            .where(Collection.id == collection_id)
        )
    ).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail='Collection not found')

    # Cache primitive fields BEFORE starting transaction work so we don't
    # touch an expired `src` inside exception handlers.
    src_title = src.title

    # Step 1: Borrow all words in the collection
    # For each word, create a copy or use existing if it already exists
    borrowed_word_ids = []

    for wic in src.words_in_collections or []:
        src_word = wic.word
        if not src_word:
            continue

        # Cache primitive values
        src_word_text = src_word.text
        src_word_language_id = src_word.language_id

        # Check if word already exists in user's vocabulary
        existing_word = (
            await session.execute(
                select(Word).where(
                    Word.text == src_word_text,
                    Word.author_id == user_id,
                    Word.language_id == src_word_language_id,
                )
            )
        ).scalar_one_or_none()

        if existing_word:
            # Use existing word
            borrowed_word_ids.append(existing_word.id)
        else:
            # Create a new borrowed word copy
            new_word = Word(
                text=src_word_text,
                language_id=src_word_language_id,
                author_id=user_id,
                source_word_id=src_word.id,
                is_premium=False,
                activity_status=ActivityStatusEnum.INACTIVE,
                activity_progress=ActivityStatusEnum.activity_progress_default,
                read_access_level=AccessLevelsEnum.PRIVATE,
                add_access_level=AccessLevelsEnum.PRIVATE,
                allow_access_change=False,
            )

            try:
                session.add(new_word)
                await session.flush()
                word_id = new_word.id

                # Copy translations associations
                src_translations = (
                    await session.execute(
                        select(WordTranslations.translation_id).where(
                            WordTranslations.word_id == src_word.id
                        )
                    )
                ).scalars()
                for tr_id in src_translations:
                    session.add(WordTranslations(word_id=word_id, translation_id=tr_id))

                # Copy definitions associations
                src_definitions = (
                    await session.execute(
                        select(WordDefinitions.definition_id).where(
                            WordDefinitions.word_id == src_word.id
                        )
                    )
                ).scalars()
                for def_id in src_definitions:
                    session.add(WordDefinitions(word_id=word_id, definition_id=def_id))

                # Copy usage examples associations
                src_examples = (
                    await session.execute(
                        select(WordUsageExamples.example_id).where(
                            WordUsageExamples.word_id == src_word.id
                        )
                    )
                ).scalars()
                for ex_id in src_examples:
                    session.add(WordUsageExamples(word_id=word_id, example_id=ex_id))

                # Copy image associations
                src_images = (
                    await session.execute(
                        select(WordImageAssociations.image_id).where(
                            WordImageAssociations.word_id == src_word.id
                        )
                    )
                ).scalars()
                for img_id in src_images:
                    session.add(WordImageAssociations(word_id=word_id, image_id=img_id))

                borrowed_word_ids.append(word_id)
            except IntegrityError as word_exc:
                # Word might have been created concurrently between our check and insert
                # Remove the failed object from session and query for existing word
                session.expunge(new_word)

                # Check if it's a unique violation
                error_msg = (
                    str(word_exc.orig) if hasattr(word_exc, 'orig') else str(word_exc)
                )
                is_unique_violation = (
                    'unique_words_in_user_voc' in error_msg
                    or 'unique' in error_msg.lower()
                    or 'duplicate' in error_msg.lower()
                    or (
                        hasattr(word_exc, 'orig')
                        and isinstance(word_exc.orig, UniqueViolationError)
                    )
                )

                if is_unique_violation:
                    # Re-query for existing word (it was created concurrently)
                    existing_word = (
                        await session.execute(
                            select(Word).where(
                                Word.text == src_word_text,
                                Word.author_id == user_id,
                                Word.language_id == src_word_language_id,
                            )
                        )
                    ).scalar_one_or_none()

                    if existing_word:
                        borrowed_word_ids.append(existing_word.id)
                    else:
                        # Word exists but we can't load it - skip this word and continue
                        # This is a rare race condition, but we should handle it gracefully
                        continue
                else:
                    # If it's not a unique violation, we need to rollback and re-raise
                    # This will lose all words created so far, but it's necessary for data integrity
                    await session.rollback()
                    raise

    # Step 2: Create the collection with allow_access_change=False
    new_coll = Collection(
        title=src_title,
        description=src.description,
        author_id=user_id,
        source_collection_id=src.id,
        allow_comments=src.allow_comments,
        allow_suggestions=src.allow_suggestions,
        allow_suggestions_notifications=src.allow_suggestions_notifications,
        # Borrowed collections must start as private and immutable
        read_access_level=AccessLevelsEnum.PRIVATE,
        add_access_level=AccessLevelsEnum.PRIVATE,
        allow_access_change=False,
    )

    try:
        session.add(new_coll)
        try:
            await session.flush()
        except IntegrityError as flush_exc:
            await session.rollback()
            # In borrow context, any IntegrityError is likely a unique constraint violation
            # Check error message or constraint name
            error_msg = (
                str(flush_exc.orig) if hasattr(flush_exc, 'orig') else str(flush_exc)
            )
            is_unique_violation = (
                'unique_user_collection' in error_msg
                or 'unique' in error_msg.lower()
                or 'duplicate' in error_msg.lower()
                or (
                    hasattr(flush_exc, 'orig')
                    and isinstance(flush_exc.orig, UniqueViolationError)
                )
            )

            if is_unique_violation:
                # Find the existing collection and raise HTTPException
                existing_coll = (
                    await session.execute(
                        select(Collection)
                        .options(selectinload(Collection.words_in_collections))
                        .where(
                            func.lower(Collection.title) == func.lower(src_title),
                            Collection.author_id == user_id,
                        )
                    )
                ).scalar_one_or_none()

                if existing_coll:
                    existing_coll_dto = map_collection(
                        existing_coll, include_words=False, for_published=True
                    )
                    raise HTTPException(
                        status_code=409,
                        detail={
                            'exception_code': 'already_exist',
                            'detail': 'Collection already exists in your vocabulary',
                            'existing_object': existing_coll_dto.model_dump(
                                mode='json'
                            ),
                        },
                    ) from flush_exc
                else:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            'exception_code': 'already_exist',
                            'detail': 'Collection already exists in your vocabulary',
                        },
                    ) from flush_exc
            raise

        # Step 3: Link the borrowed words to the new collection
        for word_id in borrowed_word_ids:
            session.add(WordsInCollections(collection_id=new_coll.id, word_id=word_id))

        await session.commit()
    except IntegrityError as exc:
        # Any integrity error here means the collection already exists for this user
        await session.rollback()

        # Check error message or constraint name
        error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
        is_unique_violation = (
            'unique_user_collection' in error_msg
            or 'unique' in error_msg.lower()
            or 'duplicate' in error_msg.lower()
            or (hasattr(exc, 'orig') and isinstance(exc.orig, UniqueViolationError))
        )

        if is_unique_violation:
            # Find the existing collection with same title (case-insensitive) and author
            existing_coll = (
                await session.execute(
                    select(Collection)
                    .options(selectinload(Collection.words_in_collections))
                    .where(
                        func.lower(Collection.title) == func.lower(src_title),
                        Collection.author_id == user_id,
                    )
                )
            ).scalar_one_or_none()

            if existing_coll:
                existing_coll_dto = map_collection(
                    existing_coll, include_words=False, for_published=True
                )
                raise HTTPException(
                    status_code=409,
                    detail={
                        'exception_code': 'already_exist',
                        'detail': 'Collection already exists in your vocabulary',
                        'existing_object': existing_coll_dto.model_dump(mode='json'),
                    },
                ) from exc
            else:
                raise HTTPException(
                    status_code=409,
                    detail={
                        'exception_code': 'already_exist',
                        'detail': 'Collection already exists in your vocabulary',
                    },
                ) from exc
        raise

    # Reload the collection with words_in_collections and author eagerly loaded to avoid MissingGreenlet error
    new_coll = (
        await session.execute(
            select(Collection)
            .options(
                selectinload(Collection.words_in_collections),
                selectinload(Collection.author),
            )
            .where(Collection.id == new_coll.id)
        )
    ).scalar_one()

    return map_collection(new_coll, include_words=True, for_published=True)


async def published_collection_favorite_toggle_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
) -> dict:
    Collection = VOCAB_MODELS['Collection']
    src = (
        await session.execute(select(Collection).where(Collection.id == collection_id))
    ).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail='Collection not found')
    return await collection_favorite_toggle_service(
        session=session, user_id=user_id, collection_id=src.id, author_only=False
    )


async def _apply_collection_filter(
    stmt, *, WordsInCollections, Word, collection_ids: list[UUID] | None
):
    if collection_ids:
        stmt = stmt.join(
            WordsInCollections, WordsInCollections.word_id == Word.id
        ).where(WordsInCollections.collection_id.in_(collection_ids))
    return stmt


async def published_translations_list_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    page: int,
    limit: int,
    collections: list[UUID] | None = None,
    models: dict = VOCAB_MODELS,
) -> dict:
    Word = models['Word']
    WordTranslation = models['WordTranslation']
    WordTranslations = models['WordTranslations']
    WordsInCollections = models['WordsInCollections']
    Language = models['Language']

    page, limit, offset = normalize_pagination(page, limit)
    stmt = (
        select(WordTranslation)
        .join(WordTranslations, WordTranslations.translation_id == WordTranslation.id)
        .join(Word, Word.id == WordTranslations.word_id)
        .where(
            Word.read_access_level.in_(_allowed_levels()),
        )
    )
    stmt = await _apply_collection_filter(
        stmt,
        WordsInCollections=WordsInCollections,
        Word=Word,
        collection_ids=collections,
    )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.options(selectinload(WordTranslation.language))
                .order_by(WordTranslation.created.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    translation_ids = [r.id for r in rows]
    last_words_map: dict[UUID, list[dict]] = {t_id: [] for t_id in translation_ids}
    counts_map: dict[UUID, int] = {t_id: 0 for t_id in translation_ids}
    if translation_ids:
        counts = (
            await session.execute(
                select(WordTranslations.translation_id, func.count())
                .where(WordTranslations.translation_id.in_(translation_ids))
                .group_by(WordTranslations.translation_id)
            )
        ).all()
        counts_map.update({t_id: count for t_id, count in counts})

        assoc_rows = (
            await session.execute(
                select(
                    WordTranslations.translation_id,
                    Word.text,
                    Language.isocode,
                    WordTranslations.created,
                )
                .join(Word, Word.id == WordTranslations.word_id)
                .join(Language, Word.language_id == Language.id)
                .where(WordTranslations.translation_id.in_(translation_ids))
                .order_by(WordTranslations.created.desc())
            )
        ).all()
        for t_id, word_text, lang_isocode, _created in assoc_rows:
            if len(last_words_map[t_id]) >= 6:
                continue
            last_words_map[t_id].append(
                {'text': word_text, 'language__isocode': lang_isocode}
            )

    results = []
    for r in rows:
        last_words = last_words_map.get(r.id, [])
        other_words_count = max(counts_map.get(r.id, 0) - len(last_words), 0)
        results.append(
            TranslationOut(
                id=r.id,
                slug=r.slug,
                text=r.text,
                language=getattr(r.language, 'isocode', None)
                if hasattr(r, 'language')
                else None,
                other_words_count=other_words_count,
                last_6_words=last_words,
                created=r.created,
                modified=r.modified,
            )
        )
    return {'page': page, 'limit': limit, 'count': total, 'results': results}


async def published_definitions_list_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    page: int,
    limit: int,
    collections: list[UUID] | None = None,
    models: dict = VOCAB_MODELS,
) -> dict:
    Word = models['Word']
    Definition = models['Definition']
    WordDefinitions = models['WordDefinitions']
    WordsInCollections = models['WordsInCollections']

    page, limit, offset = normalize_pagination(page, limit)
    stmt = (
        select(Definition)
        .join(WordDefinitions, WordDefinitions.definition_id == Definition.id)
        .join(Word, Word.id == WordDefinitions.word_id)
        .where(
            Word.read_access_level.in_(_allowed_levels()),
        )
    )
    stmt = await _apply_collection_filter(
        stmt,
        WordsInCollections=WordsInCollections,
        Word=Word,
        collection_ids=collections,
    )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.options(selectinload(Definition.language))
                .order_by(Definition.created.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    definition_ids = [r.id for r in rows]
    last_words_map: dict[UUID, list[str]] = {d_id: [] for d_id in definition_ids}
    counts_map: dict[UUID, int] = {d_id: 0 for d_id in definition_ids}
    if definition_ids:
        counts = (
            await session.execute(
                select(WordDefinitions.definition_id, func.count())
                .where(WordDefinitions.definition_id.in_(definition_ids))
                .group_by(WordDefinitions.definition_id)
            )
        ).all()
        counts_map.update({d_id: count for d_id, count in counts})

        assoc_rows = (
            await session.execute(
                select(
                    WordDefinitions.definition_id,
                    Word.text,
                    WordDefinitions.created,
                )
                .join(Word, Word.id == WordDefinitions.word_id)
                .where(WordDefinitions.definition_id.in_(definition_ids))
                .order_by(WordDefinitions.created.desc())
            )
        ).all()
        for d_id, word_text, _created in assoc_rows:
            if len(last_words_map[d_id]) >= 4:
                continue
            last_words_map[d_id].append(word_text)

    results = []
    for r in rows:
        last_words = last_words_map.get(r.id, [])
        other_words_count = max(counts_map.get(r.id, 0) - len(last_words), 0)
        results.append(
            DefinitionOut(
                id=r.id,
                slug=r.slug,
                text=r.text,
                translation=r.translation,
                language=getattr(r.language, 'isocode', None),
                other_words_count=other_words_count,
                last_4_words=last_words,
                created=r.created,
                modified=r.modified,
            )
        )
    return {'page': page, 'limit': limit, 'count': total, 'results': results}


async def published_examples_list_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    page: int,
    limit: int,
    collections: list[UUID] | None = None,
    models: dict = VOCAB_MODELS,
) -> dict:
    Word = models['Word']
    UsageExample = models['UsageExample']
    WordUsageExamples = models['WordUsageExamples']
    WordsInCollections = models['WordsInCollections']

    page, limit, offset = normalize_pagination(page, limit)
    stmt = (
        select(UsageExample)
        .join(WordUsageExamples, WordUsageExamples.example_id == UsageExample.id)
        .join(Word, Word.id == WordUsageExamples.word_id)
        .where(
            Word.read_access_level.in_(_allowed_levels()),
        )
    )
    stmt = await _apply_collection_filter(
        stmt,
        WordsInCollections=WordsInCollections,
        Word=Word,
        collection_ids=collections,
    )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.options(selectinload(UsageExample.language))
                .order_by(UsageExample.created.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    example_ids = [r.id for r in rows]
    last_words_map: dict[UUID, list[str]] = {e_id: [] for e_id in example_ids}
    counts_map: dict[UUID, int] = {e_id: 0 for e_id in example_ids}
    if example_ids:
        counts = (
            await session.execute(
                select(WordUsageExamples.example_id, func.count())
                .where(WordUsageExamples.example_id.in_(example_ids))
                .group_by(WordUsageExamples.example_id)
            )
        ).all()
        counts_map.update({e_id: count for e_id, count in counts})

        assoc_rows = (
            await session.execute(
                select(
                    WordUsageExamples.example_id,
                    Word.text,
                    WordUsageExamples.created,
                )
                .join(Word, Word.id == WordUsageExamples.word_id)
                .where(WordUsageExamples.example_id.in_(example_ids))
                .order_by(WordUsageExamples.created.desc())
            )
        ).all()
        for e_id, word_text, _created in assoc_rows:
            if len(last_words_map[e_id]) >= 4:
                continue
            last_words_map[e_id].append(word_text)

    results = []
    for r in rows:
        last_words = last_words_map.get(r.id, [])
        other_words_count = max(counts_map.get(r.id, 0) - len(last_words), 0)
        results.append(
            ExampleOut(
                id=r.id,
                slug=r.slug,
                text=r.text,
                translation=r.translation,
                language=getattr(r.language, 'isocode', None),
                source=r.source or 'OTH',
                source_name=r.source_name,
                source_url=r.source_url,
                other_words_count=other_words_count,
                last_4_words=last_words,
                created=r.created,
                modified=r.modified,
            )
        )
    return {'page': page, 'limit': limit, 'count': total, 'results': results}


async def published_images_list_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    page: int,
    limit: int,
    collections: list[UUID] | None = None,
    models: dict = VOCAB_MODELS,
) -> dict:
    Word = models['Word']
    ImageAssociation = models['ImageAssociation']
    WordImageAssociations = models['WordImageAssociations']
    WordsInCollections = models['WordsInCollections']

    page, limit, offset = normalize_pagination(page, limit)
    stmt = (
        select(ImageAssociation)
        .join(
            WordImageAssociations, WordImageAssociations.image_id == ImageAssociation.id
        )
        .join(Word, Word.id == WordImageAssociations.word_id)
        .where(
            Word.read_access_level.in_(_allowed_levels()),
        )
    )
    stmt = await _apply_collection_filter(
        stmt,
        WordsInCollections=WordsInCollections,
        Word=Word,
        collection_ids=collections,
    )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(ImageAssociation.created.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    image_ids = [r.id for r in rows]
    last_words_map: dict[UUID, list[str]] = {i_id: [] for i_id in image_ids}
    counts_map: dict[UUID, int] = {i_id: 0 for i_id in image_ids}
    if image_ids:
        counts = (
            await session.execute(
                select(WordImageAssociations.image_id, func.count())
                .where(WordImageAssociations.image_id.in_(image_ids))
                .group_by(WordImageAssociations.image_id)
            )
        ).all()
        counts_map.update({i_id: count for i_id, count in counts})

        assoc_rows = (
            await session.execute(
                select(
                    WordImageAssociations.image_id,
                    Word.text,
                    WordImageAssociations.created,
                )
                .join(Word, Word.id == WordImageAssociations.word_id)
                .where(WordImageAssociations.image_id.in_(image_ids))
                .order_by(WordImageAssociations.created.desc())
            )
        ).all()
        for i_id, word_text, _created in assoc_rows:
            if len(last_words_map[i_id]) >= 6:
                continue
            last_words_map[i_id].append(word_text)

    results = []
    for r in rows:
        last_words = last_words_map.get(r.id, [])
        other_words_count = max(counts_map.get(r.id, 0) - len(last_words), 0)
        results.append(
            ImageOut(
                id=r.id,
                image_url=r.image_url,
                width=r.width,
                height=r.height,
                num=r.num,
                other_words_count=other_words_count,
                last_6_words=last_words,
                created=r.created,
                modified=r.modified,
            )
        )
    return {'page': page, 'limit': limit, 'count': total, 'results': results}
