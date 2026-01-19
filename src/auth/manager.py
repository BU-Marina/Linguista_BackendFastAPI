"""User manager setup."""

import uuid
import logging
from typing import Optional

from fastapi_users import (
    BaseUserManager,
    UUIDIDMixin,
)
from fastapi_users.password import PasswordHelper
from fastapi_users.jwt import generate_jwt

from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from pydantic import SecretStr

from config.settings import settings
from core.db import AsyncSessionLocal
from apps.users.models import User, UserSettings
from core.celery.app import celery_app
from tasks.constants import (
    EMAIL_VERIFY,
    EMAIL_RESET_PASSWORD,
)

logger = logging.getLogger(__name__)

pwd_context = CryptContext(
    schemes=[
        'argon2',
        'bcrypt',
        'django_pbkdf2_sha256',
        'pbkdf2_sha256',
    ],
    deprecated='auto',  # позволит needs_update() вернуть True для устаревших схем
)


class CustomPasswordHelper(PasswordHelper):
    """Управление паролем."""

    def verify_and_update(
        self, plain_password: str, hashed_password: str
    ) -> tuple[bool, str | None]:
        """
        Проверяет plain_password против user.hashed_password.
        При успехе — если хеш нуждается в апгрейде, пересоздаёт новый хеш и сохраняет user.
        Возвращает True/False.
        """
        if not hashed_password:
            return (False, None)

        try:
            is_valid = pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return (False, None)

        # Если хеш помечен как устаревший — обновим его (rehash) и сохраним.
        new_hash = None
        if pwd_context.needs_update(hashed_password):
            new_hash = pwd_context.hash(plain_password)

        return (is_valid, new_hash)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """Управление пользователями."""

    user_db_model = User

    verification_token_secret: str
    reset_password_token_secret: str

    verification_token_lifetime_seconds: int = 60 * 60 * 24  # 24 hours
    reset_password_token_lifetime_seconds: int = 60 * 60  # 1 hour

    def __init__(self, user_db, password_helper):
        super().__init__(user_db, password_helper)

        # Если settings returns SecretStr:
        if isinstance(settings.VERIFICATION_TOKEN_SECRET, SecretStr):
            self.verification_token_secret = (
                settings.VERIFICATION_TOKEN_SECRET.get_secret_value()
            )
        else:
            self.verification_token_secret = settings.VERIFICATION_TOKEN_SECRET

        if isinstance(settings.RESET_PASSWORD_TOKEN_SECRET, SecretStr):
            self.reset_password_token_secret = (
                settings.RESET_PASSWORD_TOKEN_SECRET.get_secret_value()
            )
        else:
            self.reset_password_token_secret = settings.RESET_PASSWORD_TOKEN_SECRET

    async def authenticate(self, credentials) -> User | None:
        # First get the user by email to check verification status
        try:
            user_by_email = await self.user_db.get_by_email(credentials.username)
        except Exception:
            user_by_email = None

        # Call parent authenticate (checks password)
        user = await super().authenticate(credentials)

        # If credentials are valid but user is not verified, raise specific error
        if user_by_email and not getattr(user_by_email, 'is_verified', False):
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    'code': 'LOGIN_USER_NOT_VERIFIED',
                    'reason': 'Please confirm your email before logging in.',
                },
            )

        return user

    async def verify_password(self, plain_password: str, user) -> bool:
        try:
            return pwd_context.verify(plain_password, user.hashed_password)
        except Exception:
            return False

    async def on_after_register(self, user: User, request=None):
        """..."""

        await self.create_user_settings_callback(user, request)

        if settings.EMAIL_VERIFY:
            await self.verify_callback(user, None, request)

    async def on_after_request_verify(self, user: User, token: str, request=None):
        """..."""

        await self.verify_callback(user, token, request)

    async def on_after_forgot_password(self, user: User, token: str, request=None):
        """..."""

        await self.reset_password_callback(user, token, request)

    async def create_user_settings_callback(self, user: User, request=None):
        """
        Хук, который вызывается после регистрации (fastapi-users).
        Создаёт UserSettings с дефолтными значениями.
        """
        logger.debug('Creating default settings for user %s', user.id)

        # создаём новую сессию, потому что текущая сессия внутри user_db может быть в другом контексте
        async with AsyncSessionLocal() as session:
            try:
                async with session.begin():
                    settings = UserSettings(user_id=user.id)
                    session.add(settings)
                    # commit в конце блока

            except IntegrityError:
                # если уникальность нарушена (кто-то успел создать settings) — ничего не делаем
                # можно логировать debug
                logger.debug('UserSettings already exists for user %s', user.id)
                await session.rollback()

            except Exception:
                # на всякий случай — rollback и лог
                await session.rollback()
                raise

    async def verify_callback(
        self, user: User, token: Optional[str] = None, request=None
    ):
        """
        Попытка использовать внутренний fastapi-users метод генерации verification token,
        если он есть. Иначе — fallback: создаём JWT с полем 'type': 'verify'.
        Затем отправляем письмо в background.
        """

        # ручная генерация JWT
        if not token:
            payload = {
                'sub': str(user.id),
                'email': user.email,
                'aud': self.verification_token_audience,
            }
            token = generate_jwt(
                payload,
                self.verification_token_secret,
                self.verification_token_lifetime_seconds,
            )

        # отправляем письмо в фоне (не блокируем регистрацию)
        celery_app.send_task(
            EMAIL_VERIFY,
            args=[
                user.username,
                user.email,
                token,
            ],
        )

    async def reset_password_callback(self, user: User, token: str, request=None):
        """
        Отправляем письмо в background.
        """

        celery_app.send_task(
            EMAIL_RESET_PASSWORD,
            args=[
                user.username,
                user.email,
                token,
            ],
        )
