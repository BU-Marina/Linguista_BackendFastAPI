"""..."""

from fastapi import APIRouter

from .v1 import (
    auth_router,
    users_router,
    languages_router,
    upload_router,
    vocabulary_router,
    collections_router,
    translations_router,
    definitions_router,
    usage_examples_router,
    image_associations_router,
    published_router,
    exercises_router,
    notifications_router,
    ws_notifications_router,
    ws_exercises_router,
    unsplash_router,
    pinterest_router,
)

main_router = APIRouter(prefix='/api/v1')

main_router.include_router(auth_router)
main_router.include_router(users_router)
main_router.include_router(languages_router)
main_router.include_router(upload_router)
main_router.include_router(vocabulary_router)
main_router.include_router(collections_router)
main_router.include_router(translations_router)
main_router.include_router(definitions_router)
main_router.include_router(usage_examples_router)
main_router.include_router(image_associations_router)
main_router.include_router(published_router)
main_router.include_router(exercises_router)
main_router.include_router(notifications_router)
main_router.include_router(ws_notifications_router)
main_router.include_router(ws_exercises_router)
main_router.include_router(unsplash_router)
main_router.include_router(pinterest_router)
