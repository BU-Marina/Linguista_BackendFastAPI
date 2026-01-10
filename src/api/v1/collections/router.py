"""Collections API."""

from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user

from api.v1.vocabulary.params import build_collections_list_params
from .schemas import CollectionIn, CollectionReadOut, PageOut
from .services import (
    collections_list_service,
    collection_create_service,
    collection_retrieve_service,
    collection_update_service,
    collection_delete_service,
    collection_add_words_service,
    collection_remove_words_service,
    collection_favorite_toggle_service,
)

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=PageOut)
async def collections_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    tags: str | None = Query(None),
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
        favorite_only=favorite_only,
    )
    return await collections_list_service(
        session=session, user_id=user.id, params=params
    )


@router.post("", response_model=CollectionReadOut)
async def collection_create(
    payload: CollectionIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_create_service(
        session=session, user_id=user.id, payload=payload
    )


@router.get("/{slug}", response_model=CollectionReadOut)
async def collection_retrieve(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_retrieve_service(
        session=session, user_id=user.id, slug=slug
    )


@router.patch("/{slug}", response_model=CollectionReadOut)
async def collection_update(
    slug: str,
    payload: CollectionIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_update_service(
        session=session, user_id=user.id, slug=slug, payload=payload
    )


@router.delete("/{slug}", status_code=204)
async def collection_delete(
    slug: str,
    delete_words: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await collection_delete_service(
        session=session, user_id=user.id, slug=slug, delete_words=delete_words
    )


@router.post("/{slug}/add-words", response_model=CollectionReadOut)
async def collection_add_words(
    slug: str,
    word_slugs: list[str] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_add_words_service(
        session=session, user_id=user.id, slug=slug, word_slugs=word_slugs
    )


@router.post("/{slug}/remove-words", response_model=CollectionReadOut)
async def collection_remove_words(
    slug: str,
    word_slugs: list[str] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_remove_words_service(
        session=session, user_id=user.id, slug=slug, word_slugs=word_slugs
    )


@router.post("/{slug}/favorite", response_model=CollectionReadOut)
async def collection_favorite_toggle(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await collection_favorite_toggle_service(
        session=session, user_id=user.id, slug=slug
    )
