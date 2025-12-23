from datetime import datetime

from pydantic import BaseModel


class MediaResponse(BaseModel):
    url: str
    type: str
    filename: str
    size: int
    uploaded_at: datetime
