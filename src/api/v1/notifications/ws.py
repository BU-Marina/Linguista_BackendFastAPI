"""WebSocket endpoints for notifications."""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import jwt
from jwt.exceptions import PyJWTError

from config.settings import settings
from core.db import AsyncSessionLocal
from api.v1.utils.redis import get_redis
from apps.users.models import User
from sqlalchemy import select
from .services import notification_mark_seen_service
from .ws_helpers import get_notifications_channel

router = APIRouter(prefix='/ws', tags=['ws'])


async def get_user_from_ws_token(token: str):
    """Extract and verify user from WebSocket token (query param)."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=['HS256'],
            audience=['fastapi-users:auth'],
        )
        user_id = payload.get('sub')
        if not user_id:
            return None

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.id == UUID(user_id), User.is_active.is_(True))
            )
            return result.scalar_one_or_none()
    except (PyJWTError, ValueError):
        return None


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


@router.websocket('/notifications/')
async def notifications_ws(
    websocket: WebSocket,
    key: str = Query(None, description='JWT token for authentication'),
):
    # Authenticate via query param token
    if not key:
        await websocket.close(code=4001, reason='Missing authentication token')
        return

    user = await get_user_from_ws_token(key)
    if not user:
        await websocket.close(code=4001, reason='Invalid authentication token')
        return

    await websocket.accept()
    channel = get_notifications_channel(user.id)
    consume_task = asyncio.create_task(_consumer_loop(websocket, channel))
    try:
        while True:
            payload = await websocket.receive_json()
            if payload.get('type') == 'read_notification' and payload.get(
                'notification_id'
            ):
                async with AsyncSessionLocal() as session:
                    await notification_mark_seen_service(
                        session=session,
                        user_id=user.id,
                        notification_id=payload['notification_id'],
                    )
    except WebSocketDisconnect:
        consume_task.cancel()
    finally:
        consume_task.cancel()
