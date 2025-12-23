"""..."""

from fastapi import APIRouter

from .v1 import (
    auth_router,
)

main_router = APIRouter()

main_router.include_router(auth_router)
# main_router.include_router(
#     meeting_room_router, prefix='/meeting_rooms', tags=['Meeting Rooms']
# )
# main_router.include_router(
#     reservation_router, prefix='/reservations', tags=['Reservations']
# )
