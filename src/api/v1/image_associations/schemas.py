"""Image associations schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ImageIn(BaseModel):
    image_url: str
    width: Optional[int] = None
    height: Optional[int] = None
    num: Optional[int] = None


class ImageOut(BaseModel):
    id: UUID
    image_url: str
    width: Optional[int] = None
    height: Optional[int] = None
    num: Optional[int] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PageOut(BaseModel):
    page: int
    limit: int
    count: int
    results: list
