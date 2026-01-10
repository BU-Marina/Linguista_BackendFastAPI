"""FastAPI-friendly exceptions."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


class APIException(HTTPException):
    """
    Lightweight DRF-like base exception for FastAPI.
    """

    def __init__(
        self,
        detail: Any = None,
        code: str | None = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        super().__init__(
            status_code=status_code, detail=detail or 'A server error occurred.'
        )
        self.code = code or 'error'


class ServiceUnavailable(APIException):
    def __init__(self, detail: str | None = None, code: str | None = None):
        super().__init__(
            detail=detail or 'Service temporarily unavailable, try again later.',
            code=code or 'service_unavailable',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
