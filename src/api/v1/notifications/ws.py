"""WebSocket endpoints for notifications."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from auth.setup import current_user
from core.db import get_async_session
from api.v1.utils.redis import get_redis
from .services import notification_mark_seen_service
from .ws_helpers import get_notifications_channel

router = APIRouter()


async def _consumer_loop(ws: WebSocket, channel_name: str):
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel_name)
    try:
        async for msg in pubsub.listen():
            if msg is None or msg['type'] != 'message':
                continue
            await ws.send_json({'type': 'notification', 'data': msg['data']})
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()


@router.websocket('/notifications/ws')
async def notifications_ws(
    websocket: WebSocket,
    user=Depends(current_user),
):
    await websocket.accept()
    channel = get_notifications_channel(user.id)
    consume_task = asyncio.create_task(_consumer_loop(websocket, channel))
    try:
        while True:
            payload = await websocket.receive_json()
            if payload.get('type') == 'read_notification' and payload.get(
                'notification_id'
            ):
                await notification_mark_seen_service(
                    session=await get_async_session(),
                    user_id=user.id,
                    notification_id=payload['notification_id'],
                )
    except WebSocketDisconnect:
        consume_task.cancel()
    finally:
        consume_task.cancel()
