"""Definitions API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user

from .schemas import DefinitionIn, DefinitionOut, PageOut
from .services import (
    definitions_list_service,
    definition_create_service,
    definition_retrieve_service,
    definition_update_service,
    definition_delete_service,
)

router = APIRouter(prefix="/definitions", tags=["definitions"])


@router.get("", response_model=PageOut)
async def definitions_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
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
    )


@router.post("", response_model=DefinitionOut)
async def definition_create(
    payload: DefinitionIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await definition_create_service(
        session=session, user_id=user.id, payload=payload
    )


@router.get("/{slug}", response_model=DefinitionOut)
async def definition_retrieve(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await definition_retrieve_service(
        session=session, user_id=user.id, slug=slug
    )


@router.patch("/{slug}", response_model=DefinitionOut)
async def definition_update(
    slug: str,
    payload: DefinitionIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await definition_update_service(
        session=session, user_id=user.id, slug=slug, payload=payload
    )


@router.delete("/{slug}", status_code=204)
async def definition_delete(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await definition_delete_service(session=session, user_id=user.id, slug=slug)
