"""Exercises endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user, optional_current_user
from .schemas import (
    ExerciseListOut,
    ExerciseDetailOut,
    ExerciseConfigurationIn,
    ExerciseConfigurationOut,
    WordsSetIn,
    WordsSetOut,
    PageOut,
)
from .services import (
    exercises_list_service,
    exercise_detail_service,
    exercise_favorite_toggle_service,
    exercise_configuration_get_service,
    exercise_configuration_create_service,
    words_sets_list_service,
    words_set_create_service,
    words_set_detail_service,
    words_set_update_service,
    words_set_delete_service,
)

router = APIRouter(prefix='/exercises', tags=['exercises'])


@router.get('', response_model=ExerciseListOut)
async def exercises_list(
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercises_list_service(
        session=session, user_id=user.id if user else None
    )


@router.get('/{slug}', response_model=ExerciseDetailOut)
async def exercise_detail(
    slug: str,
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_detail_service(
        session=session, slug=slug, user_id=user.id if user else None
    )


@router.post('/{slug}/favorite-toggle', response_model=ExerciseDetailOut)
async def exercise_favorite_toggle(
    slug: str,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_favorite_toggle_service(
        session=session, slug=slug, user_id=user.id
    )


@router.get('/{slug}/configuration', response_model=ExerciseConfigurationOut)
async def exercise_configuration_get(
    slug: str,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_configuration_get_service(
        session=session, user_id=user.id, slug=slug
    )


@router.post('/{slug}/configuration', response_model=ExerciseConfigurationOut)
async def exercise_configuration_create(
    slug: str,
    payload: ExerciseConfigurationIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_configuration_create_service(
        session=session,
        user_id=user.id,
        slug=slug,
        payload=payload,
    )


@router.get('/{slug}/words-sets', response_model=PageOut)
async def words_sets_list(
    slug: str,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    search: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await words_sets_list_service(
        session=session,
        user_id=user.id,
        slug=slug,
        page=page,
        limit=limit,
        search=search,
    )


@router.post('/{slug}/words-sets', response_model=WordsSetOut)
async def words_set_create(
    slug: str,
    payload: WordsSetIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await words_set_create_service(
        session=session, user_id=user.id, slug=slug, payload=payload
    )


@router.get('/{slug}/words-sets/{word_set_slug}', response_model=WordsSetOut)
async def words_set_detail(
    slug: str,
    word_set_slug: str,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await words_set_detail_service(
        session=session, user_id=user.id, slug=slug, word_set_slug=word_set_slug
    )


@router.patch('/{slug}/words-sets/{word_set_slug}', response_model=WordsSetOut)
async def words_set_update(
    slug: str,
    word_set_slug: str,
    payload: WordsSetIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await words_set_update_service(
        session=session,
        user_id=user.id,
        slug=slug,
        word_set_slug=word_set_slug,
        payload=payload,
    )


@router.delete('/{slug}/words-sets/{word_set_slug}')
async def words_set_delete(
    slug: str,
    word_set_slug: str,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    await words_set_delete_service(
        session=session, user_id=user.id, word_set_slug=word_set_slug
    )
    return {'status': 'ok'}
