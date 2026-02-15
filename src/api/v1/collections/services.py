"""Collections services."""

from __future__ import annotations

from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, func, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.core_schemas import FavoriteToggleOut
from api.v1.utils.ordering import apply_ordering
from api.v1.utils.searching import apply_search
from api.v1.vocabulary.models import VOCAB_MODELS
from api.v1.vocabulary.params import CollectionsListParams
from core.celery.app import celery_app
from core.utils.urls import get_full_media_url
from tasks.constants import UPDATE_COLLECTION_SUBSCRIPTION_INFO
from .schemas import (
    CollectionIn,
    CollectionReadOut,
    PageOut,
    CollectionResolveOut,
    CollectionSubscriptionDetailOut,
    SourceCollectionOut,
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
    WordsInCollections = models['WordsInCollections']
    Word = models['Word']
    Language = models['Language']
    WordImageAssociations = models['WordImageAssociations']

    stmt = select(Collection).where(Collection.author_id == user_id)
    if params.tags:
        stmt = stmt.join(Collection.tags).where(Tag.name.in_(params.tags))
    if params.favorite_only:
        stmt = stmt.join(FavoriteCollection).where(
            FavoriteCollection.user_id == user_id
        )
    # Filter by words language
    if params.languages:
        subq = (
            select(WordsInCollections.collection_id)
            .join(Word, Word.id == WordsInCollections.word_id)
            .join(Language, Language.id == Word.language_id)
            .where(Language.isocode.in_(params.languages))
            .distinct()
        )
        stmt = stmt.where(Collection.id.in_(subq))

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
                select(WordsInCollections.collection_id, func.count())
                .where(WordsInCollections.collection_id.in_([c.id for c in rows]))
                .group_by(WordsInCollections.collection_id)
            )
        ).all()
    )

    # Get last 4 words per collection (for preview tiles)
    last_words_map: dict[UUID, list[dict]] = {}
    if rows:
        for coll_id in [c.id for c in rows]:
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

            last_words: list[dict] = []
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

    results = []
    for c in rows:
        c._favorite = c.id in fav_ids
        c._words_count = counts.get(c.id, 0)
        c._last_4_words = last_words_map.get(c.id, [])
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
    Word = models['Word']
    WordsInCollections = models['WordsInCollections']

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

    # Add words if provided
    words_added = []
    if payload.words:
        words = (
            (
                await session.execute(
                    select(Word).where(
                        Word.id.in_(payload.words), Word.author_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        if words:
            for w in words:
                session.add(WordsInCollections(word_id=w.id, collection_id=coll.id))
                words_added.append(w)
            await session.commit()
            if words_added:
                celery_app.send_task(
                    UPDATE_COLLECTION_SUBSCRIPTION_INFO,
                    args=[
                        str(coll.id),
                        {'new_words': [str(w.id) for w in words_added]},
                        None,
                    ],
                )

    coll._words_count = len(words_added)
    # For profile use full author info
    return map_collection(coll, include_words=False, for_published=True)


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
    WordTranslations = models['WordTranslations']
    WordTranslation = models['WordTranslation']
    WordImageAssociations = models['WordImageAssociations']
    WordDefinitions = models['WordDefinitions']
    WordUsageExamples = models['WordUsageExamples']
    CollectionComment = models['CollectionComment']
    CollectionSubscription = models['CollectionSubscription']

    coll = (
        await session.execute(
            select(Collection)
            .where(Collection.id == collection_id, Collection.author_id == user_id)
            .options(
                selectinload(Collection.source_collection).selectinload(
                    Collection.author
                ),
                selectinload(Collection.words_in_collections)
                .selectinload(WordsInCollections.word)
                .options(
                    selectinload(Word.tags),
                    selectinload(Word.types),
                    selectinload(Word.language),
                    selectinload(Word.wordimageassociations).selectinload(
                        WordImageAssociations.image
                    ),
                ),
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

    # Compute total translations count for words in this collection
    words_in_coll = getattr(coll, 'words_in_collections', []) or []
    word_ids = [wic.word_id for wic in words_in_coll]
    words_translations_count = 0
    words_definitions_count = 0
    words_examples_count = 0

    # Translations per word for words_texts
    translations_map: dict[UUID, list[str]] = {}
    if word_ids:
        words_translations_count = (
            await session.execute(
                select(func.count())
                .select_from(WordTranslations)
                .where(WordTranslations.word_id.in_(word_ids))
            )
        ).scalar_one()

        # Get translations mapping
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

    # Words texts mapping
    words_texts: dict[str, list[str]] = {}
    for w in words_in_coll:
        words_texts[w.word.text] = translations_map.get(w.word_id, [])

    # Words images (first image per word)
    words_images: list[str] = []
    for w in words_in_coll:
        word_image_assocs = getattr(w.word, 'wordimageassociations', []) or []
        if word_image_assocs:
            first_assoc = word_image_assocs[0]
            if hasattr(first_assoc, 'image') and first_assoc.image:
                image_url = getattr(first_assoc.image, 'image_url', None)
                if image_url:
                    words_images.append(get_full_media_url(image_url))

    words_images_count = len(words_images)

    # Favorite count for collection (all users)
    favorite_for_amount = (
        await session.execute(
            select(func.count())
            .select_from(FavoriteCollection)
            .where(FavoriteCollection.collection_id == coll.id)
        )
    ).scalar_one()

    # Borrowings count (collections that borrowed from this one)
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
        from api.v1.published.services import _map_comment

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

    # Subscribers count
    subscribers_count = (
        await session.execute(
            select(func.count())
            .select_from(CollectionSubscription)
            .where(CollectionSubscription.collection_id == coll.id)
        )
    ).scalar_one()

    # Words are fetched via a separate endpoint; omit words in profile response,
    # but use full author info (AuthorShortOut) like in published APIs.
    base = map_collection(coll, include_words=False, for_published=True)
    return CollectionReadOut(
        **base.model_dump(),
        words_translations_count=words_translations_count,
        words_images_count=words_images_count,
        words_definitions_count=words_definitions_count,
        words_examples_count=words_examples_count,
        allow_comments=bool(coll.allow_comments),
        allow_suggestions=bool(getattr(coll, 'allow_suggestions', True)),
        allow_suggestions_notifications=bool(
            getattr(coll, 'allow_suggestions_notifications', True)
        ),
        comments_count=comments_count,
        comments=comments,
        favorite_for_amount=favorite_for_amount,
        views_amount=0,
        borrowings_amount=borrowings_amount,
        borrowed=bool(coll.source_collection_id),
        source_collection=None
        if not getattr(coll, 'source_collection', None)
        else SourceCollectionOut(
            id=coll.source_collection.id,
            slug=coll.source_collection.slug,
            title=coll.source_collection.title,
            author=None
            if not getattr(coll.source_collection, 'author', None)
            else {
                'slug': coll.source_collection.author.slug,
                'username': coll.source_collection.author.username,
                'first_name': coll.source_collection.author.first_name,
                'profile_image_url': coll.source_collection.author.profile_image_url,
            },
        ),
        words_images=words_images,
        words_texts=words_texts,
        subscribers_count=subscribers_count,
    )


async def collection_update_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    payload: CollectionIn,
    models: dict = VOCAB_MODELS,
) -> CollectionReadOut:
    Collection = models['Collection']
    from core.constants import AccessLevelsEnum

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

    # Ignores collections with restricted mark.
    # If allow_access_change is False, ignore attempts to set access levels to PUBLIC
    valid_levels = {lvl for lvl, _ in AccessLevelsEnum.access_levels}

    if payload.read_access_level is not None:
        if not coll.allow_access_change:
            if payload.read_access_level == AccessLevelsEnum.PUBLIC:
                # Skip setting read_access_level to PUBLIC
                pass
            else:
                # Allow other access levels
                if payload.read_access_level not in valid_levels:
                    raise HTTPException(
                        status_code=400,
                        detail=f'Invalid read_access_level: {payload.read_access_level}',
                    )
                coll.read_access_level = payload.read_access_level
        else:
            # allow_access_change is True, allow all updates
            if payload.read_access_level not in valid_levels:
                raise HTTPException(
                    status_code=400,
                    detail=f'Invalid read_access_level: {payload.read_access_level}',
                )
            coll.read_access_level = payload.read_access_level

    if payload.add_access_level is not None:
        if not coll.allow_access_change:
            if payload.add_access_level == AccessLevelsEnum.PUBLIC:
                # Skip setting add_access_level to PUBLIC
                pass
            else:
                # Allow other access levels
                if payload.add_access_level not in valid_levels:
                    raise HTTPException(
                        status_code=400,
                        detail=f'Invalid add_access_level: {payload.add_access_level}',
                    )
                coll.add_access_level = payload.add_access_level
        else:
            # allow_access_change is True, allow all updates
            if payload.add_access_level not in valid_levels:
                raise HTTPException(
                    status_code=400,
                    detail=f'Invalid add_access_level: {payload.add_access_level}',
                )
            coll.add_access_level = payload.add_access_level

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
    FavoriteWord = models['FavoriteWord']
    FavoriteCollection = models['FavoriteCollection']
    CollectionSubscription = models['CollectionSubscription']
    WordTranslations = models['WordTranslations']
    WordDefinitions = models['WordDefinitions']
    WordUsageExamples = models['WordUsageExamples']
    WordImageAssociations = models['WordImageAssociations']

    coll = (
        await session.execute(
            select(Collection).where(
                Collection.id == collection_id, Collection.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail='Collection not found')

    # Get word IDs before deleting WordsInCollections entries
    word_ids = []
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

    # Explicitly delete favorites and subscriptions for this collection so that
    # SQLAlchemy/DB don't attempt to NULL the collection_id FK (it is NOT NULL).
    await session.execute(
        delete(FavoriteCollection).where(FavoriteCollection.collection_id == coll.id)
    )
    await session.execute(
        delete(CollectionSubscription).where(
            CollectionSubscription.collection_id == coll.id
        )
    )

    # Explicitly delete WordsInCollections entries before deleting the collection
    # to avoid SQLAlchemy trying to nullify the foreign key
    await session.execute(
        delete(WordsInCollections).where(WordsInCollections.collection_id == coll.id)
    )

    # Delete words (and all their related join-table rows & favorites) if requested
    if delete_words and word_ids:
        # Join tables referencing Word.id
        await session.execute(
            delete(WordTranslations).where(WordTranslations.word_id.in_(word_ids))
        )
        await session.execute(
            delete(WordDefinitions).where(WordDefinitions.word_id.in_(word_ids))
        )
        await session.execute(
            delete(WordUsageExamples).where(WordUsageExamples.word_id.in_(word_ids))
        )
        await session.execute(
            delete(WordImageAssociations).where(
                WordImageAssociations.word_id.in_(word_ids)
            )
        )
        # Favorites
        await session.execute(
            delete(FavoriteWord).where(FavoriteWord.word_id.in_(word_ids))
        )
        await session.execute(
            delete(Word).where(and_(Word.id.in_(word_ids), Word.author_id == user_id))
        )

    await session.delete(coll)
    await session.commit()


async def collection_add_words_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    collection_id: UUID,
    word_ids: list[str],
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
                select(Word).where(Word.id.in_(word_ids), Word.author_id == user_id)
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
    word_ids: list[str],
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
        (await session.execute(select(Word.id).where(Word.id.in_(word_ids))))
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
        args=[str(coll.id), {'removed_words': word_ids}, None],
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
    author_only: bool = True,
) -> CollectionReadOut:
    Collection = models['Collection']
    FavoriteCollection = models['FavoriteCollection']

    coll = (
        await session.execute(
            select(Collection).where(
                Collection.id == collection_id, Collection.author_id == user_id
            )
        )
        if author_only
        else await session.execute(
            select(Collection).where(Collection.id == collection_id)
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
        coll._favorite = False
    else:
        session.add(FavoriteCollection(user_id=user_id, collection_id=coll.id))
        coll._favorite = True

    await session.commit()
    return FavoriteToggleOut(
        favorite=coll._favorite,
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

    # Toggle the boolean flag
    setattr(coll, flag, not bool(current))
    await session.commit()

    # Reuse the main retrieve service to build a fully-populated CollectionReadOut
    # with all counters, comments, etc., and with proper eager loading.
    return await collection_retrieve_service(
        session=session, user_id=user_id, collection_id=collection_id, models=models
    )


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
