"""Definitions API."""

from fastapi import APIRouter, Depends, Query, Body
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user

from .schemas import DefinitionIn, DefinitionOut, PageOut, DefinitionResolveOut
from .services import (
    definitions_list_service,
    definition_create_service,
    definition_retrieve_service,
    definition_update_service,
    definition_delete_service,
    definition_add_words_service,
    definition_remove_words_service,
    definition_resolve_slug_service,
)

router = APIRouter(prefix='/definitions', tags=['definitions'])


@router.get('', response_model=PageOut)
async def definitions_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    collections: str | None = Query(
        None,
        description='Comma-separated collection ids to filter definitions by linked words',
    ),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await definitions_list_service(
        session=session,
        user_id=user.id,
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        collections=collections,
    )


@router.post('', response_model=DefinitionOut)
async def definition_create(
    payload: DefinitionIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await definition_create_service(
        session=session, user_id=user.id, payload=payload
    )


@router.get('/slug/{slug}', response_model=DefinitionResolveOut)
async def definition_resolve_slug(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await definition_resolve_slug_service(
        session=session, user_id=user.id, slug=slug
    )


@router.get('/{definition_id}', response_model=DefinitionOut)
async def definition_retrieve(
    definition_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await definition_retrieve_service(
        session=session, user_id=user.id, definition_id=definition_id
    )


@router.patch('/{definition_id}', response_model=DefinitionOut)
async def definition_update(
    definition_id: UUID,
    payload: DefinitionIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await definition_update_service(
        session=session, user_id=user.id, definition_id=definition_id, payload=payload
    )


@router.delete('/{definition_id}', status_code=204)
async def definition_delete(
    definition_id: UUID,
    delete_words: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await definition_delete_service(
        session=session,
        user_id=user.id,
        definition_id=definition_id,
        delete_words=delete_words,
    )


@router.post('/{definition_id}/add-words', response_model=DefinitionOut)
async def definition_add_words(
    definition_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await definition_add_words_service(
        session=session, user_id=user.id, definition_id=definition_id, word_ids=word_ids
    )


@router.post('/{definition_id}/remove-words', response_model=DefinitionOut)
async def definition_remove_words(
    definition_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await definition_remove_words_service(
        session=session, user_id=user.id, definition_id=definition_id, word_ids=word_ids
    )
