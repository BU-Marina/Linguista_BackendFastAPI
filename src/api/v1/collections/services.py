"""Collections services."""

from __future__ import annotations

from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, func, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.ordering import apply_ordering
from api.v1.utils.searching import apply_search
from api.v1.vocabulary.models import VOCAB_MODELS
from api.v1.vocabulary.params import CollectionsListParams
from core.celery.app import celery_app
from tasks.constants import UPDATE_COLLECTION_SUBSCRIPTION_INFO
from .schemas import (
    CollectionIn,
    CollectionReadOut,
    PageOut,
    CollectionResolveOut,
    CollectionSubscriptionDetailOut,
)
from .mapping import map_collection


async def collections_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    params: CollectionsListParams,
    models: dict = VOCAB_MODELS,
) -> PageOut:
    Collection = models['Collection']
    Tag = models['Tag']
    FavoriteCollection = models['FavoriteCollection']

    stmt = select(Collection).where(Collection.author_id == user_id)
    if params.tags:
        stmt = stmt.join(Collection.tags).where(Tag.name.in_(params.tags))
    if params.favorite_only:
        stmt = stmt.join(FavoriteCollection).where(
            FavoriteCollection.user_id == user_id
        )

    stmt = stmt.options(selectinload(Collection.tags))

    search_fields = ['title', 'description']
    stmt = apply_search(stmt, Collection, params.search, search_fields)

    ordering_map = {
        'title': Collection.title,
        '-title': Collection.title.desc(),
        'created': Collection.created,
        '-created': Collection.created.desc(),
        'modified': Collection.modified,
        '-modified': Collection.modified.desc(),
    }
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default='-modified')

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    stmt = stmt.offset(params.offset).limit(params.limit)
    rows = (await session.execute(stmt)).scalars().all()

    fav_ids = set(
        (
            await session.execute(
                select(FavoriteCollection.collection_id).where(
                    FavoriteCollection.user_id == user_id,
                    FavoriteCollection.collection_id.in_([c.id for c in rows]),
                )
            )
        )
        .scalars()
        .all()
    )

    counts = dict(
        (
            await session.execute(
                select(Collection.id, func.count())
                .select_from(Collection)
                .join(models['WordsInCollections'])
                .where(Collection.id.in_([c.id for c in rows]))
                .group_by(Collection.id)
            )
        ).all()
    )

    results = []
    for c in rows:
        c._favorite = c.id in fav_ids
        c._words_count = counts.get(c.id, 0)
        results.append(map_collection(c))

    # Build pagination links
    from api.v1.utils.pagination import build_pagination_links

    next_link, previous_link = build_pagination_links(
        base_url='/collections',
        page=params.page,
        limit=params.limit,
        total=total,
        query_params={
            'ordering': params.ordering,
            'search': params.search,
            'favorite_only': params.favorite_only,
        },
    )

    return PageOut(
        page=params.page,
        limit=params.limit,
        count=total,
        results=results,
        next=next_link,
        previous=previous_link,
    )


async def collection_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    payload: CollectionIn,
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    Collection = models['Collection']

    coll = Collection(
        title=payload.title,
        description=payload.description,
        allow_comments=payload.allow_comments,
        allow_suggestions=payload.allow_suggestions,
        allow_suggestions_notifications=payload.allow_suggestions_notifications,
        author_id=user_id,
    )
    session.add(coll)
    await session.commit()
    await session.refresh(coll)
    coll._favorite = False
    coll._words_count = 0
    return map_collection(coll, include_words=True)


async def collection_resolve_slug_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = VOCAB_MODELS,
) -> CollectionResolveOut:
    Collection = models['Collection']
    obj = (
        await session.execute(
            select(Collection.id, Collection.slug).where(
                Collection.slug == slug, Collection.author_id == user_id
            )
        )
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail='Collection not found')
    return CollectionResolveOut(id=obj.id, slug=obj.slug)


async def collection_retrieve_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    Collection = models['Collection']
    FavoriteCollection = models['FavoriteCollection']
    WordsInCollections = models['WordsInCollections']
    Word = models['Word']

    coll = (
        await session.execute(
            select(Collection)
            .where(Collection.id == collection_id, Collection.author_id == user_id)
            .options(
                selectinload(Collection.words_in_collections)
                .selectinload(WordsInCollections.word)
                .options(
                    selectinload(Word.tags),
                    selectinload(Word.types),
                    selectinload(Word.language),
                )
            )
        )
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    fav = (
        await session.execute(
            select(func.count())
            .select_from(FavoriteCollection)
            .where(
                FavoriteCollection.user_id == user_id,
                FavoriteCollection.collection_id == coll.id,
            )
        )
    ).scalar_one()
    coll._favorite = fav > 0
    coll._words_count = len(coll.words_in_collections or [])
    # Words are fetched via a separate endpoint; omit words in profile response
    return map_collection(coll, include_words=False)


async def collection_update_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    payload: CollectionIn,
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    Collection = models['Collection']

    coll = (
        await session.execute(
            select(Collection).where(
                Collection.id == collection_id, Collection.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    coll.title = payload.title
    coll.description = payload.description
    coll.allow_comments = payload.allow_comments
    coll.allow_suggestions = payload.allow_suggestions
    coll.allow_suggestions_notifications = payload.allow_suggestions_notifications
    await session.commit()
    await session.refresh(coll)
    coll._favorite = False
    return await collection_retrieve_service(
        session=session, user_id=user_id, collection_id=collection_id, models=models
    )


async def collection_delete_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    delete_words: bool = False,
    models: dict = VOCAB_MODELS,
) -> None:
    Collection = models['Collection']
    WordsInCollections = models['WordsInCollections']
    Word = models['Word']

    coll = (
        await session.execute(
            select(Collection).where(
                Collection.id == collection_id, Collection.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    if delete_words:
        word_ids = (
            (
                await session.execute(
                    select(WordsInCollections.word_id).where(
                        WordsInCollections.collection_id == coll.id
                    )
                )
            )
            .scalars()
            .all()
        )
        if word_ids:
            await session.execute(
                delete(Word).where(
                    and_(Word.id.in_(word_ids), Word.author_id == user_id)
                )
            )

    await session.delete(coll)
    await session.commit()


async def collection_add_words_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    word_slugs: list[str],
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    Collection = models['Collection']
    Word = models['Word']
    WordsInCollections = models['WordsInCollections']

    coll = (
        await session.execute(
            select(Collection).where(
                Collection.id == collection_id, Collection.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    words = (
        (
            await session.execute(
                select(Word).where(Word.slug.in_(word_slugs), Word.author_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    if not words:
        raise HTTPException(status_code=400, detail='No words found')

    existing_pairs = set(
        (
            await session.execute(
                select(
                    WordsInCollections.word_id, WordsInCollections.collection_id
                ).where(
                    WordsInCollections.collection_id == coll.id,
                    WordsInCollections.word_id.in_([w.id for w in words]),
                )
            )
        ).all()
    )

    for w in words:
        if (w.id, coll.id) in existing_pairs:
            continue
        session.add(WordsInCollections(word_id=w.id, collection_id=coll.id))

    await session.commit()
    celery_app.send_task(
        UPDATE_COLLECTION_SUBSCRIPTION_INFO,
        args=[str(coll.id), {'new_words': [str(w.id) for w in words]}, None],
    )
    return await collection_retrieve_service(
        session=session, user_id=user_id, collection_id=collection_id, models=models
    )


async def collection_add_words_bulk_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_ids: list[UUID],
    word_ids: list[UUID],
    models: dict = VOCAB_MODELS,
) -> dict:
    Collection = models['Collection']
    Word = models['Word']
    WordsInCollections = models['WordsInCollections']

    if not collection_ids or not word_ids:
        raise HTTPException(
            status_code=400, detail='collections and word_ids are required'
        )

    # ensure collections belong to user
    cols = (
        (
            await session.execute(
                select(Collection.id).where(
                    Collection.id.in_(collection_ids), Collection.author_id == user_id
                )
            )
        )
        .scalars()
        .all()
    )
    if len(cols) != len(set(collection_ids)):
        raise HTTPException(status_code=404, detail='Some collections not found')

    words = (
        (
            await session.execute(
                select(Word.id).where(Word.id.in_(word_ids), Word.author_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    if not words:
        raise HTTPException(status_code=400, detail='No words found')

    existing = set(
        (
            await session.execute(
                select(
                    WordsInCollections.word_id, WordsInCollections.collection_id
                ).where(
                    WordsInCollections.collection_id.in_(collection_ids),
                    WordsInCollections.word_id.in_(word_ids),
                )
            )
        ).all()
    )

    added = 0
    for cid in collection_ids:
        for wid in word_ids:
            if (wid, cid) in existing:
                continue
            session.add(WordsInCollections(word_id=wid, collection_id=cid))
            added += 1

    await session.commit()
    celery_app.send_task(
        UPDATE_COLLECTION_SUBSCRIPTION_INFO,
        args=[None, {'new_words': [str(w) for w in word_ids]}, None],
        kwargs={'collections_pks': [str(c) for c in collection_ids]},
    )
    return {'added': added}


async def collection_remove_words_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    word_slugs: list[str],
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    Collection = models['Collection']
    Word = models['Word']
    WordsInCollections = models['WordsInCollections']

    coll = (
        await session.execute(
            select(Collection).where(
                Collection.id == collection_id, Collection.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    word_ids = (
        (
            await session.execute(
                select(Word.id).where(
                    Word.slug.in_(word_slugs), Word.author_id == user_id
                )
            )
        )
        .scalars()
        .all()
    )
    if not word_ids:
        raise HTTPException(status_code=400, detail='No words found')

    await session.execute(
        delete(WordsInCollections).where(
            WordsInCollections.collection_id == coll.id,
            WordsInCollections.word_id.in_(word_ids),
        )
    )
    await session.commit()
    celery_app.send_task(
        UPDATE_COLLECTION_SUBSCRIPTION_INFO,
        args=[str(coll.id), {'removed_words': word_slugs}, None],
    )
    return await collection_retrieve_service(
        session=session, user_id=user_id, collection_id=collection_id, models=models
    )


async def collection_favorite_toggle_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    Collection = models['Collection']
    FavoriteCollection = models['FavoriteCollection']

    coll = (
        await session.execute(
            select(Collection).where(
                Collection.id == collection_id, Collection.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    existing = (
        await session.execute(
            select(FavoriteCollection).where(
                FavoriteCollection.user_id == user_id,
                FavoriteCollection.collection_id == coll.id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        await session.delete(existing)
    else:
        session.add(FavoriteCollection(user_id=user_id, collection_id=coll.id))

    await session.commit()
    return await collection_retrieve_service(
        session=session, user_id=user_id, collection_id=collection_id, models=models
    )


async def _toggle_flag_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    flag: str,
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    Collection = models['Collection']
    coll = (
        await session.execute(
            select(Collection).where(
                Collection.id == collection_id, Collection.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')
    current = getattr(coll, flag, None)
    if current is None:
        raise HTTPException(status_code=400, detail=f'Flag {flag} not supported')
    setattr(coll, flag, not bool(current))
    await session.commit()
    await session.refresh(coll)
    return map_collection(coll, include_words=True)


async def collection_allow_comments_switch_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    return await _toggle_flag_service(
        session=session,
        user_id=user_id,
        collection_id=collection_id,
        flag='allow_comments',
        models=models,
    )


async def collection_allow_suggestions_switch_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    return await _toggle_flag_service(
        session=session,
        user_id=user_id,
        collection_id=collection_id,
        flag='allow_suggestions',
        models=models,
    )


async def collection_allow_suggestions_notifications_switch_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    return await _toggle_flag_service(
        session=session,
        user_id=user_id,
        collection_id=collection_id,
        flag='allow_suggestions_notifications',
        models=models,
    )


def _split_ids(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [v for v in value.split(',') if v]


async def collection_subscription_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    models: dict = VOCAB_MODELS,
) -> CollectionSubscriptionDetailOut:
    Collection = models['Collection']
    CollectionSubscription = models['CollectionSubscription']

    sub = (
        await session.execute(
            select(CollectionSubscription, Collection)
            .join(Collection, Collection.id == CollectionSubscription.collection_id)
            .where(
                CollectionSubscription.collection_id == collection_id,
                CollectionSubscription.subscriber_id == user_id,
            )
        )
    ).first()

    if not sub:
        raise HTTPException(status_code=404, detail='Subscription not found')

    subscription, collection = sub
    return CollectionSubscriptionDetailOut(
        collection_id=collection.id,
        collection_slug=collection.slug,
        collection_title=collection.title,
        new_words=_split_ids(subscription.new_words),
        updated_words=_split_ids(subscription.updated_words),
    )
