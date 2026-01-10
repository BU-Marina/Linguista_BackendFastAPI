"""Vocabulary services (simplified FastAPI port)."""

from __future__ import annotations

from uuid import UUID
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import select, func, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.ordering import apply_ordering
from api.v1.utils.searching import apply_search
from core.celery.app import celery_app
from tasks.constants import (
    UPDATE_AUTHOR_SUBSCRIPTION_INFO,
    UPDATE_COLLECTION_SUBSCRIPTION_INFO,
    CLEAR_EMPTY_VOCAB_OBJECTS,
)

from .models import VOCAB_MODELS
from .schemas import (
    WordIn,
    WordReadOut,
    PageOut,
    MultipleWordsIn,
    MultipleWordsCreateOut,
    RelationWordIn,
    RelatedWordsOut,
    TagOut,
    TypeOut,
)
from .mapping import map_word, map_word_read
from .params import WordsListParams


async def _get_language_ids(session: AsyncSession, isocodes: Iterable[str], Language):
    if not isocodes:
        return {}
    rows = await session.execute(
        select(Language.id, Language.isocode).where(Language.isocode.in_(isocodes))
    )
    return {iso: lang_id for lang_id, iso in rows.fetchall()}


async def _resolve_language_id(
    session: AsyncSession, Language, isocode: str | None
) -> UUID | None:
    if not isocode:
        return None
    row = (
        await session.execute(select(Language.id).where(Language.isocode == isocode))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=400, detail=f"Language not found: {isocode}")
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
    Word = models["Word"]
    Tag = models["Tag"]
    WordType = models["WordType"]
    Language = models["Language"]
    WordTranslation = models["WordTranslation"]
    WordTranslations = models["WordTranslations"]
    Definition = models["Definition"]
    WordDefinitions = models["WordDefinitions"]
    UsageExample = models["UsageExample"]
    WordUsageExamples = models["WordUsageExamples"]
    ImageAssociation = models["ImageAssociation"]
    WordImageAssociations = models["WordImageAssociations"]

    lang_iso = getattr(payload, "language", None) or default_language
    lang_row = (
        await session.execute(select(Language).where(Language.isocode == lang_iso))
    ).scalar_one_or_none()
    if not lang_row:
        raise HTTPException(status_code=400, detail=f"Language not found: {lang_iso}")

    word = Word(
        text=payload.text,
        language_id=lang_row.id,
        author_id=user_id,
        note=getattr(payload, "note", None),
        activity_status=getattr(payload, "activity_status", None),
    )
    session.add(word)
    await session.flush()

    tags = getattr(payload, "tags", None) or []
    if tags:
        tags_rows = (
            (await session.execute(select(Tag).where(Tag.name.in_(tags))))
            .scalars()
            .all()
        )
        existing_names = {t.name for t in tags_rows}
        for name in tags:
            if name not in existing_names:
                t = Tag(name=name)
                session.add(t)
                tags_rows.append(t)
                existing_names.add(name)
        word.tags = tags_rows

    types = getattr(payload, "types", None) or []
    if types:
        types_rows = (
            (
                await session.execute(
                    select(WordType).where(
                        or_(WordType.name_en.in_(types), WordType.name_ru.in_(types))
                    )
                )
            )
            .scalars()
            .all()
        )
        word.types = types_rows

    translations_objs = []
    for tr in getattr(payload, "translations", []) or []:
        lang_id = (
            await _resolve_language_id(session, Language, tr.language)
            if tr.language
            else word.language_id
        )
        t = WordTranslation(text=tr.text, language_id=lang_id, author_id=user_id)
        session.add(t)
        await session.flush()
        session.add(WordTranslations(word_id=word.id, translation_id=t.id))
        translations_objs.append(t)

    definitions_objs = []
    for d in getattr(payload, "definitions", []) or []:
        lang_id = (
            await _resolve_language_id(session, Language, d.language)
            if d.language
            else word.language_id
        )
        definition = Definition(
            text=d.text,
            translation=d.translation,
            language_id=lang_id,
            author_id=user_id,
        )
        session.add(definition)
        await session.flush()
        session.add(WordDefinitions(word_id=word.id, definition_id=definition.id))
        definitions_objs.append(definition)

    examples_objs = []
    for ex in getattr(payload, "examples", []) or []:
        lang_id = (
            await _resolve_language_id(session, Language, ex.language)
            if ex.language
            else word.language_id
        )
        example = UsageExample(
            text=ex.text,
            translation=ex.translation,
            language_id=lang_id,
            author_id=user_id,
            source=ex.source or "OTH",
            source_name=ex.source_name,
            source_url=ex.source_url,
        )
        session.add(example)
        await session.flush()
        session.add(WordUsageExamples(word_id=word.id, example_id=example.id))
        examples_objs.append(example)

    images_objs = []
    for img in getattr(payload, "images", []) or []:
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
    Word = models["Word"]
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
                raise HTTPException(status_code=404, detail="Related word not found")
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


async def _get_word_by_slug(session: AsyncSession, user_id, slug: str, models):
    Word = models["Word"]
    return (
        await session.execute(
            select(Word)
            .where(Word.slug == slug, Word.author_id == user_id)
            .options(
                selectinload(Word.tags),
                selectinload(Word.types),
                selectinload(Word.language),
            )
        )
    ).scalar_one_or_none()


async def _get_related_words(
    session: AsyncSession,
    user_id,
    word_id,
    relation_model,
    models,
) -> list:
    Word = models["Word"]
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


async def words_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    params: WordsListParams,
    models: dict = VOCAB_MODELS,
) -> PageOut:
    Word = models["Word"]
    Language = models["Language"]
    Tag = models["Tag"]
    WordType = models["WordType"]
    FavoriteWord = models["FavoriteWord"]

    stmt = select(Word).where(Word.author_id == user_id)

    if params.languages:
        stmt = stmt.join(Language).where(Language.isocode.in_(params.languages))
    if params.tags:
        stmt = stmt.join(Word.tags).where(Tag.name.in_(params.tags))
    if params.types:
        stmt = stmt.join(Word.types).where(
            or_(WordType.name_en.in_(params.types), WordType.name_ru.in_(params.types))
        )
    if params.favorite_only:
        stmt = stmt.join(FavoriteWord).where(FavoriteWord.user_id == user_id)

    stmt = stmt.options(
        selectinload(Word.tags),
        selectinload(Word.types),
        selectinload(Word.translations),
        selectinload(Word.language),
    )

    search_fields = ["text"]
    stmt = apply_search(stmt, Word, params.search, search_fields)

    ordering_map = {
        "text": Word.text,
        "-text": Word.text.desc(),
        "created": Word.created,
        "-created": Word.created.desc(),
        "modified": Word.modified,
        "-modified": Word.modified.desc(),
    }
    stmt = apply_ordering(stmt, params.ordering, ordering_map, default="-modified")

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
        results.append(map_word(w))

    return PageOut(page=params.page, limit=params.limit, count=total, results=results)


async def word_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    payload: WordIn,
    models: dict = VOCAB_MODELS,
) -> WordReadOut:
    Synonym = models["Synonym"]
    Antonym = models["Antonym"]
    Similar = models["Similar"]

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
    await session.refresh(word)
    word._favorite = False
    celery_app.send_task(
        UPDATE_AUTHOR_SUBSCRIPTION_INFO,
        args=[str(user_id), {"new_words": [str(word.id)]}, None],
    )
    return map_word_read(word)


async def multiple_words_create_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    payload: MultipleWordsIn,
    params: WordsListParams | None = None,
    models: dict = VOCAB_MODELS,
) -> MultipleWordsCreateOut:
    Word = models["Word"]
    Collection = models["Collection"]
    WordsInCollections = models["WordsInCollections"]
    Synonym = models["Synonym"]
    Antonym = models["Antonym"]
    Similar = models["Similar"]

    created_words = []

    for item in payload.words:
        word = await _create_word_with_nested(
            session,
            user_id=user_id,
            payload=item,
            models=models,
            default_language=item.language,
        )

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

        created_words.append(word)

    # attach to collections if provided
    collections = []
    if payload.collections:
        collections = (
            (
                await session.execute(
                    select(Collection).where(
                        Collection.slug.in_(payload.collections),
                        Collection.author_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        missing = set(payload.collections) - {c.slug for c in collections}
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Collections not found: {', '.join(sorted(missing))}",
            )

        for coll in collections:
            for w in created_words:
                session.add(WordsInCollections(word_id=w.id, collection_id=coll.id))

    await session.commit()
    for w in created_words:
        await session.refresh(w)
        w._favorite = False

    celery_app.send_task(
        UPDATE_AUTHOR_SUBSCRIPTION_INFO,
        args=[str(user_id), {"new_words": [str(w.id) for w in created_words]}, None],
    )

    # reuse list service for response
    params = params or WordsListParams()
    params, total, results = await words_list_service(
        session=session,
        user_id=user_id,
        params=params,
        models=models,
    )
    return MultipleWordsCreateOut(
        page=params.page,
        limit=params.limit,
        count=total,
        results=results,
        words_created_count=len(created_words),
        words_created=[w.id for w in created_words],
        collections_count=len(collections),
    )


async def word_retrieve_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = VOCAB_MODELS,
) -> WordReadOut:
    Word = models["Word"]
    FavoriteWord = models["FavoriteWord"]
    WordTranslation = models["WordTranslation"]
    WordTranslations = models["WordTranslations"]
    Definition = models["Definition"]
    WordDefinitions = models["WordDefinitions"]
    UsageExample = models["UsageExample"]
    WordUsageExamples = models["WordUsageExamples"]
    ImageAssociation = models["ImageAssociation"]
    WordImageAssociations = models["WordImageAssociations"]

    stmt = (
        select(Word)
        .where(Word.slug == slug, Word.author_id == user_id)
        .options(
            selectinload(Word.tags),
            selectinload(Word.types),
            selectinload(Word.language),
        )
    )
    word = (await session.execute(stmt)).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

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

    fav = (
        await session.execute(
            select(func.count())
            .select_from(FavoriteWord)
            .where(FavoriteWord.user_id == user_id, FavoriteWord.word_id == word.id)
        )
    ).scalar_one()
    word._favorite = fav > 0
    return map_word_read(word)


async def word_update_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    payload: WordIn,
    models: dict = VOCAB_MODELS,
) -> WordReadOut:
    Word = models["Word"]
    Tag = models["Tag"]
    WordType = models["WordType"]
    Language = models["Language"]

    word = (
        await session.execute(
            select(Word)
            .where(Word.slug == slug, Word.author_id == user_id)
            .options(selectinload(Word.tags), selectinload(Word.types))
        )
    ).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    lang_row = (
        await session.execute(
            select(Language).where(Language.isocode == payload.language)
        )
    ).scalar_one_or_none()
    if not lang_row:
        raise HTTPException(status_code=400, detail="Language not found")

    word.text = payload.text
    word.language_id = lang_row.id
    word.note = payload.note
    word.activity_status = payload.activity_status

    if payload.tags is not None:
        tags_rows = (
            (await session.execute(select(Tag).where(Tag.name.in_(payload.tags))))
            .scalars()
            .all()
        )
        existing_names = {t.name for t in tags_rows}
        for name in payload.tags:
            if name not in existing_names:
                t = Tag(name=name)
                session.add(t)
                tags_rows.append(t)
                existing_names.add(name)
        word.tags = tags_rows

    if payload.types is not None:
        types_rows = (
            (
                await session.execute(
                    select(WordType).where(
                        or_(
                            WordType.name_en.in_(payload.types),
                            WordType.name_ru.in_(payload.types),
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        word.types = types_rows

    await session.commit()
    await session.refresh(word)
    word._favorite = False
    return map_word_read(word)


async def word_delete_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = VOCAB_MODELS,
) -> None:
    Word = models["Word"]
    word = (
        await session.execute(
            select(Word).where(Word.slug == slug, Word.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    await session.delete(word)
    await session.commit()
    celery_app.send_task(
        UPDATE_COLLECTION_SUBSCRIPTION_INFO,
        args=[None, {"removed_words": [str(word.id)]}, None],
        kwargs={"collections_pks": []},
    )
    celery_app.send_task(
        UPDATE_AUTHOR_SUBSCRIPTION_INFO,
        args=[str(user_id), {"removed_words": [str(word.id)]}, None],
    )
    celery_app.send_task(
        CLEAR_EMPTY_VOCAB_OBJECTS,
        args=[str(user_id), {}],
        kwargs={"all": True},
    )


async def word_favorite_toggle_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = VOCAB_MODELS,
) -> WordReadOut:
    Word = models["Word"]
    FavoriteWord = models["FavoriteWord"]

    word = (
        await session.execute(
            select(Word).where(Word.slug == slug, Word.author_id == user_id)
        )
    ).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

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
    return await word_retrieve_service(
        session=session, user_id=user_id, slug=slug, models=models
    )


# ---------------- Tags & Types ----------------


async def tags_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    models: dict = VOCAB_MODELS,
) -> list[TagOut]:
    Tag = models["Tag"]
    Word = models["Word"]
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
    models: dict = VOCAB_MODELS,
) -> list[TypeOut]:
    WordType = models["WordType"]
    rows = (
        (await session.execute(select(WordType).order_by(WordType.name_en)))
        .scalars()
        .all()
    )
    return [TypeOut.model_validate(row) for row in rows]


# ---------------- Relations: synonyms / antonyms / similars ----------------


async def _relations_list_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    relation_model,
    models: dict = VOCAB_MODELS,
) -> RelatedWordsOut:
    word = await _get_word_by_slug(session, user_id, slug, models)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    related = await _get_related_words(
        session, user_id, word.id, relation_model, models
    )
    mapped = [map_word(rw) for rw in related]
    return RelatedWordsOut(count=len(mapped), results=mapped)


async def _relations_add_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    target_slugs: list[str],
    relation_model,
    models: dict = VOCAB_MODELS,
) -> RelatedWordsOut:
    Word = models["Word"]
    word = await _get_word_by_slug(session, user_id, slug, models)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    targets = (
        (
            await session.execute(
                select(Word).where(
                    Word.slug.in_(target_slugs), Word.author_id == user_id
                )
            )
        )
        .scalars()
        .all()
    )
    if not targets:
        raise HTTPException(status_code=400, detail="No target words found")

    await _add_bidirectional_relations(
        session, word.id, [t.id for t in targets], relation_model
    )
    await session.commit()
    return await _relations_list_service(
        session=session,
        user_id=user_id,
        slug=slug,
        relation_model=relation_model,
        models=models,
    )


async def _relations_remove_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    target_slugs: list[str],
    relation_model,
    models: dict = VOCAB_MODELS,
) -> RelatedWordsOut:
    Word = models["Word"]
    word = await _get_word_by_slug(session, user_id, slug, models)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    targets = (
        (
            await session.execute(
                select(Word.id).where(
                    Word.slug.in_(target_slugs), Word.author_id == user_id
                )
            )
        )
        .scalars()
        .all()
    )
    if not targets:
        raise HTTPException(status_code=400, detail="No target words found")

    await _remove_bidirectional_relations(session, word.id, targets, relation_model)
    await session.commit()
    return await _relations_list_service(
        session=session,
        user_id=user_id,
        slug=slug,
        relation_model=relation_model,
        models=models,
    )


async def synonyms_list_service(**kwargs) -> RelatedWordsOut:
    kwargs["relation_model"] = VOCAB_MODELS["Synonym"]
    return await _relations_list_service(**kwargs)


async def synonyms_add_service(**kwargs) -> RelatedWordsOut:
    kwargs["relation_model"] = VOCAB_MODELS["Synonym"]
    return await _relations_add_service(**kwargs)


async def synonyms_remove_service(**kwargs) -> RelatedWordsOut:
    kwargs["relation_model"] = VOCAB_MODELS["Synonym"]
    return await _relations_remove_service(**kwargs)


async def antonyms_list_service(**kwargs) -> RelatedWordsOut:
    kwargs["relation_model"] = VOCAB_MODELS["Antonym"]
    return await _relations_list_service(**kwargs)


async def antonyms_add_service(**kwargs) -> RelatedWordsOut:
    kwargs["relation_model"] = VOCAB_MODELS["Antonym"]
    return await _relations_add_service(**kwargs)


async def antonyms_remove_service(**kwargs) -> RelatedWordsOut:
    kwargs["relation_model"] = VOCAB_MODELS["Antonym"]
    return await _relations_remove_service(**kwargs)


async def similars_list_service(**kwargs) -> RelatedWordsOut:
    kwargs["relation_model"] = VOCAB_MODELS["Similar"]
    return await _relations_list_service(**kwargs)


async def similars_add_service(**kwargs) -> RelatedWordsOut:
    kwargs["relation_model"] = VOCAB_MODELS["Similar"]
    return await _relations_add_service(**kwargs)


async def similars_remove_service(**kwargs) -> RelatedWordsOut:
    kwargs["relation_model"] = VOCAB_MODELS["Similar"]
    return await _relations_remove_service(**kwargs)


"""Vocabulary services."""
