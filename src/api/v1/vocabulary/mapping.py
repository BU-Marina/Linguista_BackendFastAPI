"""Row/ORM -> Pydantic mappers for vocabulary."""

from __future__ import annotations


from .schemas import (
    WordListOut,
    WordReadOut,
)
from api.v1.translations.schemas import TranslationOut
from api.v1.definitions.schemas import DefinitionOut
from api.v1.usage_examples.schemas import ExampleOut
from api.v1.image_associations.schemas import ImageOut


def map_word(word) -> WordListOut:
    tags = [t.name for t in getattr(word, "tags", []) or []]
    types = []
    for t in getattr(word, "types", []) or []:
        name = getattr(t, "name_en", None) or getattr(t, "name_ru", None) or ""
        types.append(name)
    translations_count = len(getattr(word, "translations", []) or [])
    return WordListOut(
        id=word.id,
        slug=word.slug,
        text=word.text,
        language=getattr(word.language, "isocode", None),
        translations_count=translations_count,
        tags=tags,
        types=types,
        favorite=getattr(word, "_favorite", False),
        created=word.created,
        modified=word.modified,
    )


def map_word_read(word) -> WordReadOut:
    base = map_word(word)
    translations = [
        TranslationOut.model_validate(ex)
        for ex in getattr(word, "translations", []) or []
    ]
    examples = [
        ExampleOut.model_validate(ex) for ex in getattr(word, "examples", []) or []
    ]
    definitions = [
        DefinitionOut.model_validate(d) for d in getattr(word, "definitions", []) or []
    ]
    images = [
        ImageOut.model_validate(img)
        for img in getattr(word, "image_associations", []) or []
    ]
    return WordReadOut(
        **base.model_dump(),
        note=getattr(word, "note", None),
        activity_status=getattr(word, "activity_status", None),
        translations=translations,
        examples=examples,
        definitions=definitions,
        images=images,
    )
