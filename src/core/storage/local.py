"""..."""

import aiofiles
from pathlib import Path
from urllib.parse import urljoin

from config.settings import MEDIA_ROOT, MEDIA_URL


class LocalStorage:
    """..."""

    def __init__(self, media_root: Path | str = MEDIA_ROOT, media_url: str = MEDIA_URL):
        self.media_root = Path(media_root)
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.media_url = media_url.rstrip("/") + "/"

    async def upload(self, file_bytes: bytes, dest_path: str) -> str:
        dest = self.media_root / dest_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(dest, "wb") as f:
            await f.write(file_bytes)

        # Возвращаем публичный URL (можно хранить относительный путь)
        return urljoin(self.media_url, dest_path)

    async def delete(self, path_or_url: str) -> None:
        # ожидаем либо URL (MEDIA_URL + path) либо относительный путь
        if path_or_url.startswith(self.media_url):
            rel = path_or_url[len(self.media_url):]
        else:
            rel = path_or_url

        p = self.media_root / rel

        try:
            p.unlink()
        except FileNotFoundError:
            pass

    async def exists(self, path_or_url: str) -> bool:
        if path_or_url.startswith(self.media_url):
            rel = path_or_url[len(self.media_url):]
        else:
            rel = path_or_url

        return (self.media_root / rel).exists()
