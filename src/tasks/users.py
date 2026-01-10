"""Users celery tasks."""

import asyncio

from sqlalchemy import update

from core.celery.app import celery_app as app
from core.db import get_async_session
from apps.users.models import Subscription

from .constants import (
    CLEAR_USER_SUBSCRIPTION_INFO,
)


@app.task(
    bind=True, max_retries=3, default_retry_delay=60, name=CLEAR_USER_SUBSCRIPTION_INFO
)
def clear_subscription_info_task(author_pk: str, authors_pks: list[str] | None = None):
    """
    Celery task. Аналог Django clear_author_subscription_info.
    Делает UPDATE через отдельный event loop / async session.
    """

    async def _run():
        # use dependency getter to create session factory
        async_session_maker = get_async_session()
        async with async_session_maker() as session:
            if authors_pks:
                where_clause = Subscription.user_id.in_(authors_pks)
            else:
                where_clause = Subscription.user_id == author_pk

            await session.execute(
                update(Subscription)
                .where(where_clause)
                .values(
                    new_words="",
                    updated_words="",
                    new_collections="",
                )
            )
            await session.commit()

    asyncio.run(_run())
