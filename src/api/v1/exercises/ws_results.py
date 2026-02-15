"""Session results builder for exercises websocket."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.exercises.models import ExerciseSessionHistory, ExerciseSessionTasksHistory
from apps.vocabulary.models import WordActivityHistory


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
                selectinload(
                    ExerciseSessionHistory.words_activity_changes
                ).selectinload(WordActivityHistory.word),
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
                # Frontend expects string seconds here; mirror DRF `str(answer_time)`
                'answer_time': str(d.answer_time or 0),
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

    # Build words_activity_changes similar to DRF WordActivityHistorySerializer
    words_activity_changes: list[dict[str, Any]] = []
    for w in hist.words_activity_changes:
        words_activity_changes.append(
            {
                'id': str(w.id),
                'session': str(w.session_id) if w.session_id else None,
                'word': {
                    'id': str(w.word.id),
                    'slug': getattr(w.word, 'slug', ''),
                    'language': getattr(
                        getattr(w.word, 'language', None), 'isocode', ''
                    ),
                    'text': w.word.text,
                    'author': str(w.word.author_id),
                    'activity_status': w.new_activity_status,
                    'activity_progress': w.new_activity_progress,
                    'is_problematic': getattr(w.word, 'is_problematic', False),
                    'created': getattr(w.word, 'created', None).isoformat()
                    if getattr(w.word, 'created', None)
                    else None,
                    'modified': getattr(w.word, 'modified', None).isoformat()
                    if getattr(w.word, 'modified', None)
                    else None,
                },
                'previous_activity_status': w.previous_activity_status,
                'previous_activity_progress': w.previous_activity_progress,
                'new_activity_status': w.new_activity_status,
                'new_activity_progress': w.new_activity_progress,
                'upgrade': w.upgrade,
                'created': getattr(w, 'created', None).isoformat()
                if getattr(w, 'created', None)
                else None,
            }
        )

    # Status counters: how many words ended up in each new status
    status_counters: dict[str, int] = {}
    for w in hist.words_activity_changes:
        status = w.new_activity_status
        status_counters[status] = status_counters.get(status, 0) + 1

    # Average answer time across tasks
    answer_times = [d['answer_time'] for d in details if d['answer_time'] is not None]
    average_answer_time = sum(answer_times) / len(answer_times) if answer_times else 0

    return {
        'id': str(hist.id),
        'words_amount': hist.words_amount,
        'tasks_amount': hist.tasks_amount,
        'corrects_amount': hist.corrects_amount,
        'incorrects_amount': hist.incorrects_amount,
        'semi_corrects_amount': hist.semi_corrects_amount,
        'complete_time': hist.complete_time,
        'average_answer_time': average_answer_time,
        'status_counters': status_counters,
        'words_activity_changes': words_activity_changes,
        'details': details,
        'created': getattr(hist, 'created', None).isoformat()
        if getattr(hist, 'created', None)
        else None,
    }
