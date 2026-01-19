"""Pagination utilities."""

from urllib.parse import urlencode


def normalize_pagination(page: int | None, limit: int | None) -> tuple[int, int, int]:
    """
    Normalize pagination parameters and calculate offset.

    Returns:
        tuple: (page, limit, offset)
    """
    page = page or 1
    limit = limit or 32

    if page < 1:
        page = 1
    if limit < 1:
        limit = 1

    offset = (page - 1) * limit
    return page, limit, offset


def build_pagination_links(
    *,
    base_url: str,
    page: int,
    limit: int,
    total: int,
    query_params: dict | None = None,
) -> tuple[str | None, str | None]:
    """
    Build next and previous pagination links.

    Args:
        base_url: Base URL for the endpoint (e.g., "/api/v1/vocabulary/words")
        page: Current page number
        limit: Items per page
        total: Total number of items
        query_params: Additional query parameters to include in links

    Returns:
        tuple: (next_link, previous_link) - either can be None if not applicable
    """
    if query_params is None:
        query_params = {}

    # Remove page from query_params if it exists (we'll add it explicitly)
    query_params = {
        k: v for k, v in query_params.items() if k != 'page' and v is not None
    }

    # Calculate total pages
    total_pages = (total + limit - 1) // limit if limit > 0 else 1

    # Build next link
    next_link = None
    if page < total_pages:
        next_params = {**query_params, 'page': page + 1, 'limit': limit}
        next_link = f'{base_url}?{urlencode(next_params)}'

    # Build previous link
    previous_link = None
    if page > 1:
        prev_params = {**query_params, 'page': page - 1, 'limit': limit}
        previous_link = f'{base_url}?{urlencode(prev_params)}'

    return next_link, previous_link
