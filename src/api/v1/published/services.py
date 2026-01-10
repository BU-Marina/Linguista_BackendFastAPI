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
from api.v1.vocabulary.models import VOCAB_MODELS
from api.v1.vocabulary.mapping import map_word, map_word_read
from api.v1.vocabulary.params import WordsListParams, CollectionsListParams
from api.v1.collections.mapping import map_collection
from core.constants import AccessLevelsEnum, ActivityStatusEnum
from apps.users.models import Friend, Subscription


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
    if params.languages:
        stmt = stmt.join(Language).where(Language.isocode.in_(params.languages))
    if params.tags:
        stmt = stmt.join(Word.tags).where(Tag.name.in_(params.tags))
    if params.types:
        stmt = stmt.join(Word.types).where(
            or_(WordType.name_en.in_(params.types), WordType.name_ru.in_(params.types))
        )
    if favorite_only and user_id:
        stmt = stmt.join(VOCAB_MODELS["FavoriteWord"]).where(
            VOCAB_MODELS["FavoriteWord"].user_id == user_id
        )
    return stmt


async def published_words_list_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    params: WordsListParams,
    author_ids: Iterable[UUID] | None = None,
    favorite_only: bool = False,
    ordering_override: str | None = None,
    models: dict = VOCAB_MODELS,
):
    Word = models["Word"]
    Language = models["Language"]
    Tag = models["Tag"]
    WordType = models["WordType"]
    FavoriteWord = models["FavoriteWord"]

    allowed_levels = [
        AccessLevelsEnum.PUBLIC,
        AccessLevelsEnum.FRIENDS,
        AccessLevelsEnum.FRIENDS_AND_STUDY_GROUPS,
    ]

    stmt = select(Word).where(
        Word.read_access_level.in_(allowed_levels),
        Word.activity_status == ActivityStatusEnum.ACTIVE,
    )
    if author_ids is not None:
        author_ids = list(author_ids)
        if not author_ids:
            return params, 0, []
        stmt = stmt.where(Word.author_id.in_(author_ids))

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

    search_fields = ["text", "note"]
    stmt = apply_search(stmt, Word, params.search, search_fields)

    ordering_map = {
        "text": Word.text,
        "created": Word.created,
        "modified": Word.modified,
    }
    default_ordering = ordering_override or "-modified"
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default=default_ordering)

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    stmt = stmt.offset(params.offset).limit(params.limit)
    stmt = stmt.options(
        selectinload(Word.tags),
        selectinload(Word.types),
        selectinload(Word.language),
        selectinload(Word.translations),
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

    return params, total, results


async def published_word_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    slug: str,
    models: dict = VOCAB_MODELS,
):
    Word = models["Word"]
    FavoriteWord = models["FavoriteWord"]

    stmt = (
        select(Word)
        .where(Word.slug == slug)
        .options(
            selectinload(Word.tags),
            selectinload(Word.types),
            selectinload(Word.language),
            selectinload(Word.translations),
            selectinload(Word.examples),
            selectinload(Word.definitions),
        )
    )
    word = (await session.execute(stmt)).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    friend_ids: set[UUID] = set()
    if user_id:
        friend_ids = await _get_friend_ids(session, user_id)

    if not _can_view(word.read_access_level, user_id, word.author_id, friend_ids):
        raise HTTPException(status_code=404, detail="Word not available")

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

    return map_word_read(word)


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
    Collection = models["Collection"]
    Tag = models["Tag"]
    WordsInCollections = models["WordsInCollections"]
    FavoriteCollection = models["FavoriteCollection"]

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

    search_fields = ["title", "description"]
    stmt = apply_search(stmt, Collection, params.search, search_fields)

    ordering_map = {
        "title": Collection.title,
        "created": Collection.created,
        "modified": Collection.modified,
    }
    default_ordering = ordering_override or "-modified"
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default=default_ordering)

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    stmt = stmt.offset(params.offset).limit(params.limit)
    stmt = stmt.options(selectinload(Collection.tags))
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

    results = []
    for c in rows:
        c._favorite = c.id in fav_ids
        c._words_count = counts.get(c.id, 0)
        results.append(map_collection(c))

    return params, total, results


async def published_collection_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    slug: str,
    models: dict = VOCAB_MODELS,
):
    Collection = models["Collection"]
    FavoriteCollection = models["FavoriteCollection"]
    WordsInCollections = models["WordsInCollections"]
    Word = models["Word"]

    stmt = (
        select(Collection)
        .where(Collection.slug == slug)
        .options(
            selectinload(Collection.tags),
            selectinload(Collection.words_in_collections)
            .selectinload(WordsInCollections.word)
            .selectinload(Word.tags),
            selectinload(Collection.words_in_collections)
            .selectinload(WordsInCollections.word)
            .selectinload(Word.types),
            selectinload(Collection.words_in_collections)
            .selectinload(WordsInCollections.word)
            .selectinload(Word.language),
        )
    )
    coll = (await session.execute(stmt)).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")

    friend_ids: set[UUID] = set()
    if user_id:
        friend_ids = await _get_friend_ids(session, user_id)

    if not _can_view(coll.read_access_level, user_id, coll.author_id, friend_ids):
        raise HTTPException(status_code=404, detail="Collection not available")

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

    return map_collection(coll, include_words=True)
