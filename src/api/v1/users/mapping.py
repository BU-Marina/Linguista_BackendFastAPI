"""row -> Pydantic"""

from __future__ import annotations

from typing import Any

from api.v1.utils.parsing import parse_separated_values

from .schemas import (
    UserListOut,
    UserReadOut,
    LearningLanguageInline,
)


# - `map_user_list_row(row) -> UserListOut`
# - `map_user_profile_row(row) -> UserReadOut`


def map_user_list_row(r: dict[str, Any]) -> UserListOut:
    """Маппинг строки из users_list (mappings()) в Pydantic."""
    return UserListOut(
        id=str(r["id"]) if "id" in r and r.get("id") is not None else None,
        slug=r["slug"],
        username=r["username"],
        first_name=r["first_name"],
        profile_image_url=r["profile_image_url"],
        profile_header_image_url=r["profile_header_image_url"],
        profile_description=r["profile_description"],
        is_teacher=bool(r["is_teacher"]),
        teaching_goal=r["teaching_goal"],
        interests=list(r.get("interests") or []),
        cities=list(r.get("cities") or []),
        native_languages=list(r.get("native_languages") or []),
        learning_languages=[
            LearningLanguageInline(**x) for x in (r.get("learning_languages") or [])
        ],
        taught_languages=[
            LearningLanguageInline(**x) for x in (r.get("taught_languages") or [])
        ],
        collections_count=r.get("collections_count"),
        subscribers_count=int(r.get("subscribers_count") or 0),
        is_subscribed=bool(r.get("is_subscribed") or False),
        enable_notifications=bool(r.get("enable_notifications") or False),
        learning_languages_overlap_percent=r.get("learning_languages_overlap_percent"),
        interests_overlap_percent=r.get("interests_overlap_percent"),
    )


def map_user_profile_row(r: dict[str, Any]) -> UserReadOut:
    """Маппинг строки из users_retrieve (mappings()) в Pydantic."""
    return UserReadOut(
        id=str(r["id"]),
        slug=r["slug"],
        username=r["username"],
        first_name=r["first_name"],
        profile_image_url=r.get("profile_image_url"),
        profile_header_image_url=r.get("profile_header_image_url"),
        profile_description=r["profile_description"],
        is_teacher=bool(r["is_teacher"]),
        teaching_goal=r["teaching_goal"],
        allow_subscriptions=bool(r.get("allow_subscriptions") or False),
        allow_buddy_search=bool(r.get("allow_buddy_search") or False),
        interests=list(r.get("interests") or []),
        cities=list(r.get("cities") or []),
        image_height=r.get("image_height"),
        image_width=r.get("image_width"),
        native_languages=list(r.get("native_languages") or []),
        learning_languages=[
            LearningLanguageInline(**x) for x in (r.get("learning_languages") or [])
        ],
        taught_languages=[
            LearningLanguageInline(**x) for x in (r.get("taught_languages") or [])
        ],
        collections_count=r.get("collections_count"),
        subscribers_count=int(r.get("subscribers_count") or 0),
        is_subscribed=bool(r.get("is_subscribed") or False),
        enable_notifications=bool(r.get("enable_notifications") or False),
        is_friend=bool(r.get("is_friend") or False),
        is_friend_request_sent=bool(r.get("is_friend_request_sent") or False),
        new_words=parse_separated_values(r.get("new_words")),
        updated_words=parse_separated_values(r.get("updated_words")),
        new_collections=parse_separated_values(r.get("new_collections")),
    )
