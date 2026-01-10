"""..."""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "replace-me")

DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # django-celery-beat & results
    "django_celery_beat",
    # "django_celery_results",
    "sa_core",
    "sa_users",
    "sa_languages",
    "sa_achievements",
    "sa_chats",
    "sa_notifications",
    "sa_vocabulary",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    },
]

# DB: reuse DATABASE_URL env var
raw_url = os.getenv("DATABASE_URL")
if not raw_url:
    raise RuntimeError("DATABASE_URL is not set")

django_url = raw_url.replace("postgresql+asyncpg://", "postgresql://")

DATABASES = {"default": dj_database_url.parse(django_url)}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# static (for admin)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# django‑celery‑beat/result config
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://redis:6379/0")

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# optional: store celery results in DB
# CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://redis:6379/0")
# DJANGO_CELERY_RESULTS = {"RESULT_EXTENDED": True}

# языки, для которых реально есть колонки name_<lang>, country_<lang>, ...
ADMIN_I18N_LANGUAGES = [
    ("ru", "Русский"),
    ("en", "English"),
    # позже добавим: ("es", "Español"), ...
]

ADMIN_I18N_DEFAULT_LANGUAGE = "en"
