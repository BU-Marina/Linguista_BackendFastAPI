"""..."""

from pydantic import BaseModel


class FavoriteToggleOut(BaseModel):
    """Response for favorite toggles."""

    favorite: bool
