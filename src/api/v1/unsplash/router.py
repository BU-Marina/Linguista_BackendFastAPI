"""Unsplash endpoints."""

from fastapi import APIRouter, Depends, Query

from library.unsplash import fetch_images
from auth.setup import optional_current_user  # keep auth consistent (even if unused)

router = APIRouter(prefix='/unsplash', tags=['unsplash'])


@router.get('/images')
async def unsplash_images(
    search: str | None = Query(None),
    per_page: int = Query(20, ge=1, le=50),
    page: int = Query(1, ge=1),
    user=Depends(optional_current_user),
):
    return await fetch_images(search=search, per_page=per_page, page=page)
