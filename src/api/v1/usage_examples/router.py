"""Usage examples API."""

from fastapi import APIRouter, Depends, Query, Body
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user

from .schemas import ExampleIn, ExampleOut, PageOut, ExampleResolveOut
from .services import (
    examples_list_service,
    example_create_service,
    example_retrieve_service,
    example_update_service,
    example_delete_service,
    example_add_words_service,
    example_remove_words_service,
    example_resolve_slug_service,
)

router = APIRouter(prefix='/examples', tags=['usage_examples'])


@router.get('', response_model=PageOut)
async def examples_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    collections: str | None = Query(
        None,
        description='Comma-separated collection ids to filter examples by linked words',
    ),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await examples_list_service(
        session=session,
        user_id=user.id,
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        collections=collections,
    )


@router.post('', response_model=ExampleOut)
async def example_create(
    payload: ExampleIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await example_create_service(
        session=session, user_id=user.id, payload=payload
    )


@router.get('/slug/{slug}', response_model=ExampleResolveOut)
async def example_resolve_slug(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await example_resolve_slug_service(
        session=session, user_id=user.id, slug=slug
    )


@router.get('/{example_id}', response_model=ExampleOut)
async def example_retrieve(
    example_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await example_retrieve_service(
        session=session, user_id=user.id, example_id=example_id
    )


@router.patch('/{example_id}', response_model=ExampleOut)
async def example_update(
    example_id: UUID,
    payload: ExampleIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await example_update_service(
        session=session, user_id=user.id, example_id=example_id, payload=payload
    )


@router.delete('/{example_id}', status_code=204)
async def example_delete(
    example_id: UUID,
    delete_words: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await example_delete_service(
        session=session,
        user_id=user.id,
        example_id=example_id,
        delete_words=delete_words,
    )


@router.post('/{example_id}/add-words', response_model=ExampleOut)
async def example_add_words(
    example_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await example_add_words_service(
        session=session, user_id=user.id, example_id=example_id, word_ids=word_ids
    )


@router.post('/{example_id}/remove-words', response_model=ExampleOut)
async def example_remove_words(
    example_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await example_remove_words_service(
        session=session, user_id=user.id, example_id=example_id, word_ids=word_ids
    )
