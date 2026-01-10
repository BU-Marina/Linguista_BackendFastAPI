"""Users api endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import optional_current_user, current_user

from .schemas import (
    EnableNotificationsOut,
    FriendRequestSentOut,
    IsFriendOut,
    PageOut,
    SubscriptionToggleOut,
    UserReadOut,
)
from .params import build_users_list_params
from .services import (
    add_to_friends_service,
    buddies_list_service,
    enable_notifications_service,
    friend_request_response_service,
    friend_requests_list_service,
    friends_list_service,
    remove_from_friends_service,
    subscriptions_list_service,
    subscribe_toggle_service,
    teachers_list_service,
    users_list_service,
    users_retrieve_service,
)


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=PageOut)
async def users_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=1000),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    learning_languages: str | None = Query(None),
    native_languages: str | None = Query(None),
    taught_languages: str | None = Query(None),
    levels: str | None = Query(None),
    levels_exclude: str | None = Query(None),
    is_confirmed: bool | None = Query(None),
    interests: str | None = Query(None),
    interests_exclude: str | None = Query(None),
    cities: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(optional_current_user),
):
    params = build_users_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        learning_languages=learning_languages,
        native_languages=native_languages,
        taught_languages=taught_languages,
        levels=levels,
        levels_exclude=levels_exclude,
        is_confirmed=is_confirmed,
        interests=interests,
        interests_exclude=interests_exclude,
        cities=cities,
    )
    request_user_id = getattr(request_user, "id", None)
    return await users_list_service(
        session=session, request_user_id=request_user_id, params=params
    )


@router.get("/subscriptions", response_model=PageOut)
async def users_subscriptions(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=1000),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    learning_languages: str | None = Query(None),
    native_languages: str | None = Query(None),
    taught_languages: str | None = Query(None),
    levels: str | None = Query(None),
    levels_exclude: str | None = Query(None),
    is_confirmed: bool | None = Query(None),
    interests: str | None = Query(None),
    interests_exclude: str | None = Query(None),
    cities: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    params = build_users_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        learning_languages=learning_languages,
        native_languages=native_languages,
        taught_languages=taught_languages,
        levels=levels,
        levels_exclude=levels_exclude,
        is_confirmed=is_confirmed,
        interests=interests,
        interests_exclude=interests_exclude,
        cities=cities,
    )
    return await subscriptions_list_service(
        session=session,
        request_user_id=request_user.id,
        params=params,
    )


@router.post("/{slug}/subscribe", response_model=SubscriptionToggleOut)
async def subscribe_toggle(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    return await subscribe_toggle_service(
        session=session,
        actor_id=request_user.id,
        target_slug=slug,
    )


@router.post("/{slug}/allow-notifications", response_model=EnableNotificationsOut)
async def enable_notifications(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    return await enable_notifications_service(
        session=session,
        actor_id=request_user.id,
        target_slug=slug,
        enable=True,
    )


@router.delete("/{slug}/allow-notifications", response_model=EnableNotificationsOut)
async def disable_notifications(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    return await enable_notifications_service(
        session=session,
        actor_id=request_user.id,
        target_slug=slug,
        enable=False,
    )


@router.post("/{slug}/add-to-friends", response_model=FriendRequestSentOut)
async def add_to_friends(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    return await add_to_friends_service(
        session=session,
        request_user_id=request_user.id,
        target_slug=slug,
    )


@router.post("/{slug}/remove-from-friends", response_model=IsFriendOut)
async def remove_from_friends(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    return await remove_from_friends_service(
        session=session,
        request_user_id=request_user.id,
        target_slug=slug,
    )


@router.get("/friend-requests", response_model=PageOut)
async def friend_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=1000),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    learning_languages: str | None = Query(None),
    native_languages: str | None = Query(None),
    taught_languages: str | None = Query(None),
    levels: str | None = Query(None),
    levels_exclude: str | None = Query(None),
    is_confirmed: bool | None = Query(None),
    interests: str | None = Query(None),
    interests_exclude: str | None = Query(None),
    cities: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    params = build_users_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        learning_languages=learning_languages,
        native_languages=native_languages,
        taught_languages=taught_languages,
        levels=levels,
        levels_exclude=levels_exclude,
        is_confirmed=is_confirmed,
        interests=interests,
        interests_exclude=interests_exclude,
        cities=cities,
    )
    return await friend_requests_list_service(
        session=session,
        request_user_id=request_user.id,
        params=params,
    )


@router.post("/friend-requests/{username}", response_model=PageOut)
async def friend_request_accept(
    username: str,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=1000),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    learning_languages: str | None = Query(None),
    native_languages: str | None = Query(None),
    taught_languages: str | None = Query(None),
    levels: str | None = Query(None),
    levels_exclude: str | None = Query(None),
    is_confirmed: bool | None = Query(None),
    interests: str | None = Query(None),
    interests_exclude: str | None = Query(None),
    cities: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    params = build_users_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        learning_languages=learning_languages,
        native_languages=native_languages,
        taught_languages=taught_languages,
        levels=levels,
        levels_exclude=levels_exclude,
        is_confirmed=is_confirmed,
        interests=interests,
        interests_exclude=interests_exclude,
        cities=cities,
    )
    return await friend_request_response_service(
        session=session,
        request_user_id=request_user.id,
        username=username,
        accept=True,
        params=params,
    )


@router.delete("/friend-requests/{username}", response_model=PageOut)
async def friend_request_reject(
    username: str,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=1000),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    learning_languages: str | None = Query(None),
    native_languages: str | None = Query(None),
    taught_languages: str | None = Query(None),
    levels: str | None = Query(None),
    levels_exclude: str | None = Query(None),
    is_confirmed: bool | None = Query(None),
    interests: str | None = Query(None),
    interests_exclude: str | None = Query(None),
    cities: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    params = build_users_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        learning_languages=learning_languages,
        native_languages=native_languages,
        taught_languages=taught_languages,
        levels=levels,
        levels_exclude=levels_exclude,
        is_confirmed=is_confirmed,
        interests=interests,
        interests_exclude=interests_exclude,
        cities=cities,
    )
    return await friend_request_response_service(
        session=session,
        request_user_id=request_user.id,
        username=username,
        accept=False,
        params=params,
    )


@router.get("/friends", response_model=PageOut)
async def friends_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=1000),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    learning_languages: str | None = Query(None),
    native_languages: str | None = Query(None),
    taught_languages: str | None = Query(None),
    levels: str | None = Query(None),
    levels_exclude: str | None = Query(None),
    is_confirmed: bool | None = Query(None),
    interests: str | None = Query(None),
    interests_exclude: str | None = Query(None),
    cities: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    params = build_users_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        learning_languages=learning_languages,
        native_languages=native_languages,
        taught_languages=taught_languages,
        levels=levels,
        levels_exclude=levels_exclude,
        is_confirmed=is_confirmed,
        interests=interests,
        interests_exclude=interests_exclude,
        cities=cities,
    )
    return await friends_list_service(
        session=session,
        request_user_id=request_user.id,
        params=params,
    )


@router.get("/buddies", response_model=PageOut)
async def buddies_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=1000),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    learning_languages: str | None = Query(None),
    native_languages: str | None = Query(None),
    taught_languages: str | None = Query(None),
    levels: str | None = Query(None),
    levels_exclude: str | None = Query(None),
    is_confirmed: bool | None = Query(None),
    interests: str | None = Query(None),
    interests_exclude: str | None = Query(None),
    cities: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    params = build_users_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        learning_languages=learning_languages,
        native_languages=native_languages,
        taught_languages=taught_languages,
        levels=levels,
        levels_exclude=levels_exclude,
        is_confirmed=is_confirmed,
        interests=interests,
        interests_exclude=interests_exclude,
        cities=cities,
    )
    return await buddies_list_service(
        session=session,
        request_user_id=request_user.id,
        params=params,
    )


@router.get("/teachers", response_model=PageOut)
async def teachers_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=1000),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    learning_languages: str | None = Query(None),
    native_languages: str | None = Query(None),
    taught_languages: str | None = Query(None),
    levels: str | None = Query(None),
    levels_exclude: str | None = Query(None),
    is_confirmed: bool | None = Query(None),
    interests: str | None = Query(None),
    interests_exclude: str | None = Query(None),
    cities: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(current_user),
):
    params = build_users_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        learning_languages=learning_languages,
        native_languages=native_languages,
        taught_languages=taught_languages,
        levels=levels,
        levels_exclude=levels_exclude,
        is_confirmed=is_confirmed,
        interests=interests,
        interests_exclude=interests_exclude,
        cities=cities,
    )
    return await teachers_list_service(
        session=session,
        request_user_id=request_user.id,
        params=params,
    )


@router.get("/{slug}", response_model=UserReadOut)
async def users_retrieve(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    request_user=Depends(optional_current_user),
):
    request_user_id = getattr(request_user, "id", None)
    return await users_retrieve_service(
        session=session, request_user_id=request_user_id, slug=slug
    )
