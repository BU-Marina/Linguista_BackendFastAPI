"""WebSocket endpoints for exercises sessions (feature-aligned)."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.setup import current_user
from core.db import get_async_session
from api.v1.utils.redis import get_redis
from .ws_helpers import (
    load_config,
    fetch_config_words,
    build_tasks,
    verdict_for_answer,
    create_session_history,
    update_history_totals,
    finalize_history,
    persist_task_history,
    build_hint_response,
    update_words_last_exercise_date,
)
from .ws_schemas import WsInitOut, TaskOut, VerdictOut, HintOut, ResultsOut
from .ws_results import get_session_history_data
from tasks.constants import UPGRADE_ACTIVITY_STATUS
from core.celery.app import celery_app

router = APIRouter()


async def _consumer_loop(ws: WebSocket, channel_name: str):
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel_name)
    try:
        async for msg in pubsub.listen():
            if msg is None or msg['type'] != 'message':
                continue
            await ws.send_json(msg['data'])
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()


@router.websocket('/exercises/session/ws')
async def exercises_session_ws(
    websocket: WebSocket,
    conf: str = Query(..., description='Exercise configuration id'),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    await websocket.accept()
    # load config and words/tasks
    cfg = await load_config(session, conf)
    words = await fetch_config_words(session, cfg)
    tasks = await build_tasks(cfg, words, user)
    hist = await create_session_history(session, cfg, len(words), len(tasks), user.id)

    current_task_index = -1
    start_time = time.time()
    hints_use_amount = cfg.hints_use_amount or 0
    word_ids_used = [w.id for w in words]

    async def send_json(payload: Any):
        await websocket.send_json(payload)

    current_task_state: dict[int, dict[str, Any]] = {}

    try:
        await send_json(
            WsInitOut(
                total_tasks=len(tasks), current_task=current_task_index
            ).model_dump()
        )
        while True:
            payload = await websocket.receive_json()
            msg_type = payload.get('type')

            if msg_type == 'next':
                current_task_index += 1
                if current_task_index < len(tasks):
                    # reset per-task state when moving to next
                    current_task_state[current_task_index] = {
                        'answers': [],
                        'verdicts': [],
                        'hints_used': [],
                        'history_id': None,
                        'total_answer_time': 0.0,
                    }
                    # optional time limit enforcement: client can track answer_time_limit in task payload
                    task_payload = TaskOut(
                        task=tasks[current_task_index],
                        total_tasks=len(tasks),
                        current_task=current_task_index,
                    ).model_dump()
                    await send_json(task_payload)
                else:
                    hist = await finalize_history(
                        session, hist, complete_time=time.time() - start_time
                    )
                    # build results payload with tasks summary
                    history_payload = await get_session_history_data(session, hist.id)
                    results = ResultsOut(results=history_payload).model_dump()
                    await send_json(results)
                    break

            elif msg_type == 'answer':
                state = current_task_state.setdefault(
                    current_task_index,
                    {
                        'answers': [],
                        'verdicts': [],
                        'hints_used': [],
                        'history_id': None,
                        'total_answer_time': 0.0,
                    },
                )
                answer = payload.get('answer', '')
                hints_used = payload.get('hints_used', [])
                answer_time_val = float(payload.get('answer_time', 0) or 0)
                task = tasks[current_task_index]
                verdict = verdict_for_answer(answer, task.get('right_answers', []))

                # adjust totals if we already had verdicts for this task
                if state['verdicts']:
                    prev_final = state['verdicts'][-1]
                    await update_history_totals(
                        session, hist, verdict=None
                    )  # no-op placeholder
                    if prev_final == 'correct':
                        hist.corrects_amount -= 1
                    elif prev_final == 'semi_correct':
                        hist.semi_corrects_amount -= 1
                    else:
                        hist.incorrects_amount -= 1

                state['answers'].append(answer)
                state['verdicts'].append(verdict)
                state['hints_used'].extend(hints_used)
                state['total_answer_time'] += answer_time_val

                # decide final verdict: all correct => correct; all incorrect => incorrect; else semi
                if all(v == 'correct' for v in state['verdicts']):
                    final_verdict = 'correct'
                elif all(v == 'incorrect' for v in state['verdicts']):
                    final_verdict = 'incorrect'
                else:
                    final_verdict = 'semi_correct'

                # update totals
                await update_history_totals(session, hist, final_verdict)

                history_obj = await persist_task_history(
                    session=session,
                    hist=hist,
                    task_index=current_task_index,
                    task=task,
                    answers_list=state['answers'],
                    verdicts_list=state['verdicts'],
                    answer_time=state['total_answer_time'],
                    hints_used=state['hints_used'],
                    existing_id=state['history_id'],
                )
                state['history_id'] = history_obj.id
                # fire activity status update
                celery_app.send_task(
                    UPGRADE_ACTIVITY_STATUS,
                    args=[
                        str(user.id),
                        str(task.get('task_word')),
                        str(hist.id),
                        final_verdict,
                    ],
                )

                verdict_payload = VerdictOut(
                    verdict=final_verdict,
                    corrects_amount=hist.corrects_amount,
                    incorrects_amount=hist.incorrects_amount,
                    semi_corrects_amount=hist.semi_corrects_amount,
                    right_answers=task.get('right_answers', []),
                    hints_used=hints_used,
                    task_index=current_task_index,
                ).model_dump()
                await send_json(verdict_payload)

            elif msg_type == 'hint_use':
                hint_code = payload.get('hint_code')
                # compute hint from task data
                hint_resp = build_hint_response(
                    tasks[current_task_index]
                    if current_task_index < len(tasks)
                    else {},
                    hint_code or '',
                    payload.get('used_keys', []),
                )
                if hints_use_amount > 0:
                    hints_use_amount -= 1
                hint_payload = HintOut(
                    hint_code=hint_code or '',
                    hint_data=hint_resp.get('hint_data', {}),
                    hints_use_amount=hints_use_amount,
                    id=str(tasks[current_task_index].get('task_related_id') or ''),
                    last_hint=hint_resp.get('last_hint', False),
                ).model_dump()
                await send_json(hint_payload)

    except WebSocketDisconnect:
        pass
    finally:
        try:
            await update_words_last_exercise_date(session, word_ids_used)
        except Exception:
            pass
