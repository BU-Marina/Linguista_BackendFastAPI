"""App. Объект приложения."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routers import main_router
from config.settings import MEDIA_ROOT, MEDIA_URL, settings

app = FastAPI()

# убедиться, что каталог существует
Path(MEDIA_ROOT).mkdir(parents=True, exist_ok=True)

# settings = Settings()

# монтируем только если используем локальный storage (например в dev)
if not settings.USE_S3:
    app.mount(MEDIA_URL.rstrip('/'), StaticFiles(directory=str(MEDIA_ROOT)), name="media")

app.include_router(main_router)
