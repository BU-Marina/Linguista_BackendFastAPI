"""Usage examples API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user

from .schemas import ExampleIn, ExampleOut, PageOut
from .services import (
    examples_list_service,
    example_create_service,
    example_retrieve_service,
    example_update_service,
    example_delete_service,
)

router = APIRouter(prefix="/examples", tags=["usage_examples"])


@router.get("", response_model=PageOut)
async def examples_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
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
    )


@router.post("", response_model=ExampleOut)
async def example_create(
    payload: ExampleIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await example_create_service(
        session=session, user_id=user.id, payload=payload
    )


@router.get("/{slug}", response_model=ExampleOut)
async def example_retrieve(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await example_retrieve_service(session=session, user_id=user.id, slug=slug)


@router.patch("/{slug}", response_model=ExampleOut)
async def example_update(
    slug: str,
    payload: ExampleIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await example_update_service(
        session=session, user_id=user.id, slug=slug, payload=payload
    )


@router.delete("/{slug}", status_code=204)
async def example_delete(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await example_delete_service(session=session, user_id=user.id, slug=slug)
