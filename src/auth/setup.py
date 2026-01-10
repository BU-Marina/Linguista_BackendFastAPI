"""..."""

import os

from fastapi import Depends
from fastapi_users import (
    FastAPIUsers,
)
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from sqlalchemy.ext.asyncio import AsyncSession

from dotenv import load_dotenv

from core.db import get_async_session
from auth.db import SQLAlchemyUserDatabaseUsernameOrEmail
from apps.users.models import User

from .manager import UserManager, CustomPasswordHelper

load_dotenv()

SECRET = os.getenv("SECRET_KEY")
ACCESS_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10"))


# user_db adapter
def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabaseUsernameOrEmail(session, User)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=ACCESS_EXPIRE_MINUTES * 60)


# JWT backend для FastAPI Users
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


# Корутина, возвращающая объект класса UserManager.
async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(
        user_db,
        password_helper=CustomPasswordHelper(),
    )


# FastAPIUsers instance
fastapi_users = FastAPIUsers(
    get_user_manager=get_user_manager,
    auth_backends=[auth_backend],
)

current_user = fastapi_users.current_user(active=True)
optional_current_user = fastapi_users.current_user(optional=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
