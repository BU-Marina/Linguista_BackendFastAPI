"""WebSocket endpoints for exercises sessions (feature-aligned)."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from api.v1.utils.redis import get_redis
from api.v1.notifications.ws import get_user_from_ws_token
from config.settings import settings
from apps.users.models import User
from apps.exercises.constants import ExercisesAnswerEnum
from sqlalchemy import select
import jwt
from jwt.exceptions import PyJWTError
import logging
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

router = APIRouter(prefix='/ws', tags=['ws'])
ws_router = router
logger = logging.getLogger(__name__)


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


@router.websocket('/exercises/session/')
async def exercises_session_ws(
    websocket: WebSocket,
    conf: str = Query(..., description='Exercise configuration id'),
    key: str | None = Query(
        None, description='JWT token for authentication (same as notifications WS)'
    ),
    session: AsyncSession = Depends(get_async_session),
):
    # Authenticate user via JWT query param.
    logger.info('Exercises WS: new connection, conf=%s, has_key=%s', conf, bool(key))
    print(f'[Exercises WS] New connection: conf={conf}, has_key={bool(key)}')

    # First, try shared helper (verifies audience & is_active).
    user = await get_user_from_ws_token(key) if key else None
    print(f'[Exercises WS] Helper user resolved: {bool(user)}')

    # If that fails but key is present, fall back to a more permissive decode
    # (no audience check) to match how the frontend token is actually issued.
    if not user and key:
        try:
            payload = jwt.decode(
                key,
                settings.SECRET_KEY,
                algorithms=['HS256'],
                options={'verify_aud': False},
            )
            user_id = payload.get('sub')
            logger.info('Exercises WS: fallback decode OK, sub=%s', user_id)
            print(f'[Exercises WS] Fallback decode OK, sub={user_id}')
            if user_id:
                result = await session.execute(
                    select(User).where(User.id == UUID(user_id))
                )
                user = result.scalar_one_or_none()
                logger.info('Exercises WS: user lookup result=%s', bool(user))
                print(f'[Exercises WS] User lookup result={bool(user)}')
        except (PyJWTError, ValueError) as e:
            logger.warning('Exercises WS: fallback decode error: %s', e)
            print(f'[Exercises WS] Fallback decode error: {e}')
            user = None

    if not user:
        logger.warning('Exercises WS: auth failed, closing with 1008 (conf=%s)', conf)
        print(f'[Exercises WS] Auth failed, closing 1008, conf={conf}')
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    # load config and words/tasks
    cfg = await load_config(session, conf)
    words = await fetch_config_words(session, cfg)
    tasks = await build_tasks(cfg, words, user)
    # Map word IDs to ORM objects for verdict logic that needs the base word
    word_by_id = {str(w.id): w for w in words}
    hist = await create_session_history(session, cfg, len(words), len(tasks), user.id)

    current_task_index = -1
    start_time = time.time()
    # None in config means "unlimited" – keep it as None so the frontend
    # doesn't treat 0 as "no more hints".
    hints_use_amount = cfg.hints_use_amount
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
                answers_list = payload.get('answers_list') or []
                task = tasks[current_task_index]
                word_obj = word_by_id.get(task.get('task_word'))
                verdict = await verdict_for_answer(
                    answer=answer,
                    answers_list=answers_list,
                    task=task,
                    word=word_obj,
                )

                # adjust totals if we already had verdicts for this task (FREE_INPUT_MAX mode)
                if state['verdicts']:
                    prev_final = state['verdicts'][-1]
                    if prev_final == ExercisesAnswerEnum.CORRECT:
                        hist.corrects_amount -= 1
                    elif prev_final == ExercisesAnswerEnum.SEMI_CORRECT:
                        hist.semi_corrects_amount -= 1
                    elif prev_final == ExercisesAnswerEnum.INCORRECT:
                        hist.incorrects_amount -= 1

                # Keep server-side answers list in sync with client payload,
                # and track per-answer verdicts using enum codes (C/I/SC)
                state['answers'] = answers_list
                state['verdicts'].append(verdict)
                state['hints_used'].extend(hints_used)
                state['total_answer_time'] += answer_time_val

                # decide final verdict: all correct => CORRECT; all incorrect => INCORRECT; else SEMI_CORRECT
                if all(v == ExercisesAnswerEnum.CORRECT for v in state['verdicts']):
                    final_verdict = ExercisesAnswerEnum.CORRECT
                elif all(v == ExercisesAnswerEnum.INCORRECT for v in state['verdicts']):
                    final_verdict = ExercisesAnswerEnum.INCORRECT
                else:
                    final_verdict = ExercisesAnswerEnum.SEMI_CORRECT

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
                    right_answers_list=task.get('right_answers_list', []),
                    hints_used=hints_used,
                    # Per-answer time (seconds), stringified to mirror DRF get_verdict_data
                    answer_time=str(answer_time_val),
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
                # Decrease counter only when a finite limit is configured.
                if hints_use_amount is not None and hints_use_amount > 0:
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
