"""Published objects services."""

from __future__ import annotations

from typing import Iterable, Sequence
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.ordering import apply_ordering
from api.v1.utils.searching import apply_search
from api.v1.utils.pagination import normalize_pagination
from api.v1.vocabulary.models import VOCAB_MODELS
from api.v1.vocabulary.mapping import map_word, map_word_read
from api.v1.vocabulary.schemas import WordReadOut, WordResolveOut
from api.v1.collections.schemas import CollectionReadOut, CollectionResolveOut
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
from api.v1.published.schemas import (
    WordsPageOut,
    WordListWithAuthorOut,
    WordPublishedProfileOut,
    CollectionPublishedProfileOut,
    CollectionCommentOut,
    CollectionCommentsPageOut,
    WordCommentOut,
    WordCommentsPageOut,
    CollectionSuggestedWordOut,
    CollectionSuggestedWordsPageOut,
)
from core.constants import AccessLevelsEnum, RequestStatusEnum
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

    comments_count = (
        await session.execute(
            select(func.count())
            .select_from(WordComment)
            .where(WordComment.word_id == word.id)
        )
    ).scalar_one()

    base = map_word_read(word).model_dump()
    # Published profile should not expose activity_status
    base.pop('activity_status', None)
    return WordPublishedProfileOut(
        **base,
        author=author_payload,
        collections=collections,
        collections_count=collections_count,
        synonyms=[],
        synonyms_count=synonyms_count,
        comments=[],
        comments_count=comments_count,
        images_count=len(images),
        definitions_count=len(definitions),
        examples_count=len(examples),
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
):
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

    return CollectionPublishedProfileOut(
        id=coll.id,
        slug=coll.slug,
        author=author_payload,
        title=coll.title,
        description=coll.description,
        favorite=coll._favorite,
        created=coll.created,
        modified=coll.modified,
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
        comments=[],
        allow_suggestions=bool(coll.allow_suggestions),
        allow_suggestions_notifications=bool(coll.allow_suggestions_notifications),
        suggestions_count=0,
        suggestions_approved_count=0,
        suggestions_rejected_count=0,
        disallow_suggestions_for=False,
        suggestions=[],
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
) -> WordsPageOut:
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

    return WordsPageOut(page=page, limit=limit, count=total, results=results)


async def published_word_borrow_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    models: dict = VOCAB_MODELS,
) -> dict:
    Word = models['Word']

    src = (
        await session.execute(
            select(Word).options(selectinload(Word.language)).where(Word.id == word_id)
        )
    ).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail='Word not found')

    new_word = Word(
        text=src.text,
        language_id=getattr(src.language, 'id', None),
        author_id=user_id,
        source_word_id=src.id,
    )
    session.add(new_word)
    await session.commit()
    await session.refresh(new_word)
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
        session=session, word_id=src.id, user_id=user_id
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
) -> WordsPageOut:
    # Not enough data to expose synonyms separately; return empty list to keep endpoint functional.
    page, limit, _ = normalize_pagination(page, limit)
    return WordsPageOut(page=page, limit=limit, count=0, results=[])


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
    enable_notifications: bool | None = None,
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    Collection = models['Collection']
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
    if sub:
        # toggle off
        await session.delete(sub)
        await session.commit()
        coll._favorite = getattr(coll, '_favorite', False)
        return map_collection(coll, include_words=False)

    sub = CollectionSubscription(
        subscriber_id=user_id,
        collection_id=coll.id,
        enable_notifications=enable_notifications
        if enable_notifications is not None
        else True,
    )
    session.add(sub)
    await session.commit()
    coll._favorite = getattr(coll, '_favorite', False)
    return map_collection(coll, include_words=False)


def _map_comment(comment: CollectionComment) -> CollectionCommentOut:
    likes = len(getattr(comment, 'likes', []) or [])
    dislikes = len(getattr(comment, 'dislikes', []) or [])
    answers = len(getattr(comment, 'answers', []) or [])
    return CollectionCommentOut(
        id=comment.id,
        collection_id=comment.collection_id,
        author_id=comment.author_id,
        text=comment.text,
        author_liked=bool(comment.author_liked),
        likes_count=likes,
        dislikes_count=dislikes,
        answers_count=answers,
        created=comment.created,
        modified=comment.modified,
    )


def _map_word_comment(comment: WordComment) -> WordCommentOut:
    likes = len(getattr(comment, 'likes', []) or [])
    dislikes = len(getattr(comment, 'dislikes', []) or [])
    answers = len(getattr(comment, 'answers', []) or [])
    return WordCommentOut(
        id=comment.id,
        word_id=comment.word_id,
        author_id=comment.author_id,
        text=comment.text,
        author_liked=bool(comment.author_liked),
        likes_count=likes,
        dislikes_count=dislikes,
        answers_count=answers,
        created=comment.created,
        modified=comment.modified,
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
        )
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows: Sequence = (
        (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    )
    results = [_map_comment(c) for c in rows]
    return CollectionCommentsPageOut(
        page=page, limit=limit, count=total, results=results
    )


async def published_collection_comment_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    text: str,
    models: dict = VOCAB_MODELS,
) -> CollectionCommentOut:
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
    await session.refresh(comment)
    return _map_comment(comment)


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
    return _map_comment(comment)


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

    # remove opposite reaction
    if reaction == 'like':
        comment.dislikes = [u for u in comment.dislikes if u.id != user_id]
        if any(u.id == user_id for u in comment.likes):
            comment.likes = [u for u in comment.likes if u.id != user_id]
        else:
            comment.likes.append(
                type(comment.likes[0])()
                if comment.likes
                else None  # placeholder won't work
            )
    elif reaction == 'dislike':
        comment.likes = [u for u in comment.likes if u.id != user_id]
        if any(u.id == user_id for u in comment.dislikes):
            comment.dislikes = [u for u in comment.dislikes if u.id != user_id]
        else:
            comment.dislikes.append(
                type(comment.dislikes[0])() if comment.dislikes else None
            )

    await session.commit()
    await session.refresh(comment)
    return _map_comment(comment)


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
    return _map_comment(comment)


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
    results = [_map_comment(a) for a in sliced]
    return CollectionCommentsPageOut(
        page=page, limit=limit, count=total, results=results
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
    return _map_comment(reply)


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
        )
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows: Sequence = (
        (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    )
    results = [_map_word_comment(c) for c in rows]
    return WordCommentsPageOut(page=page, limit=limit, count=total, results=results)


async def published_word_comment_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    text: str,
    models: dict = VOCAB_MODELS,
) -> WordCommentOut:
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
    await session.refresh(comment)
    return _map_word_comment(comment)


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
    return _map_word_comment(comment)


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

    # remove opposite reaction
    if reaction == 'like':
        comment.dislikes = [u for u in comment.dislikes if u.id != user_id]
        if any(u.id == user_id for u in comment.likes):
            comment.likes = [u for u in comment.likes if u.id != user_id]
        else:
            comment.likes.append(type(comment.likes[0])() if comment.likes else None)
    elif reaction == 'dislike':
        comment.likes = [u for u in comment.likes if u.id != user_id]
        if any(u.id == user_id for u in comment.dislikes):
            comment.dislikes = [u for u in comment.dislikes if u.id != user_id]
        else:
            comment.dislikes.append(
                type(comment.dislikes[0])() if comment.dislikes else None
            )

    await session.commit()
    await session.refresh(comment)
    return _map_word_comment(comment)


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
    return _map_word_comment(comment)


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
    results = [_map_word_comment(a) for a in sliced]
    return WordCommentsPageOut(page=page, limit=limit, count=total, results=results)


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
    return _map_word_comment(reply)


# ----------------------------
# Collection suggested words (published)
# ----------------------------


def _map_suggested_word(s: WordsSuggestedToCollections) -> CollectionSuggestedWordOut:
    return CollectionSuggestedWordOut(
        id=s.id,
        word_id=s.word_id,
        collection_id=s.collection_id,
        user_id=s.user_id,
        status=s.status,
        created=s.created,
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

    page, limit, offset = normalize_pagination(page, limit)
    stmt = (
        select(Suggested)
        .where(Suggested.collection_id == collection_id)
        .order_by(Suggested.created.desc())
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows: Sequence = (
        (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    )
    results = [_map_suggested_word(s) for s in rows]
    return CollectionSuggestedWordsPageOut(
        page=page, limit=limit, count=total, results=results
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

    coll = (
        await session.execute(select(Collection).where(Collection.id == collection_id))
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')
    if coll.author_id != user_id:
        raise HTTPException(status_code=403, detail='Forbidden')

    await session.execute(
        Suggested.__table__.update()
        .where(
            Suggested.collection_id == collection_id,
            Suggested.word_id.in_(word_ids),
        )
        .values(status=new_status)
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
    if coll.author_id != user_id:
        raise HTTPException(status_code=403, detail='Forbidden')

    await session.execute(
        Suggested.__table__.delete().where(
            Suggested.collection_id == collection_id, Suggested.word_id.in_(word_ids)
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
    WordsInCollections = models['WordsInCollections']

    src = (
        await session.execute(
            select(Collection)
            .options(selectinload(Collection.words_in_collections))
            .where(Collection.id == collection_id)
        )
    ).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail='Collection not found')

    new_coll = Collection(
        title=src.title,
        description=src.description,
        author_id=user_id,
        source_collection_id=src.id,
        allow_comments=src.allow_comments,
        allow_suggestions=src.allow_suggestions,
        allow_suggestions_notifications=src.allow_suggestions_notifications,
    )
    session.add(new_coll)
    await session.flush()

    for wic in src.words_in_collections or []:
        session.add(WordsInCollections(collection_id=new_coll.id, word_id=wic.word_id))

    await session.commit()
    await session.refresh(new_coll)
    return map_collection(new_coll, include_words=True)


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
        session=session, user_id=user_id, collection_id=src.id
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
                source=r.source,
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
