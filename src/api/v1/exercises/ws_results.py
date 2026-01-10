"""Session results builder for exercises websocket."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.exercises.models import ExerciseSessionHistory, ExerciseSessionTasksHistory


async def get_session_history_data(
    session: AsyncSession, history_id: UUID
) -> dict[str, Any]:
    """
    Builds results payload similar to DRF ExerciseSessionHistoryShortSerializer:
    - counters, complete_time
    - last task details list (with verdicts)
    """
    hist = (
        await session.execute(
            select(ExerciseSessionHistory)
            .where(ExerciseSessionHistory.id == history_id)
            .options(
                selectinload(ExerciseSessionHistory.details).selectinload(
                    ExerciseSessionTasksHistory.task_word
                ),
                selectinload(ExerciseSessionHistory.details).selectinload(
                    ExerciseSessionTasksHistory.right_answers_words
                ),
                selectinload(ExerciseSessionHistory.details).selectinload(
                    ExerciseSessionTasksHistory.right_answers_translations
                ),
                selectinload(ExerciseSessionHistory.details).selectinload(
                    ExerciseSessionTasksHistory.right_answers_definitions
                ),
            )
        )
    ).scalar_one_or_none()
    if not hist:
        return {}

    details = []
    for d in hist.details:
        details.append(
            {
                'task_index': d.task_index,
                'task': d.task,
                'task_type': d.task_type,
                'task_language': d.task_language,
                'answer': d.answer,
                'answers_list': d.answers_list,
                'verdict': d.verdict,
                'verdicts_list': d.verdicts_list,
                'answer_time': d.answer_time,
                'answer_time_limit': d.answer_time_limit,
                'task_word_id': str(d.task_word_id),
                'task_translation_id': str(d.task_translation_id)
                if d.task_translation_id
                else None,
                'right_answers_words': [str(w.id) for w in d.right_answers_words],
                'right_answers_translations': [
                    str(t.id) for t in d.right_answers_translations
                ],
                'right_answers_definitions': [
                    str(defn.id) for defn in d.right_answers_definitions
                ],
                'image_width': d.image_width,
                'image_height': d.image_height,
            }
        )

    return {
        'id': str(hist.id),
        'user_id': str(hist.user_id),
        'exercise_id': str(hist.exercise_id),
        'words_amount': hist.words_amount,
        'tasks_amount': hist.tasks_amount,
        'corrects_amount': hist.corrects_amount,
        'incorrects_amount': hist.incorrects_amount,
        'semi_corrects_amount': hist.semi_corrects_amount,
        'complete_time': hist.complete_time,
        'details': details,
    }
