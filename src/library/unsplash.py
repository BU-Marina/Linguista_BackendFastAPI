"""Unsplash proxy client (FastAPI-compatible)."""

from __future__ import annotations

import os
import logging
from typing import Optional

import httpx

try:
    from api.v1.utils.exceptions import ServiceUnavailable  # type: ignore
except Exception:  # fallback for non-app contexts

    class ServiceUnavailable(Exception):
        ...


logger = logging.getLogger(__name__)

MAIN_URL = 'https://api.unsplash.com/'


def _headers() -> dict[str, str]:
    client_id = os.getenv('UNSPLASH_CLIENT_ID', '')
    return {
        'Accept-Version': 'v1',
        'Authorization': f'Client-ID {client_id}',
    }


async def fetch_images(
    *,
    search: Optional[str] = None,
    per_page: int = 20,
    page: int = 1,
    timeout: float = 20.0,
) -> dict:
    url = MAIN_URL + 'photos/'
    if search:
        url = MAIN_URL + 'search/photos/'
    params = {'per_page': per_page, 'page': page}
    if search:
        params['query'] = search

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=_headers(), params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:  # broad to mirror DRF behavior
        logger.error('Unsplash fetch failed: %s', exc)
        raise ServiceUnavailable from exc
