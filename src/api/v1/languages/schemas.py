"""..."""

from typing import Optional

from pydantic import BaseModel, Field


class LearningLanguageInline(BaseModel):
    """
    Минимальная Pydantic-модель для LearningLanguageInLineSerializer.
    """
    language: str = Field(..., description="Language isocode, e.g. 'en'")
    level: Optional[str] = Field(None, description="Proficiency level (optional)")
    is_confirmed: bool = Field(False, description="Flag is_confirmed (read-only in serializer)")
    words_count: int = Field(0, description="Amount of words in this language for user (computed)")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }
