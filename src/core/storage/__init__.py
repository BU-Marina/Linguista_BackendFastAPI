"""..."""

from .local import LocalStorage
from .s3 import S3Storage

from config.settings import (
    settings,
    MEDIA_ROOT,
    MEDIA_URL,
)

# settings = Settings()

_local = LocalStorage(MEDIA_ROOT, MEDIA_URL)
_s3 = S3Storage(bucket=settings.S3_BUCKET, endpoint_url=settings.S3_ENDPOINT) if settings.USE_S3 else None

async def get_storage():
    return _s3 if _s3 is not None else _local
