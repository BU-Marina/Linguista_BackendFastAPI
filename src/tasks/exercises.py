"""Exercises-related Celery tasks."""

from __future__ import annotations

import asyncio

from sqlalchemy import update

from core.celery.app import celery_app as app
from core.db import get_async_session
from apps.exercises.models import ExerciseConfiguration

from .constants import DELETE_PREVIOUS_EX_CONF


@app.task(
    name=DELETE_PREVIOUS_EX_CONF, bind=True, max_retries=3, default_retry_delay=60
)
def delete_previous_confs_task(
    config_id: str, author_id: str, exercise_id: str, is_default: bool
):
    """
    Clears previous default configurations for the same user/exercise when a new default is created.
    """

    async def _run():
        async_session_maker = get_async_session()
        async with async_session_maker() as session:
            if not is_default:
                return
            await session.execute(
                update(ExerciseConfiguration)
                .where(
                    ExerciseConfiguration.author_id == author_id,
                    ExerciseConfiguration.exercise_id == exercise_id,
                    ExerciseConfiguration.id != config_id,
                )
                .values(is_default=False)
            )
            await session.commit()

    asyncio.run(_run())
