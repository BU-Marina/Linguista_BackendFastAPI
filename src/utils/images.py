"""..."""

from pydantic import AnyUrl


def _coerce_url(val):
    """..."""
    if val is None:
        return None

    # если это pydantic AnyUrl — привести к строке
    if isinstance(val, AnyUrl):
        return str(val)

    return val
