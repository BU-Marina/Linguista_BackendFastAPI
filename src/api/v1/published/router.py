"""Published resources endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user, optional_current_user
from api.v1.vocabulary.params import (
    build_words_list_params,
    build_collections_list_params,
)
from .schemas import (
    WordsPageOut,
    WordReadOut,
    CollectionsPageOut,
    CollectionReadOut,
)
from .services import (
    published_words_list_service,
    published_word_detail_service,
    published_collections_list_service,
    published_collection_detail_service,
    _get_friend_ids,
    _get_subscription_author_ids,
)
from core.celery.app import celery_app
from tasks.constants import UPDATE_WORD_VIEWS, UPDATE_COLLECTION_VIEWS

router = APIRouter(prefix="/published", tags=["published"])


@router.get("/words", response_model=WordsPageOut)
async def published_words(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        languages=languages,
        tags=tags,
        types=types,
    )
    params, total, results = await published_words_list_service(
        session=session,
        user_id=user.id if user else None,
        params=params,
    )
    return WordsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get("/words/new", response_model=WordsPageOut)
async def published_words_new(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    search: str | None = Query(None),
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering="-created",
        search=search,
        languages=languages,
        tags=tags,
        types=types,
    )
    params, total, results = await published_words_list_service(
        session=session,
        user_id=user.id if user else None,
        params=params,
        ordering_override="-created",
    )
    return WordsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get("/words/friends", response_model=WordsPageOut)
async def published_words_friends(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    friend_ids = await _get_friend_ids(session, user.id)
    if not friend_ids:
        return WordsPageOut(page=page, limit=limit, count=0, results=[])

    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        languages=languages,
        tags=tags,
        types=types,
    )
    params, total, results = await published_words_list_service(
        session=session,
        user_id=user.id,
        params=params,
        author_ids=friend_ids,
    )
    return WordsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get("/words/subscriptions", response_model=WordsPageOut)
async def published_words_subscriptions(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    author_ids = await _get_subscription_author_ids(session, user.id)
    if not author_ids:
        return WordsPageOut(page=page, limit=limit, count=0, results=[])

    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        languages=languages,
        tags=tags,
        types=types,
    )
    params, total, results = await published_words_list_service(
        session=session,
        user_id=user.id,
        params=params,
        author_ids=author_ids,
    )
    return WordsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get("/words/favorites", response_model=WordsPageOut)
async def published_words_favorites(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        languages=languages,
        tags=tags,
        types=types,
    )
    params, total, results = await published_words_list_service(
        session=session,
        user_id=user.id,
        params=params,
        favorite_only=True,
    )
    return WordsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get("/words/{slug}", response_model=WordReadOut)
async def published_word_detail(
    slug: str,
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    result = await published_word_detail_service(
        session=session,
        user_id=user.id if user else None,
        slug=slug,
    )
    if user:
        celery_app.send_task(UPDATE_WORD_VIEWS, args=[str(user.id), str(result.id)])
    return result


@router.get("/collections", response_model=CollectionsPageOut)
async def published_collections(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    tags: str | None = Query(None),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_collections_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        tags=tags,
    )
    params, total, results = await published_collections_list_service(
        session=session,
        user_id=user.id if user else None,
        params=params,
    )
    return CollectionsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get("/collections/new", response_model=CollectionsPageOut)
async def published_collections_new(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    search: str | None = Query(None),
    tags: str | None = Query(None),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_collections_list_params(
        page=page,
        limit=limit,
        ordering="-created",
        search=search,
        tags=tags,
    )
    params, total, results = await published_collections_list_service(
        session=session,
        user_id=user.id if user else None,
        params=params,
        ordering_override="-created",
    )
    return CollectionsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get("/collections/friends", response_model=CollectionsPageOut)
async def published_collections_friends(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    tags: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    friend_ids = await _get_friend_ids(session, user.id)
    if not friend_ids:
        return CollectionsPageOut(page=page, limit=limit, count=0, results=[])

    params = build_collections_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        tags=tags,
    )
    params, total, results = await published_collections_list_service(
        session=session,
        user_id=user.id,
        params=params,
        author_ids=friend_ids,
    )
    return CollectionsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get("/collections/subscriptions", response_model=CollectionsPageOut)
async def published_collections_subscriptions(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    tags: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    author_ids = await _get_subscription_author_ids(session, user.id)
    if not author_ids:
        return CollectionsPageOut(page=page, limit=limit, count=0, results=[])

    params = build_collections_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        tags=tags,
    )
    params, total, results = await published_collections_list_service(
        session=session,
        user_id=user.id,
        params=params,
        author_ids=author_ids,
    )
    return CollectionsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get("/collections/favorites", response_model=CollectionsPageOut)
async def published_collections_favorites(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    tags: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_collections_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        tags=tags,
    )
    params, total, results = await published_collections_list_service(
        session=session,
        user_id=user.id,
        params=params,
        favorite_only=True,
    )
    return CollectionsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get("/collections/{slug}", response_model=CollectionReadOut)
async def published_collection_detail(
    slug: str,
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    result = await published_collection_detail_service(
        session=session,
        user_id=user.id if user else None,
        slug=slug,
    )
    if user:
        celery_app.send_task(
            UPDATE_COLLECTION_VIEWS, args=[str(user.id), str(result.id)]
        )
    return result
