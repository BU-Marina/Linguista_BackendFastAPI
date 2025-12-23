"""..."""

from typing import Protocol


class StorageBackend(Protocol):
    async def upload(self, file_bytes: bytes, dest_path: str) -> str:
        """Upload bytes, return public URL or path to saved file."""
        ...

    async def delete(self, path_or_url: str) -> None:
        """Delete object by its stored path or url."""
        ...

    async def exists(self, path_or_url: str) -> bool:
        """..."""
        ...
