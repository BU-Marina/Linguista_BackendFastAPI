"""Collections API."""

from fastapi import APIRouter, Depends, Query, Body
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user

from api.v1.core_schemas import FavoriteToggleOut
from api.v1.vocabulary.params import build_collections_list_params
from .schemas import (
    CollectionIn,
    CollectionReadOut,
    PageOut,
    CollectionResolveOut,
    CollectionSubscriptionDetailOut,
)
from .services import (
    collections_list_service,
    collection_create_service,
    collection_retrieve_service,
    collection_update_service,
    collection_delete_service,
    collection_add_words_service,
    collection_remove_words_service,
    collection_favorite_toggle_service,
    collection_resolve_slug_service,
    collection_add_words_bulk_service,
    collection_allow_comments_switch_service,
    collection_allow_suggestions_switch_service,
    collection_allow_suggestions_notifications_switch_service,
    collection_subscription_detail_service,
)

router = APIRouter(prefix='/collections', tags=['collections'])


@router.get('', response_model=PageOut)
async def collections_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    tags: str | None = Query(None),
    languages: str | None = Query(None),
    favorite_only: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    params = build_collections_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        tags=tags,
        languages=languages,
        favorite_only=favorite_only,
    )
    return await collections_list_service(
        session=session, user_id=user.id, params=params
    )


@router.post('', response_model=CollectionReadOut)
async def collection_create(
    payload: CollectionIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_create_service(
        session=session, user_id=user.id, payload=payload
    )


@router.get('/slug/{slug}', response_model=CollectionResolveOut)
async def collection_resolve_slug(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_resolve_slug_service(
        session=session, user_id=user.id, slug=slug
    )


@router.get('/{collection_id}', response_model=CollectionReadOut)
async def collection_retrieve(
    collection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_retrieve_service(
        session=session, user_id=user.id, collection_id=collection_id
    )


@router.patch('/{collection_id}', response_model=CollectionReadOut)
async def collection_update(
    collection_id: UUID,
    payload: CollectionIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_update_service(
        session=session, user_id=user.id, collection_id=collection_id, payload=payload
    )


@router.delete('/{collection_id}', status_code=204)
async def collection_delete(
    collection_id: UUID,
    delete_words: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await collection_delete_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
        delete_words=delete_words,
    )


@router.post('/{collection_id}/add-words', response_model=CollectionReadOut)
async def collection_add_words(
    collection_id: UUID,
    word_ids: list[str] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_add_words_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
        word_ids=word_ids,
    )


@router.post('/{collection_id}/remove-words', response_model=CollectionReadOut)
async def collection_remove_words(
    collection_id: UUID,
    word_ids: list[str] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_remove_words_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
        word_ids=word_ids,
    )


@router.post('/add-words-to-collections')
async def collections_add_words_bulk(
    collections: list[UUID] = Body(..., embed=True),
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_add_words_bulk_service(
        session=session, user_id=user.id, collection_ids=collections, word_ids=word_ids
    )


@router.post('/{collection_id}/allow-comments-switch', response_model=CollectionReadOut)
async def collection_allow_comments_switch(
    collection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_allow_comments_switch_service(
        session=session, user_id=user.id, collection_id=collection_id
    )


@router.post(
    '/{collection_id}/allow-suggestions-switch', response_model=CollectionReadOut
)
async def collection_allow_suggestions_switch(
    collection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_allow_suggestions_switch_service(
        session=session, user_id=user.id, collection_id=collection_id
    )


@router.post(
    '/{collection_id}/allow-suggestions-notifications-switch',
    response_model=CollectionReadOut,
)
async def collection_allow_suggestions_notifications_switch(
    collection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_allow_suggestions_notifications_switch_service(
        session=session, user_id=user.id, collection_id=collection_id
    )


@router.get(
    '/{collection_id}/subscription',
    response_model=CollectionSubscriptionDetailOut,
    responses={404: {'description': 'Subscription not found'}},
)
async def collection_subscription_detail(
    collection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_subscription_detail_service(
        session=session, user_id=user.id, collection_id=collection_id
    )


@router.post('/{collection_id}/favorite', response_model=FavoriteToggleOut)
async def collection_favorite_toggle(
    collection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_favorite_toggle_service(
        session=session, user_id=user.id, collection_id=collection_id
    )
