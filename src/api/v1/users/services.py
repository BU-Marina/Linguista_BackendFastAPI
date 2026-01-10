"""Users app services."""


# ### users_list_service
# - строит base query
# - считает total
# - применяет ordering, offset/limit
# - строит final jsonb_agg stmt
# - выполняет, мапит в `PageOut`

# ### users_retrieve_service
# - выполняет `build_user_profile_stmt(slug, viewer_id)`
# - если нет — 404
# - дергает `clear_author_subscription_info.delay(author_id)`
# - мапит в `UserReadOut`


from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, func, exists, literal, and_, or_, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from api.v1.utils.searching import apply_search
from api.v1.utils.ordering import apply_ordering
from core.celery.app import celery_app
from tasks.constants import (
    CLEAR_USER_SUBSCRIPTION_INFO,
)

from .models import USER_MODELS
from .schemas import (
    EnableNotificationsOut,
    FriendRequestSentOut,
    IsFriendOut,
    PageOut,
    SubscriptionToggleOut,
    UserReadOut,
)
from .params import UsersListParams
from .queries import (
    build_users_list_base_stmt,
    build_user_profile_stmt,
    build_users_page_stmt,
)
from .filters import (
    apply_users_filters,
)
from .mapping import (
    map_user_list_row,
    map_user_profile_row,
)


async def _build_paginated_response(
    *,
    session: AsyncSession,
    base_stmt,
    params: UsersListParams,
    request_user_id,
    models: dict,
) -> PageOut:
    """Общий пайплайн: search -> filters -> ordering -> pagination -> mapping."""
    User = models["User"]
    City = models["City"]
    Interest = models["Interest"]
    Language = models["Language"]
    UserLearningLanguage = models["UserLearningLanguage"]
    Subscription = models["Subscription"]
    users_user_interests = models["users_user_interests"]

    # search
    search_fields = [
        "username",
        "first_name",
        "profile_description",
        "cities.name",
        "interests.name",
    ]
    base_stmt = apply_search(
        base_stmt, User, params.search, search_fields, splitter="."
    )

    # domain filters
    base_stmt = apply_users_filters(
        base_stmt,
        params,
        User=User,
        City=City,
        Interest=Interest,
        Language=Language,
        UserLearningLanguage=UserLearningLanguage,
    )

    # total before pagination
    total = (
        await session.execute(select(func.count()).select_from(base_stmt.subquery()))
    ).scalar_one()

    # ordering helpers
    subscribers_count_expr = (
        select(func.count(Subscription.subscriber_id))
        .where(Subscription.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )

    if request_user_id:
        req_langs_count_sq = (
            select(func.count(func.distinct(UserLearningLanguage.language_id)))
            .where(UserLearningLanguage.user_id == request_user_id)
            .scalar_subquery()
        )
        req_interests_count_sq = (
            select(func.count(func.distinct(users_user_interests.c.interest_id)))
            .where(users_user_interests.c.user_id == request_user_id)
            .scalar_subquery()
        )

        req_lang_ids_sq = select(UserLearningLanguage.language_id).where(
            UserLearningLanguage.user_id == request_user_id
        )
        req_interest_ids_sq = select(users_user_interests.c.interest_id).where(
            users_user_interests.c.user_id == request_user_id
        )

        overlap_langs_count_expr = (
            select(func.count(func.distinct(UserLearningLanguage.language_id)))
            .where(
                (UserLearningLanguage.user_id == User.id)
                & (UserLearningLanguage.language_id.in_(req_lang_ids_sq))
            )
            .correlate(User)
            .scalar_subquery()
        )

        overlap_interests_count_expr = (
            select(func.count(func.distinct(users_user_interests.c.interest_id)))
            .where(
                (users_user_interests.c.user_id == User.id)
                & (users_user_interests.c.interest_id.in_(req_interest_ids_sq))
            )
            .correlate(User)
            .scalar_subquery()
        )

        learning_languages_overlap_percent_expr = func.coalesce(
            (
                func.coalesce(overlap_langs_count_expr, 0)
                / func.nullif(req_langs_count_sq, 0)
            )
            * 100.0,
            0.0,
        )
        interests_overlap_percent_expr = func.coalesce(
            (
                func.coalesce(overlap_interests_count_expr, 0)
                / func.nullif(req_interests_count_sq, 0)
            )
            * 100.0,
            0.0,
        )
    else:
        learning_languages_overlap_percent_expr = literal(0.0)
        interests_overlap_percent_expr = literal(0.0)

    ordering_map = {
        "learning_languages_overlap_percent": learning_languages_overlap_percent_expr,
        "interests_overlap_percent": interests_overlap_percent_expr,
        "subscribers_count": subscribers_count_expr,
        "last_login": User.last_login,
        "created": User.created,
        "username": User.username,
    }

    base_stmt = apply_ordering(
        base_stmt,
        params.ordering,
        ordering_map,
        default="-learning_languages_overlap_percent",
    )
    base_stmt = base_stmt.offset(params.offset).limit(params.limit)

    final_stmt = build_users_page_stmt(
        base_filtered_stmt=base_stmt,
        request_user_id=request_user_id,
        models=models,
    )

    rows = (await session.execute(final_stmt)).mappings().all()
    results = [map_user_list_row(dict(r)) for r in rows]
    return PageOut(page=params.page, limit=params.limit, count=total, results=results)


async def users_list_service(
    *,
    session: AsyncSession,
    request_user_id,
    params: UsersListParams,
    models: dict = USER_MODELS,
) -> PageOut:
    """Service для GET /users."""
    base = build_users_list_base_stmt(
        User=models["User"],
        UserSettings=models["UserSettings"],
        params=params,
    )
    return await _build_paginated_response(
        session=session,
        base_stmt=base,
        params=params,
        request_user_id=request_user_id,
        models=models,
    )


async def users_retrieve_service(
    *,
    session: AsyncSession,
    request_user_id,
    slug: str,
    models: dict = USER_MODELS,
) -> UserReadOut:
    """
    Service для GET /users/{slug}
    - достаёт профиль по slug
    - триггерит celery clear_author_subscription_info
    """
    stmt = build_user_profile_stmt(
        slug=slug,
        request_user_id=request_user_id,
        User=models["User"],
        UserSettings=models["UserSettings"],
        City=models["City"],
        Interest=models["Interest"],
        Language=models["Language"],
        UserLearningLanguage=models["UserLearningLanguage"],
        UserNativeLanguage=models["UserNativeLanguage"],
        Subscription=models["Subscription"],
        users_user_cities=models["users_user_cities"],
        users_user_interests=models["users_user_interests"],
    )

    row = (await session.execute(stmt)).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    celery_app.send_task(
        CLEAR_USER_SUBSCRIPTION_INFO,
        args=[str(row["id"])],
    )

    return map_user_profile_row(dict(row))


# -------------------------
# Subscriptions helpers
# -------------------------


async def _get_user_by_slug(session: AsyncSession, slug: str, *, models: dict):
    User = models["User"]
    UserSettings = models["UserSettings"]
    stmt = (
        select(
            User.id,
            User.slug,
            func.coalesce(UserSettings.allow_subscriptions, literal(True)).label(
                "allow_subscriptions"
            ),
        )
        .select_from(User)
        .outerjoin(UserSettings, UserSettings.user_id == User.id)
        .where(User.slug == slug)
    )
    return (await session.execute(stmt)).mappings().first()


async def subscribe_toggle_service(
    *,
    session: AsyncSession,
    actor_id: UUID,
    target_slug: str,
    models: dict = USER_MODELS,
) -> SubscriptionToggleOut:
    """Subscribe/unsubscribe current user to another user."""
    Subscription = models["Subscription"]

    target = await _get_user_by_slug(session, target_slug, models=models)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target_id = target["id"]
    if target_id == actor_id:
        raise HTTPException(status_code=400, detail="Cannot subscribe to yourself")

    if not target["allow_subscriptions"]:
        raise HTTPException(
            status_code=403, detail="Subscriptions are disabled for this user"
        )

    existing = (
        await session.execute(
            select(Subscription.id).where(
                Subscription.subscriber_id == actor_id,
                Subscription.user_id == target_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        await session.execute(
            delete(Subscription).where(
                Subscription.id == existing,
            )
        )
        await session.commit()
        return SubscriptionToggleOut(is_subscribed=False)

    try:
        session.add(Subscription(subscriber_id=actor_id, user_id=target_id))
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Already subscribed") from exc

    return SubscriptionToggleOut(is_subscribed=True)


def _ordered_pair(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    return (a, b) if a < b else (b, a)


async def enable_notifications_service(
    *,
    session: AsyncSession,
    actor_id: UUID,
    target_slug: str,
    enable: bool,
    models: dict = USER_MODELS,
) -> EnableNotificationsOut:
    """Turn notifications on/off for a subscription."""
    Subscription = models["Subscription"]

    target = await _get_user_by_slug(session, target_slug, models=models)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target_id = target["id"]
    subscription = (
        await session.execute(
            select(Subscription).where(
                Subscription.subscriber_id == actor_id,
                Subscription.user_id == target_id,
            )
        )
    ).scalar_one_or_none()
    if not subscription:
        raise HTTPException(
            status_code=409, detail="You are not subscribed to this user"
        )

    subscription.enable_notifications = enable
    await session.commit()
    return EnableNotificationsOut(enable_notifications=bool(enable))


async def subscriptions_list_service(
    *,
    session: AsyncSession,
    request_user_id: UUID,
    params: UsersListParams,
    models: dict = USER_MODELS,
) -> PageOut:
    """List authors current user is subscribed to."""
    User = models["User"]
    Subscription = models["Subscription"]
    base = build_users_list_base_stmt(
        User=User,
        UserSettings=models["UserSettings"],
        params=params,
    ).where(
        User.id.in_(
            select(Subscription.user_id).where(
                Subscription.subscriber_id == request_user_id
            )
        )
    )
    return await _build_paginated_response(
        session=session,
        base_stmt=base,
        params=params,
        request_user_id=request_user_id,
        models=models,
    )


async def friends_list_service(
    *,
    session: AsyncSession,
    request_user_id: UUID,
    params: UsersListParams,
    models: dict = USER_MODELS,
) -> PageOut:
    """Friends: пользователи, у которых есть связь в users_friend."""
    User = models["User"]
    Friend = models["Friend"]

    base = build_users_list_base_stmt(
        User=User,
        UserSettings=models["UserSettings"],
        params=params,
    ).where(
        exists().where(
            or_(
                and_(Friend.user_id == request_user_id, Friend.friend_id == User.id),
                and_(Friend.friend_id == request_user_id, Friend.user_id == User.id),
            )
        )
    )

    return await _build_paginated_response(
        session=session,
        base_stmt=base,
        params=params,
        request_user_id=request_user_id,
        models=models,
    )


async def friend_requests_list_service(
    *,
    session: AsyncSession,
    request_user_id: UUID,
    params: UsersListParams,
    models: dict = USER_MODELS,
) -> PageOut:
    """Friend requests sent TO current user."""
    User = models["User"]
    FriendRequest = models["FriendRequest"]

    base = build_users_list_base_stmt(
        User=User,
        UserSettings=models["UserSettings"],
        params=params,
    ).where(
        exists().where(
            and_(
                FriendRequest.requester_id == User.id,
                FriendRequest.target_id == request_user_id,
            )
        )
    )

    return await _build_paginated_response(
        session=session,
        base_stmt=base,
        params=params,
        request_user_id=request_user_id,
        models=models,
    )


async def friend_request_response_service(
    *,
    session: AsyncSession,
    request_user_id: UUID,
    username: str,
    accept: bool,
    params: UsersListParams,
    models: dict = USER_MODELS,
) -> PageOut:
    """Accept or decline a friend request."""
    User = models["User"]
    Friend = models["Friend"]
    FriendRequest = models["FriendRequest"]

    target_row = (
        await session.execute(select(User.id).where(User.username == username))
    ).scalar_one_or_none()
    if not target_row:
        raise HTTPException(status_code=404, detail="Request not found")

    target_id = target_row

    incoming_request = (
        await session.execute(
            select(FriendRequest.id).where(
                FriendRequest.requester_id == target_id,
                FriendRequest.target_id == request_user_id,
            )
        )
    ).scalar_one_or_none()

    if not incoming_request:
        raise HTTPException(status_code=404, detail="Request not found")

    await session.execute(
        delete(FriendRequest).where(FriendRequest.id == incoming_request)
    )

    if accept:
        a, b = _ordered_pair(request_user_id, target_id)
        try:
            session.add(Friend(user_id=a, friend_id=b))
            await session.commit()
        except IntegrityError:
            await session.rollback()
    else:
        await session.commit()

    # return updated requests list
    return await friend_requests_list_service(
        session=session,
        request_user_id=request_user_id,
        params=params,
        models=models,
    )


async def add_to_friends_service(
    *,
    session: AsyncSession,
    request_user_id: UUID,
    target_slug: str,
    models: dict = USER_MODELS,
) -> FriendRequestSentOut:
    """Send friend request => подписка в одну сторону."""
    Friend = models["Friend"]
    FriendRequest = models["FriendRequest"]

    target = await _get_user_by_slug(session, target_slug, models=models)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target_id = target["id"]
    if target_id == request_user_id:
        raise HTTPException(status_code=400, detail="Cannot add yourself")

    a, b = _ordered_pair(request_user_id, target_id)
    already_friends = (
        await session.execute(
            select(Friend.id).where(
                or_(
                    and_(Friend.user_id == a, Friend.friend_id == b),
                    and_(Friend.user_id == b, Friend.friend_id == a),
                )
            )
        )
    ).scalar_one_or_none()
    if already_friends:
        raise HTTPException(status_code=409, detail="Already friends")

    incoming = (
        await session.execute(
            select(FriendRequest.id).where(
                FriendRequest.requester_id == target_id,
                FriendRequest.target_id == request_user_id,
            )
        )
    ).scalar_one_or_none()
    outgoing = (
        await session.execute(
            select(FriendRequest.id).where(
                FriendRequest.requester_id == request_user_id,
                FriendRequest.target_id == target_id,
            )
        )
    ).scalar_one_or_none()

    if not outgoing and not incoming:
        try:
            session.add(
                FriendRequest(requester_id=request_user_id, target_id=target_id)
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()

    is_sent = incoming is not None or outgoing is not None
    return FriendRequestSentOut(is_friend_request_sent=bool(is_sent))


async def remove_from_friends_service(
    *,
    session: AsyncSession,
    request_user_id: UUID,
    target_slug: str,
    models: dict = USER_MODELS,
) -> IsFriendOut:
    """Remove friend (drop relation)."""
    Friend = models["Friend"]

    target = await _get_user_by_slug(session, target_slug, models=models)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target_id = target["id"]
    a, b = _ordered_pair(request_user_id, target_id)
    await session.execute(
        delete(Friend).where(
            or_(
                and_(Friend.user_id == a, Friend.friend_id == b),
                and_(Friend.user_id == b, Friend.friend_id == a),
            )
        )
    )
    await session.commit()
    return IsFriendOut(is_friend=False)


async def buddies_list_service(
    *,
    session: AsyncSession,
    request_user_id: UUID,
    params: UsersListParams,
    models: dict = USER_MODELS,
) -> PageOut:
    """Users with allow_buddy_search enabled."""
    User = models["User"]
    UserSettings = models["UserSettings"]

    base = build_users_list_base_stmt(
        User=User,
        UserSettings=UserSettings,
        params=params,
    ).where(
        func.coalesce(UserSettings.allow_buddy_search, literal(True)).is_(True),
        User.id != request_user_id,
    )

    return await _build_paginated_response(
        session=session,
        base_stmt=base,
        params=params,
        request_user_id=request_user_id,
        models=models,
    )


async def teachers_list_service(
    *,
    session: AsyncSession,
    request_user_id,
    params: UsersListParams,
    models: dict = USER_MODELS,
) -> PageOut:
    """Users with is_teacher flag."""
    User = models["User"]
    base = build_users_list_base_stmt(
        User=User,
        UserSettings=models["UserSettings"],
        params=params,
    ).where(User.is_teacher.is_(True))

    return await _build_paginated_response(
        session=session,
        base_stmt=base,
        params=params,
        request_user_id=request_user_id,
        models=models,
    )
