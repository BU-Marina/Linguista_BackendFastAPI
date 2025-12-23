from fastapi import APIRouter

from auth.setup import auth_backend, fastapi_users

from .endpoints import auth_router
from .schemas import UserCreate, UserMeReadScalar

router = APIRouter()

router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix='/auth/jwt',
    tags=['auth'],
)
router.include_router(
    fastapi_users.get_register_router(UserMeReadScalar, UserCreate),
    prefix='/auth',
    tags=['auth'],
)
router.include_router(
    fastapi_users.get_verify_router(UserMeReadScalar),
    prefix="/auth",
    tags=["auth"],
)
router.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
router.include_router(
    auth_router,
    prefix='/auth',
    tags=['auth'],
)
