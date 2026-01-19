"""Utility functions for URL construction."""

from urllib.parse import urljoin
from config.settings import settings, MEDIA_URL


def get_full_media_url(relative_path: str | None) -> str | None:
    """
    Convert a relative media path to a full URL.

    Args:
        relative_path: Relative path like "/media/images/..." or "images/..."

    Returns:
        Full URL like "http://localhost:8000/media/images/..." or None if input is None
    """
    if not relative_path:
        return None

    # If it's already a full URL, return as is
    if relative_path.startswith(('http://', 'https://')):
        return relative_path

    # If it starts with MEDIA_URL, use it directly
    if relative_path.startswith(MEDIA_URL):
        return urljoin(settings.BACKEND_URL, relative_path)

    # Otherwise, prepend MEDIA_URL
    media_path = urljoin(MEDIA_URL, relative_path)
    return urljoin(settings.BACKEND_URL, media_path)
