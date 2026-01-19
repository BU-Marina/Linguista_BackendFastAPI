"""Row/ORM -> Pydantic mappers for vocabulary."""

from __future__ import annotations


from .schemas import (
    WordListOut,
    WordReadOut,
)
from core.utils.i18n import i18n_get
from config.settings import settings
from api.v1.translations.schemas import TranslationOut
from api.v1.definitions.schemas import DefinitionOut
from api.v1.usage_examples.schemas import ExampleOut
from api.v1.image_associations.schemas import ImageOut


def map_word(word, lang: str | None = None) -> WordListOut:
    lang = lang or settings.DEFAULT_LANG
    tags = [t.name for t in getattr(word, 'tags', []) or []]
    types = []
    for t in getattr(word, 'types', []) or []:
        name = (
            i18n_get(t, 'name', lang)
            or getattr(t, 'name_en', None)
            or getattr(t, 'name_ru', None)
            or ''
        )
        types.append(name)

    # Get translations with minimal info needed for list view
    translations_list = getattr(word, 'translations', []) or []
    translations_count = len(translations_list)
    translations = [
        {
            'text': t.text,
            'language': getattr(t.language, 'isocode', None)
            if hasattr(t, 'language')
            else None,
        }
        for t in translations_list
    ]

    return WordListOut(
        id=word.id,
        slug=word.slug,
        text=word.text,
        language=getattr(word.language, 'isocode', None),
        translations_count=translations_count,
        translations=translations,
        tags=tags,
        types=types,
        favorite=getattr(word, '_favorite', False),
        created=word.created,
        modified=word.modified,
    )


def map_word_read(word, lang: str | None = None) -> WordReadOut:
    base = map_word(word, lang=lang)
    base_dict = base.model_dump()

    # Map translations with proper language conversion (replace the short version from base)
    translations = []
    for t in getattr(word, 'translations', []) or []:
        translations.append(
            TranslationOut(
                id=t.id,
                slug=t.slug,
                text=t.text,
                language=getattr(t.language, 'isocode', None)
                if hasattr(t, 'language')
                else None,
                created=t.created,
                modified=t.modified,
            )
        )

    examples = [
        ExampleOut.model_validate(ex) for ex in getattr(word, 'examples', []) or []
    ]
    definitions = [
        DefinitionOut.model_validate(d) for d in getattr(word, 'definitions', []) or []
    ]
    images = [
        ImageOut.model_validate(img)
        for img in getattr(word, 'image_associations', []) or []
    ]

    # Remove translations from base_dict to avoid duplicate keyword argument
    base_dict.pop('translations', None)

    return WordReadOut(
        **base_dict,
        note=getattr(word, 'note', None),
        activity_status=getattr(word, 'activity_status', None),
        translations=translations,
        examples=examples,
        definitions=definitions,
        images=images,
        image_associations=images,
        read_access_level=getattr(word, 'read_access_level', None),
        add_access_level=getattr(word, 'add_access_level', None),
        allow_access_change=getattr(word, 'allow_access_change', True),
        allow_comments=getattr(word, 'allow_comments', True),
    )
