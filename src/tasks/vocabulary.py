"""Vocabulary-related celery tasks (lightweight update stubs)."""

from __future__ import annotations

import asyncio
from typing import Iterable

from sqlalchemy import update, func
from sqlalchemy.dialects.postgresql import insert

from core.celery.app import celery_app as app
from core.db import get_async_session
from apps.users.models import Subscription
from apps.vocabulary.models import (
    CollectionSubscription,
    ViewWord,
    ViewCollection,
)

from .constants import (
    UPDATE_AUTHOR_SUBSCRIPTION_INFO,
    UPDATE_COLLECTION_SUBSCRIPTION_INFO,
    CLEAR_EMPTY_VOCAB_OBJECTS,
    UPDATE_WORD_VIEWS,
    UPDATE_COLLECTION_VIEWS,
    CLEAR_COLLECTION_SUBSCRIPTION_INFO,
)


def _join_ids(items: Iterable[str] | None) -> str:
    if not items:
        return ""
    return ",".join(items)


@app.task(
    name=UPDATE_AUTHOR_SUBSCRIPTION_INFO,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def update_author_subscription_info_task(
    author_pk: str, payload: dict | None = None, host: str | None = None
):
    """
    Rough analogue of Django task:
    - payload keys can be new_words / removed_words / new_collections.
    - We store as comma-separated text in Subscription.new_words/updated_words/new_collections.
    """

    async def _run():
        async_session_maker = get_async_session()
        async with async_session_maker() as session:
            stmt = update(Subscription).where(Subscription.user_id == author_pk)
            values = {}
            if payload:
                if "new_words" in payload:
                    values["new_words"] = _join_ids(payload.get("new_words"))
                if "removed_words" in payload:
                    values["updated_words"] = _join_ids(payload.get("removed_words"))
                if "new_collections" in payload:
                    values["new_collections"] = _join_ids(
                        payload.get("new_collections")
                    )
            if values:
                stmt = stmt.values(**values)
                await session.execute(stmt)
                await session.commit()

    asyncio.run(_run())


@app.task(
    name=UPDATE_COLLECTION_SUBSCRIPTION_INFO,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def update_collection_subscription_info_task(
    collection_pk: str | None,
    payload: dict | None = None,
    host: str | None = None,
    collections_pks: list[str] | None = None,
):
    """
    Update collection subscriptions info fields; accepts either a single collection_pk or list in collections_pks.
    """

    async def _run():
        async_session_maker = get_async_session()
        async with async_session_maker() as session:
            target_ids = collections_pks or (
                [] if collection_pk is None else [collection_pk]
            )
            if not target_ids:
                return
            stmt = update(CollectionSubscription).where(
                CollectionSubscription.collection_id.in_(target_ids)
            )
            values = {}
            if payload:
                if "new_words" in payload:
                    values["new_words"] = _join_ids(payload.get("new_words"))
                if "removed_words" in payload:
                    values["updated_words"] = _join_ids(payload.get("removed_words"))
            if values:
                stmt = stmt.values(**values)
                await session.execute(stmt)
                await session.commit()

    asyncio.run(_run())


@app.task(
    name=CLEAR_EMPTY_VOCAB_OBJECTS, bind=True, max_retries=3, default_retry_delay=60
)
def clear_empty_objects_task(
    user_pk: str | None = None, payload: dict | None = None, all: bool = True
):
    """
    Stub cleanup task. Extend with real cleanup if needed.
    """
    return True


@app.task(name=UPDATE_WORD_VIEWS, bind=True, max_retries=3, default_retry_delay=60)
def update_word_views_task(user_pk: str, word_pk: str):
    """Upsert view record for a word."""

    async def _run():
        async_session_maker = get_async_session()
        async with async_session_maker() as session:
            stmt = (
                insert(ViewWord)
                .values(user_id=user_pk, word_id=word_pk, view_datetime=func.now())
                .on_conflict_do_update(
                    index_elements=["word_id", "user_id"],
                    set_={"view_datetime": func.now()},
                )
            )
            await session.execute(stmt)
            await session.commit()

    asyncio.run(_run())


@app.task(
    name=UPDATE_COLLECTION_VIEWS, bind=True, max_retries=3, default_retry_delay=60
)
def update_collection_views_task(user_pk: str, collection_pk: str):
    """Upsert view record for a collection."""

    async def _run():
        async_session_maker = get_async_session()
        async with async_session_maker() as session:
            stmt = (
                insert(ViewCollection)
                .values(
                    user_id=user_pk,
                    collection_id=collection_pk,
                    view_datetime=func.now(),
                )
                .on_conflict_do_update(
                    index_elements=["collection_id", "user_id"],
                    set_={"view_datetime": func.now()},
                )
            )
            await session.execute(stmt)
            await session.commit()

    asyncio.run(_run())


@app.task(
    name=CLEAR_COLLECTION_SUBSCRIPTION_INFO,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def clear_collection_subscription_info_task(collection_pk: str):
    """Reset notification payload fields for collection subscriptions."""

    async def _run():
        async_session_maker = get_async_session()
        async with async_session_maker() as session:
            await session.execute(
                update(CollectionSubscription)
                .where(CollectionSubscription.collection_id == collection_pk)
                .values(
                    new_words="",
                    updated_words="",
                )
            )
            await session.commit()

    asyncio.run(_run())
