"""..."""

from fastapi import APIRouter

from .v1 import (
    auth_router,
    users_router,
    languages_router,
    upload_router,
)

main_router = APIRouter()

main_router.include_router(auth_router)
main_router.include_router(users_router)
main_router.include_router(languages_router)
main_router.include_router(upload_router, prefix="/upload")
