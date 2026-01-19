"""..."""

import os
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env')  # аналог Config.env_file

    # DB
    DATABASE_URL: str
    MIGRATION_DATABASE_URL: str

    # REDIS
    REDIS_URL: str = 'redis://redis:6379/0'

    # CELERY
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL
    CELERY_BEAT_SCHEDULER: str = 'django_celery_beat.schedulers:DatabaseScheduler'

    # STORAGE
    USE_S3: bool
    S3_BUCKET: str
    S3_ENDPOINT: str

    # TOKENS
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    VERIFICATION_TOKEN_SECRET: str
    RESET_PASSWORD_TOKEN_SECRET: str

    # FASTAPI MAIL
    EMAIL_VERIFY: bool
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    SMTP_STARTTLS: bool
    SMTP_SSL_TLS: bool
    FRONTEND_VERIFY_URL: str
    FRONTEND_RESET_URL: str

    # DJANGO DEBUG VALUE
    DJANGO_DEBUG: bool

    # LOCALIZATION
    SUPPORTED_LANGS: List[str]
    DEFAULT_LANG: str

    # CORS
    CORS_ORIGINS: List[str] = [
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:4173',
        'http://127.0.0.1:4173',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ]

    # BACKEND URL (for constructing full URLs in API responses)
    BACKEND_URL: str = 'http://localhost:8000'


settings = Settings()
