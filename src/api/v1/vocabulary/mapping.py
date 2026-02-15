"""Row/ORM -> Pydantic mappers for vocabulary."""

from __future__ import annotations


from .schemas import WordListOut, WordReadOut, SourceWordOut
from core.utils.i18n import i18n_get
from config.settings import settings
from api.v1.translations.schemas import TranslationOut
from api.v1.definitions.schemas import DefinitionOut
from api.v1.usage_examples.schemas import ExampleOut
from api.v1.image_associations.schemas import ImageOut
from core.constants import ActivityStatusEnum


_ACTIVITY_STATUS_LABELS = {
    code: label for code, label in ActivityStatusEnum.activity_statuses
}


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

    # Extract actual translation objects from the join table
    word_translations = getattr(word, 'wordtranslations', []) or []
    translations_list = [
        wt.translation
        for wt in word_translations
        if hasattr(wt, 'translation') and wt.translation
    ]
    # Get translations with minimal info needed for list view
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

    activity_status_code = getattr(word, 'activity_status', None)
    activity_status_human = _ACTIVITY_STATUS_LABELS.get(
        activity_status_code, activity_status_code
    )

    # Compute background_image_url from first associated image, if any
    word_image_assocs = getattr(word, 'wordimageassociations', []) or []
    images = [wia.image for wia in word_image_assocs if hasattr(wia, 'image')]
    background_image_url = images[0].image_url if images else None

    author_username = getattr(getattr(word, 'author', None), 'username', None)

    return WordListOut(
        id=word.id,
        slug=word.slug,
        text=word.text,
        language=getattr(word.language, 'isocode', None),
        activity_status=activity_status_human,
        activity_progress=getattr(word, 'activity_progress', None),
        is_problematic=getattr(word, 'is_problematic', False),
        background_image_url=background_image_url,
        translations_count=translations_count,
        translations=translations,
        tags=tags,
        types=types,
        favorite=getattr(word, '_favorite', False),
        author=author_username,
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
                words_count=getattr(t, 'words_count', 0),
                other_words_count=getattr(t, 'other_words_count', 0),
                last_6_words=getattr(t, 'last_6_words', []),
                created=t.created,
                modified=t.modified,
            )
        )

    examples = [
        ExampleOut(
            id=ex.id,
            slug=ex.slug,
            text=ex.text,
            translation=getattr(ex, 'translation', None),
            language=getattr(ex.language, 'isocode', None)
            if hasattr(ex, 'language') and ex.language
            else None,
            source=getattr(ex, 'source', None) or 'OTH',
            source_name=getattr(ex, 'source_name', None),
            source_url=getattr(ex, 'source_url', None),
            words_count=getattr(ex, 'words_count', 0),
            other_words_count=getattr(ex, 'other_words_count', 0),
            last_4_words=getattr(ex, 'last_4_words', []),
            created=ex.created,
            modified=ex.modified,
        )
        for ex in getattr(word, 'examples', []) or []
    ]
    definitions = [
        DefinitionOut(
            id=d.id,
            slug=d.slug,
            text=d.text,
            translation=d.translation,
            language=getattr(d.language, 'isocode', None)
            if hasattr(d, 'language') and d.language
            else None,
            words_count=getattr(d, 'words_count', 0),
            other_words_count=getattr(d, 'other_words_count', 0),
            last_4_words=getattr(d, 'last_4_words', []),
            created=d.created,
            modified=d.modified,
        )
        for d in getattr(word, 'definitions', []) or []
    ]
    images = [
        ImageOut.model_validate(img)
        for img in getattr(word, 'image_associations', []) or []
    ]

    # Remove fields we will override to avoid duplicate keyword arguments
    base_dict.pop('translations', None)
    base_dict.pop('author', None)

    # Build rich author payload for profile view (WordReadOut)
    author_obj = getattr(word, 'author', None)
    author_payload = None
    if author_obj is not None:
        author_payload = {
            'id': str(getattr(author_obj, 'id', None)),
            'slug': getattr(author_obj, 'slug', None),
            'username': getattr(author_obj, 'username', None),
            'first_name': getattr(author_obj, 'first_name', None),
            'profile_image_url': getattr(author_obj, 'profile_image_url', None),
            'profile_header_image_url': getattr(
                author_obj, 'profile_header_image_url', None
            ),
        }

    # Build source_word payload if word is borrowed
    source_word_payload = None
    source_word_obj = getattr(word, 'source_word', None)
    if source_word_obj is not None:
        source_author_obj = getattr(source_word_obj, 'author', None)
        source_author_payload = None
        if source_author_obj is not None:
            source_author_payload = {
                'slug': getattr(source_author_obj, 'slug', None),
                'username': getattr(source_author_obj, 'username', None),
                'first_name': getattr(source_author_obj, 'first_name', None),
                'profile_image_url': getattr(
                    source_author_obj, 'profile_image_url', None
                ),
            }
        source_word_payload = SourceWordOut(
            id=source_word_obj.id,
            slug=source_word_obj.slug,
            text=source_word_obj.text,
            author=source_author_payload,
        )

    return WordReadOut(
        **base_dict,
        author=author_payload,
        note=getattr(word, 'note', None),
        source_word=source_word_payload,
        translations=translations,
        examples=examples,
        definitions=definitions,
        images=images,
        image_associations=images,
        images_count=len(images),
        definitions_count=len(definitions),
        examples_count=len(examples),
        read_access_level=getattr(word, 'read_access_level', None),
        add_access_level=getattr(word, 'add_access_level', None),
        allow_access_change=getattr(word, 'allow_access_change', True),
        allow_comments=getattr(word, 'allow_comments', True),
    )
