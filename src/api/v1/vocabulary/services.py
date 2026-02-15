"""Vocabulary services (simplified FastAPI port)."""

from __future__ import annotations

from uuid import UUID
from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import select, func, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.core_schemas import FavoriteToggleOut
from api.v1.utils.ordering import apply_ordering
from api.v1.utils.searching import apply_search
from core.celery.app import celery_app
from tasks.constants import (
    UPDATE_AUTHOR_SUBSCRIPTION_INFO,
    UPDATE_COLLECTION_SUBSCRIPTION_INFO,
    CLEAR_EMPTY_VOCAB_OBJECTS,
)

from .models import VOCAB_MODELS
from apps.vocabulary.models import (
    vocabulary_word_tags,
    vocabulary_word_types,
    vocabulary_word_share_with,
)
from .schemas import (
    WordIn,
    WordInPartial,
    WordReadOut,
    SynonymReadOut,
    PageOut,
    MultipleWordsIn,
    MultipleWordsCreateOut,
    RelationWordIn,
    RelatedWordsOut,
    TagOut,
    TypeOut,
    WordResolveOut,
    WordCollectionsIn,
    WordsIdsIn,
    WordAccessLevelUpdateIn,
    WordListWithAuthorOut,
)
from .mapping import map_word, map_word_read
from api.v1.collections.mapping import map_collection
from .params import WordsListParams
from .filters import WordFilterParams, apply_word_filters
from core.constants import AccessLevelsEnum
from apps.users.models import UserSettings
from core.utils.i18n import i18n_get


def _params_to_filter_params(params: WordsListParams) -> WordFilterParams:
    """Convert WordsListParams to WordFilterParams for the filters module."""
    return WordFilterParams(
        languages=params.languages,
        tags=params.tags,
        types=params.types,
        activity_status=params.activity_status,
        is_problematic=params.is_problematic,
        first_letter=params.first_letter,
        last_letter=params.last_letter,
        have_associations=params.have_associations,
        read_access=params.read_access,
        add_access=params.add_access,
        borrowed=params.borrowed,
        words=params.words,
        collections=params.collections,
        translations=params.translations,
        images=params.images,
        definitions=params.definitions,
        examples=params.examples,
        words_exclude=params.words_exclude,
        collections_exclude=params.collections_exclude,
        translations_exclude=params.translations_exclude,
        images_exclude=params.images_exclude,
        definitions_exclude=params.definitions_exclude,
        examples_exclude=params.examples_exclude,
        suggested_words_exclude=params.suggested_words_exclude,
        translations_count=params.translations_count,
        translations_count_gt=params.translations_count_gt,
        translations_count_lt=params.translations_count_lt,
        examples_count=params.examples_count,
        examples_count_gt=params.examples_count_gt,
        examples_count_lt=params.examples_count_lt,
        definitions_count=params.definitions_count,
        definitions_count_gt=params.definitions_count_gt,
        definitions_count_lt=params.definitions_count_lt,
        images_count=params.images_count,
        images_count_gt=params.images_count_gt,
        images_count_lt=params.images_count_lt,
        synonyms_count=params.synonyms_count,
        synonyms_count_gt=params.synonyms_count_gt,
        synonyms_count_lt=params.synonyms_count_lt,
        favorite_only=params.favorite_only,
    )


async def _resolve_language_id(
    session: AsyncSession, Language, isocode: str | None
) -> UUID | None:
    if not isocode:
        return None
    row = (
        await session.execute(select(Language.id).where(Language.isocode == isocode))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=400, detail=f'Language not found: {isocode}')
    return row


async def _create_word_with_nested(
    session: AsyncSession,
    *,
    user_id: UUID,
    payload,
    models: dict,
    default_language: str | None = None,
):
    """
    Build a word and nested objects without committing. Payload can be WordIn or RelationWordIn.
    """
    Word = models['Word']
    Tag = models['Tag']
    WordType = models['WordType']
    Language = models['Language']
    WordTranslation = models['WordTranslation']
    WordTranslations = models['WordTranslations']
    WordDefinitions = models['WordDefinitions']
    WordUsageExamples = models['WordUsageExamples']
    WordImageAssociations = models['WordImageAssociations']
    Definition = models['Definition']
    WordDefinitions = models['WordDefinitions']
    UsageExample = models['UsageExample']
    WordUsageExamples = models['WordUsageExamples']
    ImageAssociation = models['ImageAssociation']
    WordImageAssociations = models['WordImageAssociations']

    lang_iso = getattr(payload, 'language', None) or default_language
    lang_row = (
        await session.execute(select(Language).where(Language.isocode == lang_iso))
    ).scalar_one_or_none()
    if not lang_row:
        raise HTTPException(status_code=400, detail=f'Language not found: {lang_iso}')

    # Build kwargs; set flags explicitly so we never insert NULL into NOT NULL columns
    word_kwargs = dict(
        text=payload.text,
        language_id=lang_row.id,
        author_id=user_id,
        note=getattr(payload, 'note', None),
        is_problematic=getattr(payload, 'is_problematic', False),
    )

    word = Word(**word_kwargs)
    session.add(word)
    await session.flush()

    tags = getattr(payload, 'tags', None) or []
    if tags:
        tags_rows = (
            (
                await session.execute(
                    select(Tag).where(Tag.name.in_(tags), Tag.author_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        existing_names = {t.name for t in tags_rows}
        new_tags = []
        for name in tags:
            if name not in existing_names:
                t = Tag(name=name, author_id=user_id)
                session.add(t)
                new_tags.append(t)
                tags_rows.append(t)
                existing_names.add(name)
        # Flush new tags to ensure they're persisted with author_id before assigning to word
        if new_tags:
            await session.flush()
        word.tags = tags_rows

    types = getattr(payload, 'types', None) or []
    if types:
        types_rows = (
            (await session.execute(select(WordType).where(WordType.slug.in_(types))))
            .scalars()
            .all()
        )
        word.types = types_rows

    translations_objs = []
    for tr in getattr(payload, 'translations', []) or []:
        lang_id = (
            await _resolve_language_id(session, Language, tr.language)
            if tr.language
            else word.language_id
        )
        # Check if translation with same text, author_id, language_id already exists
        existing_tr = (
            await session.execute(
                select(WordTranslation).where(
                    func.lower(WordTranslation.text) == func.lower(tr.text),
                    WordTranslation.author_id == user_id,
                    WordTranslation.language_id == lang_id,
                )
            )
        ).scalar_one_or_none()

        if existing_tr:
            # Reuse existing translation
            t = existing_tr
        else:
            # Create new translation
            t = WordTranslation(text=tr.text, language_id=lang_id, author_id=user_id)
            session.add(t)
            await session.flush()

        # Check if join already exists
        existing_join = (
            await session.execute(
                select(WordTranslations).where(
                    WordTranslations.word_id == word.id,
                    WordTranslations.translation_id == t.id,
                )
            )
        ).scalar_one_or_none()
        if not existing_join:
            session.add(WordTranslations(word_id=word.id, translation_id=t.id))
        translations_objs.append(t)

    definitions_objs = []
    for d in getattr(payload, 'definitions', []) or []:
        lang_id = (
            await _resolve_language_id(session, Language, d.language)
            if d.language
            else word.language_id
        )
        # Check if definition with same text, author_id already exists
        existing_def = (
            await session.execute(
                select(Definition).where(
                    func.lower(Definition.text) == func.lower(d.text),
                    Definition.author_id == user_id,
                )
            )
        ).scalar_one_or_none()

        if existing_def:
            # Reuse existing definition
            definition = existing_def
        else:
            # Create new definition
            definition = Definition(
                text=d.text,
                translation=d.translation,
                language_id=lang_id,
                author_id=user_id,
            )
            session.add(definition)
            await session.flush()

        # Check if join already exists
        existing_join = (
            await session.execute(
                select(WordDefinitions).where(
                    WordDefinitions.word_id == word.id,
                    WordDefinitions.definition_id == definition.id,
                )
            )
        ).scalar_one_or_none()
        if not existing_join:
            session.add(WordDefinitions(word_id=word.id, definition_id=definition.id))
        definitions_objs.append(definition)

    examples_objs = []
    for ex in getattr(payload, 'examples', []) or []:
        lang_id = (
            await _resolve_language_id(session, Language, ex.language)
            if ex.language
            else word.language_id
        )
        # Check if example with same text, author_id already exists
        existing_ex = (
            await session.execute(
                select(UsageExample).where(
                    func.lower(UsageExample.text) == func.lower(ex.text),
                    UsageExample.author_id == user_id,
                )
            )
        ).scalar_one_or_none()

        if existing_ex:
            # Reuse existing example
            example = existing_ex
        else:
            # Create new example
            example = UsageExample(
                text=ex.text,
                translation=ex.translation,
                language_id=lang_id,
                author_id=user_id,
                source=ex.source or 'OTH',
                source_name=ex.source_name,
                source_url=ex.source_url,
            )
            session.add(example)
            await session.flush()

        # Check if join already exists
        existing_join = (
            await session.execute(
                select(WordUsageExamples).where(
                    WordUsageExamples.word_id == word.id,
                    WordUsageExamples.example_id == example.id,
                )
            )
        ).scalar_one_or_none()
        if not existing_join:
            session.add(WordUsageExamples(word_id=word.id, example_id=example.id))
        examples_objs.append(example)

    images_objs = []
    for img in getattr(payload, 'images', []) or []:
        image = ImageAssociation(
            image_url=img.image_url,
            width=img.width,
            height=img.height,
            num=img.num,
            author_id=user_id,
        )
        session.add(image)
        await session.flush()
        session.add(WordImageAssociations(word_id=word.id, image_id=image.id))
        images_objs.append(image)

    word.translations = translations_objs
    word.definitions = definitions_objs
    word.examples = examples_objs
    word.image_associations = images_objs
    return word


async def _get_or_create_related_word_ids(
    session: AsyncSession,
    *,
    items: list[RelationWordIn],
    user_id: UUID,
    models: dict,
    default_language: str | None = None,
) -> list[UUID]:
    Word = models['Word']
    ids: list[UUID] = []
    for rel in items:
        if rel.is_reference():
            stmt = select(Word.id).where(Word.author_id == user_id)
            if rel.id:
                stmt = stmt.where(Word.id == rel.id)
            if rel.slug:
                stmt = stmt.where(Word.slug == rel.slug)
            found = (await session.execute(stmt)).scalar_one_or_none()
            if not found:
                raise HTTPException(status_code=404, detail='Related word not found')
            ids.append(found)
            continue

        # new embedded word
        rel.ensure_creatable(default_language)
        new_word = await _create_word_with_nested(
            session,
            user_id=user_id,
            payload=rel,
            models=models,
            default_language=rel.language or default_language,
        )
        ids.append(new_word.id)
    return ids


async def _get_word_by_id(session: AsyncSession, user_id: UUID, word_id: UUID, models):
    Word = models['Word']
    return (
        await session.execute(
            select(Word)
            .where(Word.id == word_id, Word.author_id == user_id)
            .options(
                selectinload(Word.tags),
                selectinload(Word.types),
                selectinload(Word.language),
            )
        )
    ).scalar_one_or_none()


async def word_resolve_slug_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = VOCAB_MODELS,
) -> WordResolveOut:
    Word = models['Word']
    row = (
        await session.execute(
            select(Word.id, Word.slug).where(
                Word.slug == slug,
                Word.author_id == user_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Word not found')
    return WordResolveOut(id=row.id, slug=row.slug)


async def _get_related_words(
    session: AsyncSession,
    user_id,
    word_id,
    relation_model,
    models,
) -> list:
    Word = models['Word']
    rel = relation_model
    rows = (
        (
            await session.execute(
                select(Word)
                .join(rel, rel.to_word_id == Word.id)
                .where(rel.from_word_id == word_id, Word.author_id == user_id)
                .options(
                    selectinload(Word.tags),
                    selectinload(Word.types),
                    selectinload(Word.language),
                )
            )
        )
        .scalars()
        .all()
    )
    return rows


async def _add_bidirectional_relations(
    session: AsyncSession,
    src_word_id,
    target_word_ids: list[UUID],
    relation_model,
):
    rel = relation_model
    existing = set(
        (
            await session.execute(
                select(rel.from_word_id, rel.to_word_id).where(
                    rel.from_word_id == src_word_id, rel.to_word_id.in_(target_word_ids)
                )
            )
        ).all()
    )
    for tid in target_word_ids:
        if (src_word_id, tid) not in existing:
            session.add(rel(from_word_id=src_word_id, to_word_id=tid))
        if (tid, src_word_id) not in existing:
            session.add(rel(from_word_id=tid, to_word_id=src_word_id))


async def _remove_bidirectional_relations(
    session: AsyncSession,
    src_word_id,
    target_word_ids: list[UUID],
    relation_model,
):
    rel = relation_model
    await session.execute(
        delete(rel).where(
            or_(
                and_(
                    rel.from_word_id == src_word_id, rel.to_word_id.in_(target_word_ids)
                ),
                and_(
                    rel.to_word_id == src_word_id, rel.from_word_id.in_(target_word_ids)
                ),
            )
        )
    )


async def _map_words_list_page(
    *,
    session: AsyncSession,
    user_id: UUID,
    params: WordsListParams,
    lang: str | None = None,
    models: dict = VOCAB_MODELS,
):
    """..."""
    Word = models['Word']
    WordTranslations = models['WordTranslations']
    WordImageAssociations = models['WordImageAssociations']
    FavoriteWord = models['FavoriteWord']

    # Only the user's own words are shown in /vocabulary
    stmt = select(Word).where(Word.author_id == user_id)

    # Apply all filters using the filters module
    filter_params = _params_to_filter_params(params)
    stmt = apply_word_filters(stmt, filter_params, models=models, user_id=user_id)

    stmt = stmt.options(
        selectinload(Word.tags),
        selectinload(Word.types),
        selectinload(Word.wordtranslations).selectinload(WordTranslations.translation),
        selectinload(Word.wordimageassociations).selectinload(
            WordImageAssociations.image
        ),
        selectinload(Word.language),
        selectinload(Word.author),
    )

    search_fields = ['text']
    stmt = apply_search(stmt, Word, params.search, search_fields)

    ordering_map = {
        'text': Word.text,
        '-text': Word.text.desc(),
        'created': Word.created,
        '-created': Word.created.desc(),
        'modified': Word.modified,
        '-modified': Word.modified.desc(),
    }
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default='-created')

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    stmt = stmt.offset(params.offset).limit(params.limit)
    rows = (await session.execute(stmt)).scalars().all()

    # mark favorites
    fav_ids = set(
        (
            await session.execute(
                select(FavoriteWord.word_id).where(
                    FavoriteWord.user_id == user_id,
                    FavoriteWord.word_id.in_([w.id for w in rows]),
                )
            )
        )
        .scalars()
        .all()
    )
    results = []
    for w in rows:
        w._favorite = w.id in fav_ids
        results.append(map_word(w, lang=lang))

    # Build pagination links
    from api.v1.utils.pagination import build_pagination_links

    next_link, previous_link = build_pagination_links(
        base_url='/vocabulary/words',
        page=params.page,
        limit=params.limit,
        total=total,
        query_params={
            'ordering': params.ordering,
            'search': params.search,
            'favorite_only': params.favorite_only,
        },
    )

    return (total, results, next_link, previous_link)


async def words_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    params: WordsListParams,
    lang: str | None = None,
) -> PageOut:
    total, results, next_link, previous_link = await _map_words_list_page(
        session=session,
        user_id=user_id,
        params=params,
        lang=lang,
    )

    return PageOut(
        page=params.page,
        limit=params.limit,
        count=total,
        results=results,
        next=next_link,
        previous=previous_link,
    )


async def word_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    payload: WordIn,
    lang: str | None = None,
    models: dict = VOCAB_MODELS,
) -> WordReadOut:
    Word = models['Word']
    Synonym = models['Synonym']
    Antonym = models['Antonym']
    Similar = models['Similar']

    word = await _create_word_with_nested(
        session,
        user_id=user_id,
        payload=payload,
        models=models,
        default_language=payload.language,
    )

    # synonyms / antonyms / similars (bidirectional add)
    if payload.synonyms:
        target_ids = await _get_or_create_related_word_ids(
            session,
            items=payload.synonyms,
            user_id=user_id,
            models=models,
            default_language=payload.language,
        )
        await _add_bidirectional_relations(session, word.id, target_ids, Synonym)
    if payload.antonyms:
        target_ids = await _get_or_create_related_word_ids(
            session,
            items=payload.antonyms,
            user_id=user_id,
            models=models,
            default_language=payload.language,
        )
        await _add_bidirectional_relations(session, word.id, target_ids, Antonym)
    if payload.similars:
        target_ids = await _get_or_create_related_word_ids(
            session,
            items=payload.similars,
            user_id=user_id,
            models=models,
            default_language=payload.language,
        )
        await _add_bidirectional_relations(session, word.id, target_ids, Similar)

    await session.commit()
    # Reload word with all relationships including source_word
    word = (
        await session.execute(
            select(Word)
            .where(Word.id == word.id)
            .options(
                selectinload(Word.tags),
                selectinload(Word.types),
                selectinload(Word.language),
                selectinload(Word.author),
                selectinload(Word.source_word).selectinload(Word.author),
            )
        )
    ).scalar_one()
    word._favorite = False
    celery_app.send_task(
        UPDATE_AUTHOR_SUBSCRIPTION_INFO,
        args=[str(user_id), {'new_words': [str(word.id)]}, None],
    )
    return map_word_read(word, lang=lang)


async def multiple_words_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    payload: MultipleWordsIn,
    params: WordsListParams | None = None,
    models: dict = VOCAB_MODELS,
) -> MultipleWordsCreateOut:
    Word = models['Word']
    Collection = models['Collection']
    WordsInCollections = models['WordsInCollections']
    Synonym = models['Synonym']
    Antonym = models['Antonym']
    Similar = models['Similar']

    created_words = []
    updated_words = []

    for item in payload.words:
        # Check if this is an update (has ID) or create (no ID)
        if item.id:
            # Update existing word - handle manually to avoid committing in the middle
            word_obj = (
                await session.execute(
                    select(Word)
                    .where(Word.id == item.id, Word.author_id == user_id)
                    .options(selectinload(Word.tags), selectinload(Word.types))
                )
            ).scalar_one_or_none()
            if not word_obj:
                raise HTTPException(
                    status_code=404, detail=f'Word not found: {item.id}'
                )

            # Update basic fields
            Language = models['Language']
            lang_row = (
                await session.execute(
                    select(Language).where(Language.isocode == item.language)
                )
            ).scalar_one_or_none()
            if not lang_row:
                raise HTTPException(status_code=400, detail='Language not found')

            word_obj.text = item.text
            word_obj.language_id = lang_row.id
            word_obj.note = item.note
            if item.is_problematic is not None:
                word_obj.is_problematic = item.is_problematic

            # Update tags
            if item.tags is not None:
                Tag = models['Tag']
                tags_rows = (
                    (
                        await session.execute(
                            select(Tag).where(
                                Tag.name.in_(item.tags), Tag.author_id == user_id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                existing_names = {t.name for t in tags_rows}
                new_tags = []
                for name in item.tags:
                    if name not in existing_names:
                        t = Tag(name=name, author_id=user_id)
                        session.add(t)
                        new_tags.append(t)
                        tags_rows.append(t)
                        existing_names.add(name)
                # Flush new tags to ensure they're persisted with author_id before assigning to word
                if new_tags:
                    await session.flush()
                word_obj.tags = tags_rows

            # Update types
            if item.types is not None:
                WordType = models['WordType']
                types_rows = (
                    (
                        await session.execute(
                            select(WordType).where(WordType.slug.in_(item.types))
                        )
                    )
                    .scalars()
                    .all()
                )
                word_obj.types = types_rows

            # Handle translations, definitions, examples, images with update logic
            # (same logic as in word_update_service but without commit)
            WordTranslation = models['WordTranslation']
            WordTranslations = models['WordTranslations']

            if item.translations is not None:
                existing_tr_join = (
                    (
                        await session.execute(
                            select(WordTranslations.translation_id).where(
                                WordTranslations.word_id == word_obj.id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                payload_tr_ids = {tr.id for tr in item.translations if tr.id}
                tr_ids_to_delete = set(existing_tr_join) - payload_tr_ids

                if tr_ids_to_delete:
                    await session.execute(
                        delete(WordTranslations).where(
                            WordTranslations.word_id == word_obj.id,
                            WordTranslations.translation_id.in_(tr_ids_to_delete),
                        )
                    )
                    await session.execute(
                        delete(WordTranslation).where(
                            WordTranslation.id.in_(tr_ids_to_delete),
                            WordTranslation.author_id == user_id,
                        )
                    )

                for tr in item.translations or []:
                    lang_id = (
                        await _resolve_language_id(session, Language, tr.language)
                        if tr.language
                        else word_obj.language_id
                    )
                    if tr.id and tr.id in existing_tr_join:
                        existing_tr = (
                            await session.execute(
                                select(WordTranslation).where(
                                    WordTranslation.id == tr.id,
                                    WordTranslation.author_id == user_id,
                                )
                            )
                        ).scalar_one_or_none()
                        if existing_tr:
                            existing_tr.text = tr.text
                            existing_tr.language_id = lang_id
                    else:
                        # Check if translation with same text, author_id, language_id already exists
                        existing_tr = (
                            await session.execute(
                                select(WordTranslation).where(
                                    func.lower(WordTranslation.text)
                                    == func.lower(tr.text),
                                    WordTranslation.author_id == user_id,
                                    WordTranslation.language_id == lang_id,
                                )
                            )
                        ).scalar_one_or_none()

                        if existing_tr:
                            # Reuse existing translation
                            t = existing_tr
                        else:
                            # Create new translation
                            t = WordTranslation(
                                text=tr.text, language_id=lang_id, author_id=user_id
                            )
                            session.add(t)
                            await session.flush()

                        existing_join = (
                            await session.execute(
                                select(WordTranslations).where(
                                    WordTranslations.word_id == word_obj.id,
                                    WordTranslations.translation_id == t.id,
                                )
                            )
                        ).scalar_one_or_none()
                        if not existing_join:
                            session.add(
                                WordTranslations(
                                    word_id=word_obj.id, translation_id=t.id
                                )
                            )

            # Handle definitions
            if item.definitions is not None:
                WordDefinitions = models['WordDefinitions']
                Definition = models['Definition']

                existing_def_join = (
                    (
                        await session.execute(
                            select(WordDefinitions.definition_id).where(
                                WordDefinitions.word_id == word_obj.id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                payload_def_ids = {d.id for d in item.definitions if d.id}
                def_ids_to_delete = set(existing_def_join) - payload_def_ids

                if def_ids_to_delete:
                    await session.execute(
                        delete(WordDefinitions).where(
                            WordDefinitions.word_id == word_obj.id,
                            WordDefinitions.definition_id.in_(def_ids_to_delete),
                        )
                    )
                    await session.execute(
                        delete(Definition).where(
                            Definition.id.in_(def_ids_to_delete),
                            Definition.author_id == user_id,
                        )
                    )

                for d in item.definitions or []:
                    lang_id = (
                        await _resolve_language_id(session, Language, d.language)
                        if d.language
                        else word_obj.language_id
                    )
                    if d.id and d.id in existing_def_join:
                        existing_def = (
                            await session.execute(
                                select(Definition).where(
                                    Definition.id == d.id,
                                    Definition.author_id == user_id,
                                )
                            )
                        ).scalar_one_or_none()
                        if existing_def:
                            existing_def.text = d.text
                            existing_def.translation = d.translation
                            existing_def.language_id = lang_id
                    else:
                        # Check if definition with same text, author_id already exists
                        existing_def = (
                            await session.execute(
                                select(Definition).where(
                                    func.lower(Definition.text) == func.lower(d.text),
                                    Definition.author_id == user_id,
                                )
                            )
                        ).scalar_one_or_none()

                        if existing_def:
                            # Reuse existing definition
                            definition = existing_def
                        else:
                            # Create new definition
                            definition = Definition(
                                text=d.text,
                                translation=d.translation,
                                language_id=lang_id,
                                author_id=user_id,
                            )
                            session.add(definition)
                            await session.flush()

                        existing_join = (
                            await session.execute(
                                select(WordDefinitions).where(
                                    WordDefinitions.word_id == word_obj.id,
                                    WordDefinitions.definition_id == definition.id,
                                )
                            )
                        ).scalar_one_or_none()
                        if not existing_join:
                            session.add(
                                WordDefinitions(
                                    word_id=word_obj.id, definition_id=definition.id
                                )
                            )

            # Handle examples
            if item.examples is not None:
                WordUsageExamples = models['WordUsageExamples']
                UsageExample = models['UsageExample']

                existing_ex_join = (
                    (
                        await session.execute(
                            select(WordUsageExamples.example_id).where(
                                WordUsageExamples.word_id == word_obj.id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                payload_ex_ids = {ex.id for ex in item.examples if ex.id}
                ex_ids_to_delete = set(existing_ex_join) - payload_ex_ids

                if ex_ids_to_delete:
                    await session.execute(
                        delete(WordUsageExamples).where(
                            WordUsageExamples.word_id == word_obj.id,
                            WordUsageExamples.example_id.in_(ex_ids_to_delete),
                        )
                    )
                    await session.execute(
                        delete(UsageExample).where(
                            UsageExample.id.in_(ex_ids_to_delete),
                            UsageExample.author_id == user_id,
                        )
                    )

                for ex in item.examples or []:
                    lang_id = (
                        await _resolve_language_id(session, Language, ex.language)
                        if ex.language
                        else word_obj.language_id
                    )
                    if ex.id and ex.id in existing_ex_join:
                        existing_ex = (
                            await session.execute(
                                select(UsageExample).where(
                                    UsageExample.id == ex.id,
                                    UsageExample.author_id == user_id,
                                )
                            )
                        ).scalar_one_or_none()
                        if existing_ex:
                            existing_ex.text = ex.text
                            existing_ex.translation = ex.translation
                            existing_ex.language_id = lang_id
                            existing_ex.source = ex.source or 'OTH'
                            existing_ex.source_name = ex.source_name
                            existing_ex.source_url = ex.source_url
                    else:
                        # Check if example with same text, author_id already exists
                        existing_ex = (
                            await session.execute(
                                select(UsageExample).where(
                                    func.lower(UsageExample.text)
                                    == func.lower(ex.text),
                                    UsageExample.author_id == user_id,
                                )
                            )
                        ).scalar_one_or_none()

                        if existing_ex:
                            # Reuse existing example
                            example = existing_ex
                        else:
                            # Create new example
                            example = UsageExample(
                                text=ex.text,
                                translation=ex.translation,
                                language_id=lang_id,
                                author_id=user_id,
                                source=ex.source or 'OTH',
                                source_name=ex.source_name,
                                source_url=ex.source_url,
                            )
                            session.add(example)
                            await session.flush()

                        existing_join = (
                            await session.execute(
                                select(WordUsageExamples).where(
                                    WordUsageExamples.word_id == word_obj.id,
                                    WordUsageExamples.example_id == example.id,
                                )
                            )
                        ).scalar_one_or_none()
                        if not existing_join:
                            session.add(
                                WordUsageExamples(
                                    word_id=word_obj.id, example_id=example.id
                                )
                            )

            # Handle images
            if item.images is not None:
                WordImageAssociations = models['WordImageAssociations']
                ImageAssociation = models['ImageAssociation']

                existing_img_join = (
                    (
                        await session.execute(
                            select(WordImageAssociations.image_id).where(
                                WordImageAssociations.word_id == word_obj.id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                payload_img_ids = {img.id for img in item.images if img.id}
                img_ids_to_delete = set(existing_img_join) - payload_img_ids

                if img_ids_to_delete:
                    await session.execute(
                        delete(WordImageAssociations).where(
                            WordImageAssociations.word_id == word_obj.id,
                            WordImageAssociations.image_id.in_(img_ids_to_delete),
                        )
                    )
                    await session.execute(
                        delete(ImageAssociation).where(
                            ImageAssociation.id.in_(img_ids_to_delete),
                            ImageAssociation.author_id == user_id,
                        )
                    )

                for img in item.images or []:
                    if img.id and img.id in existing_img_join:
                        existing_img = (
                            await session.execute(
                                select(ImageAssociation).where(
                                    ImageAssociation.id == img.id,
                                    ImageAssociation.author_id == user_id,
                                )
                            )
                        ).scalar_one_or_none()
                        if existing_img:
                            existing_img.image_url = img.image_url
                            existing_img.width = img.width
                            existing_img.height = img.height
                            existing_img.num = img.num
                    else:
                        image = ImageAssociation(
                            image_url=img.image_url,
                            width=img.width,
                            height=img.height,
                            num=img.num,
                            author_id=user_id,
                        )
                        session.add(image)
                        await session.flush()
                        existing_join = (
                            await session.execute(
                                select(WordImageAssociations).where(
                                    WordImageAssociations.word_id == word_obj.id,
                                    WordImageAssociations.image_id == image.id,
                                )
                            )
                        ).scalar_one_or_none()
                        if not existing_join:
                            session.add(
                                WordImageAssociations(
                                    word_id=word_obj.id, image_id=image.id
                                )
                            )

            updated_words.append(word_obj)
            word = word_obj
        else:
            # Create new word
            word = await _create_word_with_nested(
                session,
                user_id=user_id,
                payload=item,
                models=models,
                default_language=item.language,
            )
            created_words.append(word)

        # Handle synonyms, antonyms, similars for both created and updated words
        if item.synonyms:
            target_ids = (
                (
                    await session.execute(
                        select(Word.id).where(
                            Word.slug.in_(item.synonyms), Word.author_id == user_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            await _add_bidirectional_relations(session, word.id, target_ids, Synonym)
        if item.antonyms:
            target_ids = (
                (
                    await session.execute(
                        select(Word.id).where(
                            Word.slug.in_(item.antonyms), Word.author_id == user_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            await _add_bidirectional_relations(session, word.id, target_ids, Antonym)
        if item.similars:
            target_ids = (
                (
                    await session.execute(
                        select(Word.id).where(
                            Word.slug.in_(item.similars), Word.author_id == user_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            await _add_bidirectional_relations(session, word.id, target_ids, Similar)

    # attach to collections if provided
    collections = []
    all_words = created_words + updated_words
    if payload.collections:
        collections = (
            (
                await session.execute(
                    select(Collection).where(
                        Collection.id.in_(payload.collections),
                        # Collection.author_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        missing = set(payload.collections) - {str(c.id) for c in collections}
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Collections not found: {', '.join(sorted(missing))}",
            )

        for coll in collections:
            for w in all_words:
                # Check if word is already in collection to avoid duplicates
                existing = (
                    await session.execute(
                        select(WordsInCollections).where(
                            WordsInCollections.word_id == w.id,
                            WordsInCollections.collection_id == coll.id,
                        )
                    )
                ).scalar_one_or_none()
                if not existing:
                    session.add(WordsInCollections(word_id=w.id, collection_id=coll.id))

    await session.commit()
    for w in all_words:
        await session.refresh(w)
        w._favorite = False

    # Send subscription updates for both created and updated words
    if created_words:
        celery_app.send_task(
            UPDATE_AUTHOR_SUBSCRIPTION_INFO,
            args=[
                str(user_id),
                {'new_words': [str(w.id) for w in created_words]},
                None,
            ],
        )
    if updated_words:
        celery_app.send_task(
            UPDATE_AUTHOR_SUBSCRIPTION_INFO,
            args=[
                str(user_id),
                {'updated_words': [str(w.id) for w in updated_words]},
                None,
            ],
        )

    # reuse list service for response
    params = params or WordsListParams()
    page_out = await words_list_service(
        session=session,
        user_id=user_id,
        params=params,
    )
    return MultipleWordsCreateOut(
        page=page_out.page,
        limit=page_out.limit,
        count=page_out.count,
        results=page_out.results,
        words_created_count=len(created_words),
        words_created=[w.id for w in created_words],
        collections_count=len(collections),
    )


async def word_retrieve_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    lang: str | None = None,
    models: dict = VOCAB_MODELS,
) -> WordReadOut:
    Word = models['Word']
    FavoriteWord = models['FavoriteWord']
    WordTranslation = models['WordTranslation']
    WordTranslations = models['WordTranslations']
    Definition = models['Definition']
    WordDefinitions = models['WordDefinitions']
    UsageExample = models['UsageExample']
    WordUsageExamples = models['WordUsageExamples']
    ImageAssociation = models['ImageAssociation']
    WordImageAssociations = models['WordImageAssociations']

    stmt = (
        select(Word)
        .where(Word.id == word_id, Word.author_id == user_id)
        .options(
            selectinload(Word.tags),
            selectinload(Word.types),
            selectinload(Word.language),
            selectinload(Word.author),
            selectinload(Word.source_word).selectinload(Word.author),
        )
    )
    word = (await session.execute(stmt)).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')

    translations = (
        (
            await session.execute(
                select(WordTranslation)
                .join(
                    WordTranslations,
                    WordTranslations.translation_id == WordTranslation.id,
                )
                .where(WordTranslations.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )
    definitions = (
        (
            await session.execute(
                select(Definition)
                .join(WordDefinitions, WordDefinitions.definition_id == Definition.id)
                .where(WordDefinitions.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )
    examples = (
        (
            await session.execute(
                select(UsageExample)
                .join(
                    WordUsageExamples, WordUsageExamples.example_id == UsageExample.id
                )
                .where(WordUsageExamples.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )
    images = (
        (
            await session.execute(
                select(ImageAssociation)
                .join(
                    WordImageAssociations,
                    WordImageAssociations.image_id == ImageAssociation.id,
                )
                .where(WordImageAssociations.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )

    # Enrich translations with per-translation word counts and last related words
    if translations:
        translation_ids = [t.id for t in translations]

        counts = (
            await session.execute(
                select(WordTranslations.translation_id, func.count())
                .join(Word, Word.id == WordTranslations.word_id)
                .where(
                    WordTranslations.translation_id.in_(translation_ids),
                    Word.author_id == user_id,
                )
                .group_by(WordTranslations.translation_id)
            )
        ).all()
        counts_map: dict[UUID, int] = {t_id: count for t_id, count in counts}

        assoc_rows = (
            await session.execute(
                select(
                    WordTranslations.translation_id,
                    Word.text,
                    WordTranslations.created,
                )
                .join(Word, Word.id == WordTranslations.word_id)
                .where(
                    WordTranslations.translation_id.in_(translation_ids),
                    Word.author_id == user_id,
                )
                .order_by(WordTranslations.created.desc())
            )
        ).all()
        last_words_map: dict[UUID, list[str]] = {t_id: [] for t_id in translation_ids}
        for t_id, word_text, _created in assoc_rows:
            if len(last_words_map[t_id]) >= 6:
                continue
            last_words_map[t_id].append(word_text)

        for t in translations:
            words_count = counts_map.get(t.id, 0)
            last_words = last_words_map.get(t.id, [])
            setattr(t, 'words_count', words_count)
            setattr(t, 'last_6_words', last_words)
            setattr(t, 'other_words_count', max(words_count - len(last_words), 0))

    word.translations = translations
    word.definitions = definitions
    word.examples = examples
    word.image_associations = images
    word.background_image_url = images[0].image_url if images else None

    fav = (
        await session.execute(
            select(func.count())
            .select_from(FavoriteWord)
            .where(FavoriteWord.user_id == user_id, FavoriteWord.word_id == word.id)
        )
    ).scalar_one()
    word._favorite = fav > 0

    # Comments count and initial comments (up to 3)
    WordComment = models['WordComment']
    comments_count = (
        await session.execute(
            select(func.count())
            .select_from(WordComment)
            .where(WordComment.word_id == word.id)
        )
    ).scalar_one()

    comments = []
    if comments_count > 0:
        comments_stmt = (
            select(WordComment)
            .where(WordComment.word_id == word.id)
            .order_by(WordComment.created.desc())
            .limit(3)
            .options(
                selectinload(WordComment.likes),
                selectinload(WordComment.dislikes),
                selectinload(WordComment.answers),
                selectinload(WordComment.author),
                selectinload(WordComment.word),
            )
        )
        comments_rows = (await session.execute(comments_stmt)).scalars().all()
        from api.v1.published.services import _map_word_comment

        comments = [_map_word_comment(c, user_id) for c in comments_rows]

    # Load synonyms, antonyms, similars
    Synonym = models['Synonym']
    Antonym = models['Antonym']
    Similar = models['Similar']
    synonyms = await _get_related_words(session, user_id, word.id, Synonym, models)
    antonyms = await _get_related_words(session, user_id, word.id, Antonym, models)
    similars = await _get_related_words(session, user_id, word.id, Similar, models)

    # Load collections (same as published word profile)
    Collection = models['Collection']
    WordsInCollections = models['WordsInCollections']
    Language = models['Language']
    Word = models['Word']
    WordImageAssociations = models['WordImageAssociations']

    collections_rows = (
        (
            await session.execute(
                select(Collection)
                .join(
                    WordsInCollections,
                    WordsInCollections.collection_id == Collection.id,
                )
                .where(WordsInCollections.word_id == word.id)
                .options(selectinload(Collection.author))
            )
        )
        .scalars()
        .all()
    )

    # Collection word counts
    counts = {}
    if collections_rows:
        counts = dict(
            (
                await session.execute(
                    select(WordsInCollections.collection_id, func.count())
                    .where(
                        WordsInCollections.collection_id.in_(
                            [c.id for c in collections_rows]
                        )
                    )
                    .group_by(WordsInCollections.collection_id)
                )
            ).all()
        )

    # Collection languages
    languages_map = {}
    if collections_rows:
        langs_result = await session.execute(
            select(
                WordsInCollections.collection_id,
                func.array_agg(func.distinct(Language.isocode)),
            )
            .join(Word, WordsInCollections.word_id == Word.id)
            .join(Language, Word.language_id == Language.id)
            .where(
                WordsInCollections.collection_id.in_([c.id for c in collections_rows])
            )
            .group_by(WordsInCollections.collection_id)
        )
        for coll_id, langs in langs_result.all():
            languages_map[coll_id] = [lang for lang in langs if lang]

    # Collection last 4 words
    last_words_map = {}
    if collections_rows:
        from core.utils.urls import get_full_media_url

        for coll_id in [c.id for c in collections_rows]:
            words_stmt = (
                select(Word)
                .join(WordsInCollections, WordsInCollections.word_id == Word.id)
                .where(WordsInCollections.collection_id == coll_id)
                .options(
                    selectinload(Word.wordimageassociations).selectinload(
                        WordImageAssociations.image
                    )
                )
                .order_by(WordsInCollections.created.desc())
                .limit(4)
            )
            words_result = (await session.execute(words_stmt)).scalars().all()
            last_words = []
            for w in words_result:
                word_image_assocs = getattr(w, 'wordimageassociations', []) or []
                image_url = None
                if word_image_assocs:
                    first_assoc = word_image_assocs[0]
                    if hasattr(first_assoc, 'image') and first_assoc.image:
                        image_url = getattr(first_assoc.image, 'image_url', None)
                        if image_url:
                            image_url = get_full_media_url(image_url)
                last_words.append(
                    {
                        'slug': w.slug,
                        'text': w.text,
                        'image': image_url,
                    }
                )
            last_words_map[coll_id] = last_words

    collections = []
    for c in collections_rows:
        c._favorite = False
        c._words_count = counts.get(c.id, 0)
        c._words_languages = languages_map.get(c.id, [])
        c._last_4_words = last_words_map.get(c.id, [])
        collections.append(map_collection(c, for_published=True))

    word_result = map_word_read(word, lang=lang)
    # Override comments and comments_count
    word_result.comments_count = comments_count
    word_result.comments = comments
    # Populate synonyms, antonyms, similars, and collections
    word_result.synonyms_count = len(synonyms)
    word_result.synonyms = [
        {'id': str(s.id), 'slug': s.slug, 'text': s.text} for s in synonyms
    ]
    word_result.antonyms_count = len(antonyms)
    word_result.antonyms = [
        {'id': str(a.id), 'slug': a.slug, 'text': a.text} for a in antonyms
    ]
    word_result.similars_count = len(similars)
    word_result.similars = [
        {'id': str(s.id), 'slug': s.slug, 'text': s.text} for s in similars
    ]
    word_result.collections_count = len(collections)
    word_result.collections = collections
    return word_result


async def synonym_retrieve_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    synonym_id: UUID,
    models: dict = VOCAB_MODELS,
):
    Synonym = models['Synonym']
    Word = models['Word']
    WordTranslation = models['WordTranslation']
    WordTranslations = models['WordTranslations']
    Definition = models['Definition']
    WordDefinitions = models['WordDefinitions']
    UsageExample = models['UsageExample']
    WordUsageExamples = models['WordUsageExamples']
    ImageAssociation = models['ImageAssociation']
    WordImageAssociations = models['WordImageAssociations']
    FavoriteWord = models['FavoriteWord']

    synonym = (
        await session.execute(
            select(Synonym)
            .where(
                Synonym.id == synonym_id,
                or_(
                    Synonym.from_word.has(Word.author_id == user_id),
                    Synonym.to_word.has(Word.author_id == user_id),
                ),
            )
            .options(
                selectinload(Synonym.from_word).selectinload(Word.tags),
                selectinload(Synonym.from_word).selectinload(Word.types),
                selectinload(Synonym.from_word).selectinload(Word.language),
                selectinload(Synonym.from_word)
                .selectinload(Word.source_word)
                .selectinload(Word.author),
                selectinload(Synonym.to_word).selectinload(Word.tags),
                selectinload(Synonym.to_word).selectinload(Word.types),
                selectinload(Synonym.to_word).selectinload(Word.language),
                selectinload(Synonym.to_word)
                .selectinload(Word.source_word)
                .selectinload(Word.author),
            )
        )
    ).scalar_one_or_none()
    if not synonym:
        raise HTTPException(status_code=404, detail='Synonym not found')

    async def _enrich_word(word: Word):
        translations = (
            (
                await session.execute(
                    select(WordTranslation)
                    .join(
                        WordTranslations,
                        WordTranslations.translation_id == WordTranslation.id,
                    )
                    .where(WordTranslations.word_id == word.id)
                )
            )
            .scalars()
            .all()
        )
        definitions = (
            (
                await session.execute(
                    select(Definition)
                    .join(
                        WordDefinitions, WordDefinitions.definition_id == Definition.id
                    )
                    .where(WordDefinitions.word_id == word.id)
                )
            )
            .scalars()
            .all()
        )
        examples = (
            (
                await session.execute(
                    select(UsageExample)
                    .join(
                        WordUsageExamples,
                        WordUsageExamples.example_id == UsageExample.id,
                    )
                    .where(WordUsageExamples.word_id == word.id)
                )
            )
            .scalars()
            .all()
        )
        images = (
            (
                await session.execute(
                    select(ImageAssociation)
                    .join(
                        WordImageAssociations,
                        WordImageAssociations.image_id == ImageAssociation.id,
                    )
                    .where(WordImageAssociations.word_id == word.id)
                )
            )
            .scalars()
            .all()
        )
        word.translations = translations
        word.definitions = definitions
        word.examples = examples
        word.image_associations = images
        fav = (
            await session.execute(
                select(func.count())
                .select_from(FavoriteWord)
                .where(FavoriteWord.user_id == user_id, FavoriteWord.word_id == word.id)
            )
        ).scalar_one()
        word._favorite = fav > 0

    await _enrich_word(synonym.from_word)
    await _enrich_word(synonym.to_word)

    # NOTE: DRF groups other synonyms by translation; here we provide flat structure placeholders
    other_synonyms: dict[str, dict] = {}

    return SynonymReadOut(
        id=synonym.id,
        to_word=map_word_read(synonym.to_word),
        from_word=map_word_read(synonym.from_word),
        other_synonyms=other_synonyms,
        note=synonym.note,
        created=getattr(synonym, 'created', None),
        modified=getattr(synonym, 'modified', None),
    )


async def word_add_to_collections_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    payload: WordCollectionsIn,
    lang: str | None = None,
    models: dict = VOCAB_MODELS,
) -> WordReadOut:
    Collection = models['Collection']
    WordsInCollections = models['WordsInCollections']

    word = await _get_word_by_id(session, user_id, word_id, models)
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')

    if not payload.collections:
        raise HTTPException(status_code=400, detail='No collections provided')

    collections = (
        (
            await session.execute(
                select(Collection).where(
                    Collection.id.in_(payload.collections),
                    Collection.author_id == user_id,
                )
            )
        )
        .scalars()
        .all()
    )
    found_ids = {c.id for c in collections}
    missing = set(payload.collections) - found_ids
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Collections not found: {', '.join(str(m) for m in missing)}",
        )

    existing_pairs = (
        (
            await session.execute(
                select(WordsInCollections.collection_id).where(
                    WordsInCollections.word_id == word.id,
                    WordsInCollections.collection_id.in_(payload.collections),
                )
            )
        )
        .scalars()
        .all()
    )
    existing = set(existing_pairs)
    for coll in collections:
        if coll.id in existing:
            continue
        session.add(WordsInCollections(word_id=word.id, collection_id=coll.id))

    await session.commit()
    return await word_retrieve_service(
        session=session, user_id=user_id, word_id=word_id, lang=lang, models=models
    )


async def words_data_to_update_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    payload: WordsIdsIn,
    lang: str | None = None,
    models: dict = VOCAB_MODELS,
) -> list[WordReadOut]:
    if not payload.words:
        return []
    results: list[WordReadOut] = []
    for wid in payload.words:
        results.append(
            await word_retrieve_service(
                session=session, user_id=user_id, word_id=wid, lang=lang, models=models
            )
        )
    return results


async def words_set_access_level_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    updates: Sequence[WordAccessLevelUpdateIn],
    models: dict = VOCAB_MODELS,
) -> int:
    valid_levels = {lvl for lvl, _ in AccessLevelsEnum.access_levels}
    updated = 0
    for item in updates:
        word = await _get_word_by_id(session, user_id, item.id, models)
        if not word:
            continue

        # Ignores words with restricted mark.
        # If allow_access_change is False, ignore attempts to set access levels to PUBLIC
        if not word.allow_access_change:
            if item.read_access_level == AccessLevelsEnum.PUBLIC:
                # Skip setting read_access_level to PUBLIC
                pass
            elif item.read_access_level:
                # Allow other access levels
                if item.read_access_level not in valid_levels:
                    raise HTTPException(
                        status_code=400,
                        detail=f'Invalid read_access_level: {item.read_access_level}',
                    )
                word.read_access_level = item.read_access_level

            if item.add_access_level == AccessLevelsEnum.PUBLIC:
                # Skip setting add_access_level to PUBLIC
                pass
            elif item.add_access_level:
                # Allow other access levels
                if item.add_access_level not in valid_levels:
                    raise HTTPException(
                        status_code=400,
                        detail=f'Invalid add_access_level: {item.add_access_level}',
                    )
                word.add_access_level = item.add_access_level
        else:
            # allow_access_change is True, allow all updates
            if item.read_access_level:
                if item.read_access_level not in valid_levels:
                    raise HTTPException(
                        status_code=400,
                        detail=f'Invalid read_access_level: {item.read_access_level}',
                    )
                word.read_access_level = item.read_access_level
            if item.add_access_level:
                if item.add_access_level not in valid_levels:
                    raise HTTPException(
                        status_code=400,
                        detail=f'Invalid add_access_level: {item.add_access_level}',
                    )
                word.add_access_level = item.add_access_level

        if item.allow_access_change is not None:
            word.allow_access_change = item.allow_access_change
        updated += 1

    await session.commit()
    return updated


async def word_allow_comments_switch_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    lang: str | None = None,
    models: dict = VOCAB_MODELS,
) -> WordReadOut:
    word = await _get_word_by_id(session, user_id, word_id, models)
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')

    settings = (
        await session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not settings or not settings.words_allow_comments:
        raise HTTPException(status_code=409, detail='Comments not allowed by settings')

    word.allow_comments = not word.allow_comments
    await session.commit()
    await session.refresh(word)

    # reuse retrieve to include all related data and flags
    return await word_retrieve_service(
        session=session, user_id=user_id, word_id=word_id, lang=lang, models=models
    )


async def words_random_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    limit: int = 1,
    models: dict = VOCAB_MODELS,
) -> PageOut:
    Word = models['Word']

    limit = max(1, min(limit, 100))

    base_q = (
        select(Word)
        .where(Word.author_id == user_id)
        .options(
            selectinload(Word.tags),
            selectinload(Word.types),
            selectinload(Word.language),
            selectinload(Word.source_word).selectinload(Word.author),
        )
        .order_by(func.random())
        .limit(limit)
    )
    words = (await session.execute(base_q)).scalars().all()

    # fetch counts separately to preserve PageOut shape
    total = (
        await session.execute(
            select(func.count()).select_from(
                select(Word.id).where(Word.author_id == user_id).subquery()
            )
        )
    ).scalar_one()

    results = [map_word_read(w) for w in words]
    return PageOut(page=1, limit=limit, count=total, results=results)


async def word_update_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    payload: WordInPartial,
    lang: str | None = None,
    models: dict = VOCAB_MODELS,
) -> WordReadOut:
    Word = models['Word']
    Tag = models['Tag']
    WordType = models['WordType']
    Language = models['Language']
    WordTranslation = models['WordTranslation']
    WordTranslations = models['WordTranslations']

    word = (
        await session.execute(
            select(Word)
            .where(Word.id == word_id, Word.author_id == user_id)
            .options(
                selectinload(Word.tags),
                selectinload(Word.types),
                selectinload(Word.source_word).selectinload(Word.author),
            )
        )
    ).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')

    # Update language if provided, otherwise keep existing
    if payload.language is not None:
        lang_row = (
            await session.execute(
                select(Language).where(Language.isocode == payload.language)
            )
        ).scalar_one_or_none()
        if not lang_row:
            raise HTTPException(status_code=400, detail='Language not found')
        word.language_id = lang_row.id

    # Update text if provided
    if payload.text is not None:
        word.text = payload.text

    # Note can be explicitly set to None, so assign directly only when present in payload
    if 'note' in payload.model_fields_set:
        word.note = payload.note
    if payload.is_problematic is not None:
        word.is_problematic = payload.is_problematic

    if payload.tags is not None:
        tags_rows = (
            (
                await session.execute(
                    select(Tag).where(
                        Tag.name.in_(payload.tags), Tag.author_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        existing_names = {t.name for t in tags_rows}
        new_tags = []
        for name in payload.tags:
            if name not in existing_names:
                t = Tag(name=name, author_id=user_id)
                session.add(t)
                new_tags.append(t)
                tags_rows.append(t)
                existing_names.add(name)
        # Flush new tags to ensure they're persisted with author_id before assigning to word
        if new_tags:
            await session.flush()
        word.tags = tags_rows

    if payload.types is not None:
        types_rows = (
            (
                await session.execute(
                    select(WordType).where(WordType.slug.in_(payload.types))
                )
            )
            .scalars()
            .all()
        )
        word.types = types_rows

    # Handle translations: update existing or create new
    if payload.translations is not None:
        # Get existing translations for this word
        existing_tr_join = (
            (
                await session.execute(
                    select(WordTranslations.translation_id).where(
                        WordTranslations.word_id == word.id
                    )
                )
            )
            .scalars()
            .all()
        )

        payload_tr_ids = {tr.id for tr in payload.translations if tr.id}
        tr_ids_to_delete = set(existing_tr_join) - payload_tr_ids

        # Delete translations not in payload
        if tr_ids_to_delete:
            await session.execute(
                delete(WordTranslations).where(
                    WordTranslations.word_id == word.id,
                    WordTranslations.translation_id.in_(tr_ids_to_delete),
                )
            )
            await session.execute(
                delete(WordTranslation).where(
                    WordTranslation.id.in_(tr_ids_to_delete),
                    WordTranslation.author_id == user_id,
                )
            )

        # Update or create translations
        for tr in payload.translations or []:
            lang_id = (
                await _resolve_language_id(session, Language, tr.language)
                if tr.language
                else word.language_id
            )
            if tr.id and tr.id in existing_tr_join:
                # Check if translation exists and if user is the author
                existing_tr = (
                    await session.execute(
                        select(WordTranslation).where(
                            WordTranslation.id == tr.id,
                        )
                    )
                ).scalar_one_or_none()

                if existing_tr:
                    is_author = existing_tr.author_id == user_id

                    if is_author:
                        # User is the author - update existing translation
                        existing_tr.text = tr.text
                        existing_tr.language_id = (
                            lang_id if lang_id is not None else existing_tr.language_id
                        )
                    else:
                        # User is not the author - create a copy
                        # First, disconnect the word from the original translation
                        await session.execute(
                            delete(WordTranslations).where(
                                WordTranslations.word_id == word.id,
                                WordTranslations.translation_id == existing_tr.id,
                            )
                        )
                        # Create new translation copy with updated data
                        new_translation = WordTranslation(
                            text=tr.text,
                            language_id=lang_id
                            if lang_id is not None
                            else existing_tr.language_id,
                            author_id=user_id,
                        )
                        session.add(new_translation)
                        await session.flush()
                        # Associate word with the new translation
                        session.add(
                            WordTranslations(
                                word_id=word.id, translation_id=new_translation.id
                            )
                        )
            else:
                # Check if translation with same text, author_id, language_id already exists
                existing_tr = (
                    await session.execute(
                        select(WordTranslation).where(
                            func.lower(WordTranslation.text) == func.lower(tr.text),
                            WordTranslation.author_id == user_id,
                            WordTranslation.language_id == lang_id,
                        )
                    )
                ).scalar_one_or_none()

                if existing_tr:
                    # Reuse existing translation
                    t = existing_tr
                else:
                    # Create new translation
                    t = WordTranslation(
                        text=tr.text, language_id=lang_id, author_id=user_id
                    )
                    session.add(t)
                    await session.flush()

                # Check if join already exists
                existing_join = (
                    await session.execute(
                        select(WordTranslations).where(
                            WordTranslations.word_id == word.id,
                            WordTranslations.translation_id == t.id,
                        )
                    )
                ).scalar_one_or_none()
                if not existing_join:
                    session.add(WordTranslations(word_id=word.id, translation_id=t.id))

    # Handle definitions: update existing or create new
    if payload.definitions is not None:
        WordDefinitions = models['WordDefinitions']
        Definition = models['Definition']

        existing_def_join = (
            (
                await session.execute(
                    select(WordDefinitions.definition_id).where(
                        WordDefinitions.word_id == word.id
                    )
                )
            )
            .scalars()
            .all()
        )

        payload_def_ids = {d.id for d in payload.definitions if d.id}
        def_ids_to_delete = set(existing_def_join) - payload_def_ids

        # Delete definitions not in payload
        if def_ids_to_delete:
            await session.execute(
                delete(WordDefinitions).where(
                    WordDefinitions.word_id == word.id,
                    WordDefinitions.definition_id.in_(def_ids_to_delete),
                )
            )
            await session.execute(
                delete(Definition).where(
                    Definition.id.in_(def_ids_to_delete),
                    Definition.author_id == user_id,
                )
            )

        # Update or create definitions
        for d in payload.definitions or []:
            lang_id = (
                await _resolve_language_id(session, Language, d.language)
                if d.language
                else word.language_id
            )
            if d.id and d.id in existing_def_join:
                # Check if definition exists and if user is the author
                existing_def = (
                    await session.execute(
                        select(Definition).where(
                            Definition.id == d.id,
                        )
                    )
                ).scalar_one_or_none()

                if existing_def:
                    is_author = existing_def.author_id == user_id

                    if is_author:
                        # User is the author - update existing definition
                        existing_def.text = d.text
                        existing_def.translation = d.translation
                        existing_def.language_id = (
                            lang_id if lang_id is not None else existing_def.language_id
                        )
                    else:
                        # User is not the author - create a copy
                        # First, disconnect the word from the original definition
                        await session.execute(
                            delete(WordDefinitions).where(
                                WordDefinitions.word_id == word.id,
                                WordDefinitions.definition_id == existing_def.id,
                            )
                        )
                        # Create new definition copy with updated data
                        new_definition = Definition(
                            text=d.text,
                            translation=d.translation,
                            language_id=lang_id
                            if lang_id is not None
                            else existing_def.language_id,
                            author_id=user_id,
                        )
                        session.add(new_definition)
                        await session.flush()
                        # Associate word with the new definition
                        session.add(
                            WordDefinitions(
                                word_id=word.id, definition_id=new_definition.id
                            )
                        )
            else:
                # Check if definition with same text, author_id already exists
                existing_def = (
                    await session.execute(
                        select(Definition).where(
                            func.lower(Definition.text) == func.lower(d.text),
                            Definition.author_id == user_id,
                        )
                    )
                ).scalar_one_or_none()

                if existing_def:
                    # Reuse existing definition
                    definition = existing_def
                else:
                    # Create new definition
                    definition = Definition(
                        text=d.text,
                        translation=d.translation,
                        language_id=lang_id,
                        author_id=user_id,
                    )
                    session.add(definition)
                    await session.flush()

                existing_join = (
                    await session.execute(
                        select(WordDefinitions).where(
                            WordDefinitions.word_id == word.id,
                            WordDefinitions.definition_id == definition.id,
                        )
                    )
                ).scalar_one_or_none()
                if not existing_join:
                    session.add(
                        WordDefinitions(word_id=word.id, definition_id=definition.id)
                    )

    # Handle examples: update existing or create new
    if payload.examples is not None:
        WordUsageExamples = models['WordUsageExamples']
        UsageExample = models['UsageExample']

        existing_ex_join = (
            (
                await session.execute(
                    select(WordUsageExamples.example_id).where(
                        WordUsageExamples.word_id == word.id
                    )
                )
            )
            .scalars()
            .all()
        )

        payload_ex_ids = {ex.id for ex in payload.examples if ex.id}
        ex_ids_to_delete = set(existing_ex_join) - payload_ex_ids

        # Delete examples not in payload
        if ex_ids_to_delete:
            await session.execute(
                delete(WordUsageExamples).where(
                    WordUsageExamples.word_id == word.id,
                    WordUsageExamples.example_id.in_(ex_ids_to_delete),
                )
            )
            await session.execute(
                delete(UsageExample).where(
                    UsageExample.id.in_(ex_ids_to_delete),
                    UsageExample.author_id == user_id,
                )
            )

        # Update or create examples
        for ex in payload.examples or []:
            lang_id = (
                await _resolve_language_id(session, Language, ex.language)
                if ex.language
                else word.language_id
            )
            if ex.id and ex.id in existing_ex_join:
                # Check if example exists and if user is the author
                existing_ex = (
                    await session.execute(
                        select(UsageExample).where(
                            UsageExample.id == ex.id,
                        )
                    )
                ).scalar_one_or_none()

                if existing_ex:
                    is_author = existing_ex.author_id == user_id

                    if is_author:
                        # User is the author - update existing example
                        existing_ex.text = ex.text
                        existing_ex.translation = ex.translation
                        existing_ex.language_id = (
                            lang_id if lang_id is not None else existing_ex.language_id
                        )
                        existing_ex.source = ex.source or existing_ex.source or 'OTH'
                        existing_ex.source_name = ex.source_name
                        existing_ex.source_url = ex.source_url
                    else:
                        # User is not the author - create a copy
                        # First, disconnect the word from the original example
                        await session.execute(
                            delete(WordUsageExamples).where(
                                WordUsageExamples.word_id == word.id,
                                WordUsageExamples.example_id == existing_ex.id,
                            )
                        )
                        # Create new example copy with updated data
                        new_example = UsageExample(
                            text=ex.text,
                            translation=ex.translation,
                            source=ex.source or existing_ex.source or 'OTH',
                            source_name=ex.source_name,
                            source_url=ex.source_url,
                            language_id=lang_id
                            if lang_id is not None
                            else existing_ex.language_id,
                            author_id=user_id,
                        )
                        session.add(new_example)
                        await session.flush()
                        # Associate word with the new example
                        session.add(
                            WordUsageExamples(
                                word_id=word.id, example_id=new_example.id
                            )
                        )
            else:
                # Check if example with same text, author_id already exists
                existing_ex = (
                    await session.execute(
                        select(UsageExample).where(
                            func.lower(UsageExample.text) == func.lower(ex.text),
                            UsageExample.author_id == user_id,
                        )
                    )
                ).scalar_one_or_none()

                if existing_ex:
                    # Reuse existing example
                    example = existing_ex
                else:
                    # Create new example
                    example = UsageExample(
                        text=ex.text,
                        translation=ex.translation,
                        language_id=lang_id,
                        author_id=user_id,
                        source=ex.source or 'OTH',
                        source_name=ex.source_name,
                        source_url=ex.source_url,
                    )
                    session.add(example)
                    await session.flush()

                existing_join = (
                    await session.execute(
                        select(WordUsageExamples).where(
                            WordUsageExamples.word_id == word.id,
                            WordUsageExamples.example_id == example.id,
                        )
                    )
                ).scalar_one_or_none()
                if not existing_join:
                    session.add(
                        WordUsageExamples(word_id=word.id, example_id=example.id)
                    )

    # Handle images: update existing or create new
    if payload.images is not None:
        WordImageAssociations = models['WordImageAssociations']
        ImageAssociation = models['ImageAssociation']

        existing_img_join = (
            (
                await session.execute(
                    select(WordImageAssociations.image_id).where(
                        WordImageAssociations.word_id == word.id
                    )
                )
            )
            .scalars()
            .all()
        )

        payload_img_ids = {img.id for img in payload.images if img.id}
        img_ids_to_delete = set(existing_img_join) - payload_img_ids

        # Delete images not in payload
        if img_ids_to_delete:
            await session.execute(
                delete(WordImageAssociations).where(
                    WordImageAssociations.word_id == word.id,
                    WordImageAssociations.image_id.in_(img_ids_to_delete),
                )
            )
            await session.execute(
                delete(ImageAssociation).where(
                    ImageAssociation.id.in_(img_ids_to_delete),
                    ImageAssociation.author_id == user_id,
                )
            )

        # Update or create images
        for img in payload.images or []:
            if img.id and img.id in existing_img_join:
                # Check if image exists and if user is the author
                existing_img = (
                    await session.execute(
                        select(ImageAssociation).where(
                            ImageAssociation.id == img.id,
                        )
                    )
                ).scalar_one_or_none()

                if existing_img:
                    is_author = existing_img.author_id == user_id

                    if is_author:
                        # User is the author - update existing image
                        existing_img.image_url = img.image_url
                        existing_img.width = (
                            img.width if img.width is not None else existing_img.width
                        )
                        existing_img.height = (
                            img.height
                            if img.height is not None
                            else existing_img.height
                        )
                        existing_img.num = (
                            img.num if img.num is not None else existing_img.num
                        )
                    else:
                        # User is not the author - create a copy
                        # First, disconnect the word from the original image
                        await session.execute(
                            delete(WordImageAssociations).where(
                                WordImageAssociations.word_id == word.id,
                                WordImageAssociations.image_id == existing_img.id,
                            )
                        )
                        # Create new image copy with updated data
                        new_image = ImageAssociation(
                            image_url=img.image_url,
                            width=img.width
                            if img.width is not None
                            else existing_img.width,
                            height=img.height
                            if img.height is not None
                            else existing_img.height,
                            num=img.num if img.num is not None else existing_img.num,
                            author_id=user_id,
                        )
                        session.add(new_image)
                        await session.flush()
                        # Associate word with the new image
                        session.add(
                            WordImageAssociations(
                                word_id=word.id, image_id=new_image.id
                            )
                        )
            else:
                # Create new image
                image = ImageAssociation(
                    image_url=img.image_url,
                    width=img.width,
                    height=img.height,
                    num=img.num,
                    author_id=user_id,
                )
                session.add(image)
                await session.flush()
                existing_join = (
                    await session.execute(
                        select(WordImageAssociations).where(
                            WordImageAssociations.word_id == word.id,
                            WordImageAssociations.image_id == image.id,
                        )
                    )
                ).scalar_one_or_none()
                if not existing_join:
                    session.add(
                        WordImageAssociations(word_id=word.id, image_id=image.id)
                    )

    await session.commit()
    # Reload word with all relationships including source_word
    word = (
        await session.execute(
            select(Word)
            .where(Word.id == word.id)
            .options(
                selectinload(Word.tags),
                selectinload(Word.types),
                selectinload(Word.language),
                selectinload(Word.author),
                selectinload(Word.source_word).selectinload(Word.author),
            )
        )
    ).scalar_one()

    # Load translations, definitions, examples, and images like word_retrieve_service does
    WordTranslation = models['WordTranslation']
    WordTranslations = models['WordTranslations']
    Definition = models['Definition']
    WordDefinitions = models['WordDefinitions']
    UsageExample = models['UsageExample']
    WordUsageExamples = models['WordUsageExamples']
    ImageAssociation = models['ImageAssociation']
    WordImageAssociations = models['WordImageAssociations']
    FavoriteWord = models['FavoriteWord']

    translations = (
        (
            await session.execute(
                select(WordTranslation)
                .join(
                    WordTranslations,
                    WordTranslations.translation_id == WordTranslation.id,
                )
                .where(WordTranslations.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )
    definitions = (
        (
            await session.execute(
                select(Definition)
                .join(WordDefinitions, WordDefinitions.definition_id == Definition.id)
                .where(WordDefinitions.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )
    examples = (
        (
            await session.execute(
                select(UsageExample)
                .join(
                    WordUsageExamples, WordUsageExamples.example_id == UsageExample.id
                )
                .where(WordUsageExamples.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )
    images = (
        (
            await session.execute(
                select(ImageAssociation)
                .join(
                    WordImageAssociations,
                    WordImageAssociations.image_id == ImageAssociation.id,
                )
                .where(WordImageAssociations.word_id == word.id)
            )
        )
        .scalars()
        .all()
    )

    word.translations = translations
    word.definitions = definitions
    word.examples = examples
    word.image_associations = images
    word.background_image_url = images[0].image_url if images else None

    fav = (
        await session.execute(
            select(func.count())
            .select_from(FavoriteWord)
            .where(FavoriteWord.user_id == user_id, FavoriteWord.word_id == word.id)
        )
    ).scalar_one()
    word._favorite = fav > 0

    # Comments count and initial comments (up to 3)
    WordComment = models['WordComment']
    comments_count = (
        await session.execute(
            select(func.count())
            .select_from(WordComment)
            .where(WordComment.word_id == word.id)
        )
    ).scalar_one()

    comments = []
    if comments_count > 0:
        comments_stmt = (
            select(WordComment)
            .where(WordComment.word_id == word.id)
            .order_by(WordComment.created.desc())
            .limit(3)
            .options(
                selectinload(WordComment.likes),
                selectinload(WordComment.dislikes),
                selectinload(WordComment.answers),
                selectinload(WordComment.author),
                selectinload(WordComment.word),
            )
        )
        comments_rows = (await session.execute(comments_stmt)).scalars().all()
        from api.v1.published.services import _map_word_comment

        comments = [_map_word_comment(c, user_id) for c in comments_rows]

    # Load synonyms, antonyms, similars
    Synonym = models['Synonym']
    Antonym = models['Antonym']
    Similar = models['Similar']
    synonyms = await _get_related_words(session, user_id, word.id, Synonym, models)
    antonyms = await _get_related_words(session, user_id, word.id, Antonym, models)
    similars = await _get_related_words(session, user_id, word.id, Similar, models)

    # Load collections (same as published word profile)
    Collection = models['Collection']
    WordsInCollections = models['WordsInCollections']
    Language = models['Language']
    Word = models['Word']
    WordImageAssociations = models['WordImageAssociations']

    collections_rows = (
        (
            await session.execute(
                select(Collection)
                .join(
                    WordsInCollections,
                    WordsInCollections.collection_id == Collection.id,
                )
                .where(WordsInCollections.word_id == word.id)
                .options(selectinload(Collection.author))
            )
        )
        .scalars()
        .all()
    )

    # Collection word counts
    counts = {}
    if collections_rows:
        counts = dict(
            (
                await session.execute(
                    select(WordsInCollections.collection_id, func.count())
                    .where(
                        WordsInCollections.collection_id.in_(
                            [c.id for c in collections_rows]
                        )
                    )
                    .group_by(WordsInCollections.collection_id)
                )
            ).all()
        )

    # Collection languages
    languages_map = {}
    if collections_rows:
        langs_result = await session.execute(
            select(
                WordsInCollections.collection_id,
                func.array_agg(func.distinct(Language.isocode)),
            )
            .join(Word, WordsInCollections.word_id == Word.id)
            .join(Language, Word.language_id == Language.id)
            .where(
                WordsInCollections.collection_id.in_([c.id for c in collections_rows])
            )
            .group_by(WordsInCollections.collection_id)
        )
        for coll_id, langs in langs_result.all():
            languages_map[coll_id] = [lang for lang in langs if lang]

    # Collection last 4 words
    last_words_map = {}
    if collections_rows:
        from core.utils.urls import get_full_media_url

        for coll_id in [c.id for c in collections_rows]:
            words_stmt = (
                select(Word)
                .join(WordsInCollections, WordsInCollections.word_id == Word.id)
                .where(WordsInCollections.collection_id == coll_id)
                .options(
                    selectinload(Word.wordimageassociations).selectinload(
                        WordImageAssociations.image
                    )
                )
                .order_by(WordsInCollections.created.desc())
                .limit(4)
            )
            words_result = (await session.execute(words_stmt)).scalars().all()
            last_words = []
            for w in words_result:
                word_image_assocs = getattr(w, 'wordimageassociations', []) or []
                image_url = None
                if word_image_assocs:
                    first_assoc = word_image_assocs[0]
                    if hasattr(first_assoc, 'image') and first_assoc.image:
                        image_url = getattr(first_assoc.image, 'image_url', None)
                        if image_url:
                            image_url = get_full_media_url(image_url)
                last_words.append(
                    {
                        'slug': w.slug,
                        'text': w.text,
                        'image': image_url,
                    }
                )
            last_words_map[coll_id] = last_words

    collections = []
    for c in collections_rows:
        c._favorite = False
        c._words_count = counts.get(c.id, 0)
        c._words_languages = languages_map.get(c.id, [])
        c._last_4_words = last_words_map.get(c.id, [])
        collections.append(map_collection(c, for_published=True))

    word_result = map_word_read(word, lang=lang)
    # Override comments and comments_count
    word_result.comments_count = comments_count
    word_result.comments = comments
    # Populate synonyms, antonyms, similars, and collections
    word_result.synonyms_count = len(synonyms)
    word_result.synonyms = [
        {'id': str(s.id), 'slug': s.slug, 'text': s.text} for s in synonyms
    ]
    word_result.antonyms_count = len(antonyms)
    word_result.antonyms = [
        {'id': str(a.id), 'slug': a.slug, 'text': a.text} for a in antonyms
    ]
    word_result.similars_count = len(similars)
    word_result.similars = [
        {'id': str(s.id), 'slug': s.slug, 'text': s.text} for s in similars
    ]
    word_result.collections_count = len(collections)
    word_result.collections = collections
    return word_result


async def word_delete_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    models: dict = VOCAB_MODELS,
) -> None:
    Word = models['Word']
    WordTranslations = models['WordTranslations']
    WordDefinitions = models['WordDefinitions']
    WordUsageExamples = models['WordUsageExamples']
    WordImageAssociations = models['WordImageAssociations']
    WordsInCollections = models['WordsInCollections']

    word = (
        await session.execute(
            select(Word).where(Word.id == word_id, Word.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')

    # Manually delete all join-table rows to avoid NULLing FKs on flush
    await session.execute(
        delete(WordTranslations).where(WordTranslations.word_id == word.id)
    )
    await session.execute(
        delete(WordDefinitions).where(WordDefinitions.word_id == word.id)
    )
    await session.execute(
        delete(WordUsageExamples).where(WordUsageExamples.word_id == word.id)
    )
    await session.execute(
        delete(WordImageAssociations).where(WordImageAssociations.word_id == word.id)
    )
    await session.execute(
        delete(WordsInCollections).where(WordsInCollections.word_id == word.id)
    )
    # Delete M2M relationships for tags, types, and share_with
    await session.execute(
        delete(vocabulary_word_tags).where(vocabulary_word_tags.c.word_id == word.id)
    )
    await session.execute(
        delete(vocabulary_word_types).where(vocabulary_word_types.c.word_id == word.id)
    )
    await session.execute(
        delete(vocabulary_word_share_with).where(
            vocabulary_word_share_with.c.word_id == word.id
        )
    )

    await session.delete(word)
    await session.commit()
    celery_app.send_task(
        UPDATE_COLLECTION_SUBSCRIPTION_INFO,
        args=[None, {'removed_words': [str(word.id)]}, None],
        kwargs={'collections_pks': []},
    )
    celery_app.send_task(
        UPDATE_AUTHOR_SUBSCRIPTION_INFO,
        args=[str(user_id), {'removed_words': [str(word.id)]}, None],
    )
    celery_app.send_task(
        CLEAR_EMPTY_VOCAB_OBJECTS,
        args=[str(user_id), {}],
        kwargs={'all': True},
    )


async def word_favorite_toggle_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    models: dict = VOCAB_MODELS,
    author_only: bool = True,
) -> FavoriteToggleOut:
    Word = models['Word']
    FavoriteWord = models['FavoriteWord']

    word = (
        await session.execute(
            select(Word).where(Word.id == word_id, Word.author_id == user_id)
        )
        if author_only
        else await session.execute(select(Word).where(Word.id == word_id))
    ).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')

    existing = (
        await session.execute(
            select(FavoriteWord).where(
                FavoriteWord.user_id == user_id, FavoriteWord.word_id == word.id
            )
        )
    ).scalar_one_or_none()

    if existing:
        await session.delete(existing)
        word._favorite = False
    else:
        session.add(FavoriteWord(user_id=user_id, word_id=word.id))
        word._favorite = True

    await session.commit()
    await session.refresh(word)
    return FavoriteToggleOut(
        favorite=word._favorite,
    )


# ---------------- Tags & Types ----------------


async def tags_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    models: dict = VOCAB_MODELS,
) -> list[TagOut]:
    Tag = models['Tag']
    Word = models['Word']
    rows = (
        (
            await session.execute(
                select(Tag)
                .join(Word.tags)
                .where(Word.author_id == user_id)
                .group_by(Tag.id)
                .order_by(Tag.name)
            )
        )
        .scalars()
        .all()
    )
    return [TagOut.model_validate(row) for row in rows]


async def types_list_service(
    *,
    session: AsyncSession,
    lang: str,
    models: dict = VOCAB_MODELS,
) -> list[TypeOut]:
    WordType = models['WordType']
    rows = (
        (await session.execute(select(WordType).order_by(WordType.name_en)))
        .scalars()
        .all()
    )
    return [
        TypeOut(
            id=row.id,
            slug=getattr(row, 'slug', None),
            name=i18n_get(row, 'name', lang)
            or getattr(row, 'name_en', None)
            or getattr(row, 'name_ru', None),
        )
        for row in rows
    ]


# ---------------- Relations: synonyms / antonyms / similars ----------------


async def _relations_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    relation_model,
    models: dict = VOCAB_MODELS,
) -> RelatedWordsOut:
    word = await _get_word_by_id(session, user_id, word_id, models)
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')
    related = await _get_related_words(
        session, user_id, word.id, relation_model, models
    )
    mapped = [map_word(rw) for rw in related]
    return RelatedWordsOut(count=len(mapped), results=mapped)


async def _relations_add_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    target_ids: list[UUID],
    relation_model,
    models: dict = VOCAB_MODELS,
) -> RelatedWordsOut:
    Word = models['Word']
    word = await _get_word_by_id(session, user_id, word_id, models)
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')

    targets = (
        (
            await session.execute(
                select(Word).where(Word.id.in_(target_ids), Word.author_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    if not targets:
        raise HTTPException(status_code=400, detail='No target words found')

    await _add_bidirectional_relations(
        session, word.id, [t.id for t in targets], relation_model
    )
    await session.commit()
    return await _relations_list_service(
        session=session,
        user_id=user_id,
        word_id=word_id,
        relation_model=relation_model,
        models=models,
    )


async def _relations_remove_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    word_id: UUID,
    target_ids: list[UUID],
    relation_model,
    models: dict = VOCAB_MODELS,
) -> RelatedWordsOut:
    Word = models['Word']
    word = await _get_word_by_id(session, user_id, word_id, models)
    if not word:
        raise HTTPException(status_code=404, detail='Word not found')

    targets = (
        (
            await session.execute(
                select(Word.id).where(
                    Word.id.in_(target_ids), Word.author_id == user_id
                )
            )
        )
        .scalars()
        .all()
    )
    if not targets:
        raise HTTPException(status_code=400, detail='No target words found')

    await _remove_bidirectional_relations(session, word.id, targets, relation_model)
    await session.commit()
    return await _relations_list_service(
        session=session,
        user_id=user_id,
        word_id=word_id,
        relation_model=relation_model,
        models=models,
    )


async def synonyms_list_service(**kwargs) -> RelatedWordsOut:
    kwargs['relation_model'] = VOCAB_MODELS['Synonym']
    return await _relations_list_service(**kwargs)


async def synonyms_add_service(**kwargs) -> RelatedWordsOut:
    kwargs['relation_model'] = VOCAB_MODELS['Synonym']
    return await _relations_add_service(**kwargs)


async def synonyms_remove_service(**kwargs) -> RelatedWordsOut:
    kwargs['relation_model'] = VOCAB_MODELS['Synonym']
    return await _relations_remove_service(**kwargs)


async def antonyms_list_service(**kwargs) -> RelatedWordsOut:
    kwargs['relation_model'] = VOCAB_MODELS['Antonym']
    return await _relations_list_service(**kwargs)


async def antonyms_add_service(**kwargs) -> RelatedWordsOut:
    kwargs['relation_model'] = VOCAB_MODELS['Antonym']
    return await _relations_add_service(**kwargs)


async def antonyms_remove_service(**kwargs) -> RelatedWordsOut:
    kwargs['relation_model'] = VOCAB_MODELS['Antonym']
    return await _relations_remove_service(**kwargs)


async def similars_list_service(**kwargs) -> RelatedWordsOut:
    kwargs['relation_model'] = VOCAB_MODELS['Similar']
    return await _relations_list_service(**kwargs)


async def similars_add_service(**kwargs) -> RelatedWordsOut:
    kwargs['relation_model'] = VOCAB_MODELS['Similar']
    return await _relations_add_service(**kwargs)


async def similars_remove_service(**kwargs) -> RelatedWordsOut:
    kwargs['relation_model'] = VOCAB_MODELS['Similar']
    return await _relations_remove_service(**kwargs)


# ---------------- Colections ----------------


async def collection_words_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    params: WordsListParams,
    models: dict = VOCAB_MODELS,
) -> PageOut:
    """
    List words in collections without filtering by author.

    This is used for collection profile to show all words in a collection,
    including accepted suggested words belonging to other authors.
    """
    Word = models['Word']
    WordTranslations = models['WordTranslations']
    WordImageAssociations = models['WordImageAssociations']
    FavoriteWord = models['FavoriteWord']

    # Start from all words; collection scoping is applied via filters
    stmt = select(Word)

    # Apply all filters using the filters module (includes collections filter)
    stmt = apply_word_filters(stmt, params, models=models, user_id=user_id)

    stmt = stmt.options(
        selectinload(Word.tags),
        selectinload(Word.types),
        selectinload(Word.wordtranslations).selectinload(WordTranslations.translation),
        selectinload(Word.wordimageassociations).selectinload(
            WordImageAssociations.image
        ),
        selectinload(Word.language),
        selectinload(Word.author),
    )

    search_fields = ['text']
    stmt = apply_search(stmt, Word, params.search, search_fields)

    ordering_map = {
        'text': Word.text,
        '-text': Word.text.desc(),
        'created': Word.created,
        '-created': Word.created.desc(),
        'modified': Word.modified,
        '-modified': Word.modified.desc(),
    }
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default='-modified')

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    stmt = stmt.offset(params.offset).limit(params.limit)
    rows = (await session.execute(stmt)).scalars().all()

    # mark favorites
    fav_ids = set(
        (
            await session.execute(
                select(FavoriteWord.word_id).where(
                    FavoriteWord.user_id == user_id,
                    FavoriteWord.word_id.in_([w.id for w in rows]),
                )
            )
        )
        .scalars()
        .all()
    )
    results = []
    for w in rows:
        w._favorite = w.id in fav_ids

        # Decide schema based on author:
        # - If the word belongs to the current user, use the regular vocabulary shape (WordListOut via map_word)
        # - Otherwise, use the published shape with full author info (WordListWithAuthorOut)
        if w.author_id == user_id:
            # Standard vocabulary mapping (author as string username)
            results.append(map_word(w))
        else:
            author = getattr(w, 'author', None)

            # Get base word fields (WordListOut) then enrich to WordListWithAuthorOut
            base_dto = map_word(w)
            base_dict = base_dto.model_dump()

            # Add simplified author fields
            base_dict['author'] = (
                {
                    'slug': getattr(author, 'slug', None),
                    'username': getattr(author, 'username', None),
                    'first_name': getattr(author, 'first_name', None),
                    'profile_image_url': getattr(author, 'profile_image_url', None),
                }
                if author is not None
                else None
            )

            # Remove activity_status and activity_progress from published words
            base_dict.pop('activity_status', None)
            base_dict.pop('activity_progress', None)

            # Validate as WordListWithAuthorOut and append its dict representation
            results.append(WordListWithAuthorOut.model_validate(base_dict))

    return PageOut(page=params.page, limit=params.limit, count=total, results=results)
