"""Exercises endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user, optional_current_user
from core.utils.i18n import parse_accept_language
from .schemas import (
    ExerciseListOut,
    ExerciseDetailOut,
    ExerciseConfigurationIn,
    ExerciseConfigurationOut,
    WordsSetIn,
    WordsSetOut,
    PageOut,
    RandomConfigIn,
)
from .services import (
    exercises_list_service,
    exercise_detail_service,
    exercise_favorite_toggle_service,
    exercise_configuration_get_service,
    exercise_configuration_create_service,
    exercise_configuration_detail_service,
    exercise_configuration_words_service,
    exercises_favorites_list_service,
    words_sets_list_service,
    words_set_create_service,
    words_set_detail_service,
    words_set_update_service,
    words_set_delete_service,
    exercise_available_words_service,
    exercise_available_collections_service,
    random_exercise_configuration_service,
    exercise_last_approach_incorrects_service,
    exercise_last_approach_service,
    exercise_shared_session_results_service,
    exercise_update_share_link_service,
    exercise_remove_share_link_service,
)

router = APIRouter(prefix='/exercises', tags=['exercises'])


@router.get('', response_model=ExerciseListOut)
async def exercises_list(
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
    accept_language: str | None = Header(None),
):
    return await exercises_list_service(
        session=session,
        user_id=user.id if user else None,
        lang=parse_accept_language(accept_language),
    )


@router.get('/favorites', response_model=PageOut)
async def exercises_favorites(
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
    accept_language: str | None = Header(None),
):
    return await exercises_favorites_list_service(
        session=session, user_id=user.id, lang=parse_accept_language(accept_language)
    )


@router.get('/{slug}', response_model=ExerciseDetailOut)
async def exercise_detail(
    slug: str,
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
    accept_language: str | None = Header(None),
):
    return await exercise_detail_service(
        session=session,
        slug=slug,
        user_id=user.id if user else None,
        lang=parse_accept_language(accept_language),
    )


@router.post('/{slug}/favorite-toggle', response_model=ExerciseDetailOut)
async def exercise_favorite_toggle(
    slug: str,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
    accept_language: str | None = Header(None),
):
    return await exercise_favorite_toggle_service(
        session=session,
        slug=slug,
        user_id=user.id,
        lang=parse_accept_language(accept_language),
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


@router.get(
    '/configurations/{config_id}',
    response_model=ExerciseConfigurationOut,
    responses={404: {'description': 'Configuration not found'}},
)
async def exercise_configuration_detail(
    config_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_configuration_detail_service(
        session=session, user_id=user.id, config_id=config_id
    )


@router.get(
    '/configurations/{config_id}/words',
    response_model=PageOut,
    responses={404: {'description': 'Configuration not found'}},
)
async def exercise_configuration_words(
    config_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=200),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_configuration_words_service(
        session=session,
        user_id=user.id,
        config_id=config_id,
        page=page,
        limit=limit,
    )


@router.post(
    '/random-configuration',
    response_model=ExerciseConfigurationOut,
    responses={404: {'description': 'No exercises available'}},
)
async def exercise_random_configuration(
    payload: RandomConfigIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await random_exercise_configuration_service(
        session=session,
        user_id=user.id,
        slug='',
        words_limit=payload.words_limit,
    )


@router.get(
    '/random-configuration',
    response_model=ExerciseConfigurationOut,
    responses={404: {'description': 'No exercises available'}},
)
async def exercise_random_configuration_get(
    words_limit: int | None = Query(None, ge=1, le=200),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await random_exercise_configuration_service(
        session=session,
        user_id=user.id,
        slug='',
        words_limit=words_limit,
    )


@router.get(
    '/{slug}/words-available',
    response_model=PageOut,
    responses={404: {'description': 'Exercise not found'}},
)
async def exercise_available_words(
    slug: str,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_available_words_service(
        session=session,
        user_id=user.id,
        slug=slug,
        page=page,
        limit=limit,
    )


@router.get(
    '/{slug}/collections-available',
    response_model=PageOut,
    responses={404: {'description': 'Exercise not found'}},
)
async def exercise_available_collections(
    slug: str,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_available_collections_service(
        session=session,
        user_id=user.id,
        slug=slug,
        page=page,
        limit=limit,
    )


@router.get(
    '/{slug}/last-approach-incorrects',
    response_model=list,
)
async def exercise_last_approach_incorrects(
    slug: str,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_last_approach_incorrects_service(
        session=session, user_id=user.id, slug=slug
    )


@router.get(
    '/{slug}/last-approach',
    response_model=dict,
)
async def exercise_last_approach(
    slug: str,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_last_approach_service(
        session=session, user_id=user.id, slug=slug
    )


@router.get(
    '/sessions/shared/{share_key}',
    response_model=dict,
)
async def exercise_shared_session_results(
    share_key: str,
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_shared_session_results_service(
        session=session, share_key=share_key
    )


@router.post(
    '/{slug}/last-approach/share',
    response_model=dict,
)
async def exercise_last_approach_generate_share_link(
    slug: str,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_update_share_link_service(
        session=session, user_id=user.id, slug=slug
    )


@router.delete(
    '/{slug}/last-approach/share',
    response_model=dict,
)
async def exercise_last_approach_remove_share_link(
    slug: str,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await exercise_remove_share_link_service(
        session=session, user_id=user.id, slug=slug
    )
