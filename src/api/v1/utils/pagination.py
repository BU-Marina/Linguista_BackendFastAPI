"""Pagination utils."""


def normalize_pagination(page: int | None, limit: int | None) -> tuple[int, int, int]:
    page = page or 1
    limit = limit or 32

    if page < 1:
        page = 1
    if limit < 1:
        limit = 1
    if limit > 1000:
        limit = 1000

    offset = (page - 1) * limit
    return page, limit, offset
