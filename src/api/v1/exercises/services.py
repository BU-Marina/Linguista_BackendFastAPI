"""Exercises services (simplified FastAPI port)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.searching import apply_search
from api.v1.utils.pagination import normalize_pagination
from api.v1.vocabulary.mapping import map_word
from api.v1.collections.mapping import map_collection
from api.v1.vocabulary.models import VOCAB_MODELS
from api.v1.languages.models import LANGUAGE_MODELS
from core.celery.app import celery_app
from tasks.constants import DELETE_PREVIOUS_EX_CONF
from core.utils.i18n import i18n_get
from apps.exercises.constants import (
    ExercisesInputModeEnum,
    TimeLimitModeEnum,
    TranslationsModeEnum,
    DefinitionsModeEnum,
)
from .models import EXERCISE_MODELS
from .schemas import (
    ExerciseListOut,
    ExerciseDetailOut,
    ExerciseConfigurationIn,
    ExerciseConfigurationOut,
    WordsSetIn,
    WordsSetOut,
    PageOut,
    ExerciseDetailOut as ExerciseDetailSchema,
    HintOut,
)
from apps.exercises.constants import exercises_lookups


def _exercise_name(ex, lang: str) -> str:
    return i18n_get(ex, 'name', lang)


def _exercise_description(ex, lang: str) -> str | None:
    return i18n_get(ex, 'description', lang)


def _exercise_constraint_description(ex, lang: str) -> str | None:
    return i18n_get(ex, 'constraint_description', lang)


def _hint_name(hint, lang: str) -> str:
    return i18n_get(hint, 'name', lang)


def _hint_description(hint, lang: str) -> str:
    return i18n_get(hint, 'description', lang)


async def exercises_list_service(
    session: AsyncSession, user_id: UUID | None, lang: str
) -> ExerciseListOut:
    Exercise = EXERCISE_MODELS['Exercise']
    FavoriteExercise = EXERCISE_MODELS['FavoriteExercise']

    stmt = (
        select(Exercise)
        .options(selectinload(Exercise.hints_available))
        .order_by(Exercise.available.desc(), Exercise.created.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()

    fav_ids: set[UUID] = set()
    if user_id:
        fav_ids = set(
            (
                await session.execute(
                    select(FavoriteExercise.exercise_id).where(
                        FavoriteExercise.user_id == user_id
                    )
                )
            ).scalars()
        )

    available = []
    unavailable = []
    for ex in rows:
        ex.favorite = ex.id in fav_ids
        data = ExerciseDetailOut(
            id=ex.id,
            slug=ex.slug,
            name=_exercise_name(ex, lang),
            description=_exercise_description(ex, lang),
            constraint_description=_exercise_constraint_description(ex, lang),
            icon=ex.icon,
            available=ex.available,
            favorite=ex.favorite,
            hints_available=[
                HintOut(
                    id=h.id,
                    name=_hint_name(h, lang),
                    description=_hint_description(h, lang),
                    code=h.code,
                    variants_mode=h.variants_mode,
                    free_input_mode=h.free_input_mode,
                    word_customization_content_needed=h.word_customization_content_needed,
                )
                for h in ex.hints_available
            ],
            created=ex.created,
            modified=ex.modified,
        )
        if ex.available:
            available.append(data)
        else:
            unavailable.append(data)

    return ExerciseListOut(available=available, unavailable=unavailable)


async def exercises_favorites_list_service(
    session: AsyncSession, user_id: UUID, lang: str
) -> PageOut:
    Exercise = EXERCISE_MODELS['Exercise']
    FavoriteExercise = EXERCISE_MODELS['FavoriteExercise']

    fav_ids = (
        (
            await session.execute(
                select(FavoriteExercise.exercise_id).where(
                    FavoriteExercise.user_id == user_id
                )
            )
        )
        .scalars()
        .all()
    )
    if not fav_ids:
        return PageOut(page=1, limit=32, count=0, results=[])

    stmt = (
        select(Exercise)
        .where(Exercise.id.in_(fav_ids))
        .options(selectinload(Exercise.hints_available))
        .order_by(Exercise.created.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    results = [
        ExerciseDetailSchema(
            id=ex.id,
            slug=ex.slug,
            name=_exercise_name(ex, lang),
            description=_exercise_description(ex, lang),
            constraint_description=_exercise_constraint_description(ex, lang),
            icon=ex.icon,
            available=ex.available,
            favorite=True,
            hints_available=[
                HintOut(
                    id=h.id,
                    name=_hint_name(h, lang),
                    description=_hint_description(h, lang),
                    code=h.code,
                    variants_mode=h.variants_mode,
                    free_input_mode=h.free_input_mode,
                    word_customization_content_needed=h.word_customization_content_needed,
                )
                for h in ex.hints_available
            ],
            created=ex.created,
            modified=ex.modified,
        )
        for ex in rows
    ]
    return PageOut(page=1, limit=len(results) or 1, count=len(results), results=results)


async def exercise_detail_service(
    session: AsyncSession, slug: str, user_id: UUID | None, lang: str
) -> ExerciseDetailOut:
    Exercise = EXERCISE_MODELS['Exercise']
    FavoriteExercise = EXERCISE_MODELS['FavoriteExercise']
    stmt = (
        select(Exercise)
        .where(Exercise.slug == slug)
        .options(selectinload(Exercise.hints_available))
    )
    ex = (await session.execute(stmt)).scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail='Exercise not found')

    if user_id:
        fav = (
            await session.execute(
                select(FavoriteExercise).where(
                    FavoriteExercise.user_id == user_id,
                    FavoriteExercise.exercise_id == ex.id,
                )
            )
        ).scalar_one_or_none()
        ex.favorite = bool(fav)
    else:
        ex.favorite = False

    return ExerciseDetailOut(
        id=ex.id,
        slug=ex.slug,
        name=_exercise_name(ex, lang),
        description=_exercise_description(ex, lang),
        constraint_description=_exercise_constraint_description(ex, lang),
        icon=ex.icon,
        available=ex.available,
        favorite=ex.favorite,
        hints_available=[
            HintOut(
                id=h.id,
                name=_hint_name(h, lang),
                description=_hint_description(h, lang),
                code=h.code,
                variants_mode=h.variants_mode,
                free_input_mode=h.free_input_mode,
                word_customization_content_needed=h.word_customization_content_needed,
            )
            for h in ex.hints_available
        ],
        created=ex.created,
        modified=ex.modified,
    )


async def exercise_favorite_toggle_service(
    session: AsyncSession, slug: str, user_id: UUID, lang: str
) -> ExerciseDetailOut:
    Exercise = EXERCISE_MODELS['Exercise']
    FavoriteExercise = EXERCISE_MODELS['FavoriteExercise']

    ex = (
        await session.execute(
            select(Exercise)
            .where(Exercise.slug == slug)
            .options(selectinload(Exercise.hints_available))
        )
    ).scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail='Exercise not found')

    existing = (
        await session.execute(
            select(FavoriteExercise).where(
                FavoriteExercise.user_id == user_id,
                FavoriteExercise.exercise_id == ex.id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        await session.delete(existing)
        ex.favorite = False
    else:
        session.add(FavoriteExercise(user_id=user_id, exercise_id=ex.id))
        ex.favorite = True

    await session.commit()
    return await exercise_detail_service(session, slug, user_id, lang)


async def exercise_configuration_get_service(
    session: AsyncSession, user_id: UUID, slug: str
) -> ExerciseConfigurationOut:
    Exercise = EXERCISE_MODELS['Exercise']
    ExerciseConfiguration = EXERCISE_MODELS['ExerciseConfiguration']

    ex = (
        await session.execute(select(Exercise).where(Exercise.slug == slug))
    ).scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail='Exercise not found')

    cfg = (
        (
            await session.execute(
                select(ExerciseConfiguration)
                .options(selectinload(ExerciseConfiguration.exercise))
                .where(
                    ExerciseConfiguration.author_id == user_id,
                    ExerciseConfiguration.exercise_id == ex.id,
                )
                .order_by(ExerciseConfiguration.created.desc())
            )
        )
        .scalars()
        .first()
    )
    if not cfg:
        raise HTTPException(status_code=404, detail='Configuration not found')

    return ExerciseConfigurationOut(
        id=cfg.id,
        exercise_id=cfg.exercise_id,
        exercise_slug=getattr(cfg.exercise, 'slug', None),
        author_id=cfg.author_id,
        input_mode=getattr(cfg, 'input_mode', None),
        answer_time_limit=cfg.answer_time_limit,
        time_limit_mode=getattr(cfg, 'time_limit_mode', None),
        repetitions_amount=getattr(cfg, 'repetitions_amount', None),
        translations_mode=getattr(cfg, 'translations_mode', None),
        definitions_mode=getattr(cfg, 'definitions_mode', None),
        hints_use_amount=cfg.hints_use_amount,
        is_default=cfg.is_default,
        words=[w.id for w in cfg.words],
        words_set=[ws.id for ws in cfg.words_set],
        hints_available=[h.id for h in cfg.hints_available],
    )


async def exercise_configuration_create_service(
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    payload: ExerciseConfigurationIn,
    models: dict = EXERCISE_MODELS,
) -> ExerciseConfigurationOut:
    Exercise = models['Exercise']
    ExerciseConfiguration = models['ExerciseConfiguration']
    WordsSet = models['WordsSet']
    Hint = models['Hint']
    Word = VOCAB_MODELS['Word']

    ex = (
        await session.execute(select(Exercise).where(Exercise.slug == slug))
    ).scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail='Exercise not found')

    # validate words ownership
    words = []
    if payload.words:
        words = (
            (
                await session.execute(
                    select(Word).where(
                        Word.id.in_(payload.words), Word.author_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        missing = set(payload.words) - {w.id for w in words}
        if missing:
            raise HTTPException(status_code=400, detail='Some words not found')

    words_sets = []
    if payload.words_set:
        words_sets = (
            (
                await session.execute(
                    select(WordsSet).where(
                        WordsSet.id.in_(payload.words_set),
                        WordsSet.author_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        missing = set(payload.words_set) - {ws.id for ws in words_sets}
        if missing:
            raise HTTPException(status_code=400, detail='Some word sets not found')

    hints = []
    if payload.hints_available:
        hints = (
            (
                await session.execute(
                    select(Hint).where(Hint.id.in_(payload.hints_available))
                )
            )
            .scalars()
            .all()
        )

    # Always create a new configuration (DRF parity); older defaults are
    # cleaned up asynchronously by the Celery task.
    cfg = ExerciseConfiguration(
        author_id=user_id,
        exercise_id=ex.id,
        input_mode=getattr(payload, 'input_mode', None)
        or ExercisesInputModeEnum.FREE_INPUT,
        answer_time_limit=payload.answer_time_limit,
        time_limit_mode=getattr(payload, 'time_limit_mode', None)
        or TimeLimitModeEnum.ALL,
        repetitions_amount=getattr(payload, 'repetitions_amount', None) or 1,
        translations_mode=getattr(payload, 'translations_mode', None)
        or TranslationsModeEnum.FROM_LEARNING,
        definitions_mode=getattr(payload, 'definitions_mode', None)
        or DefinitionsModeEnum.DEFINITION_BY_WORD,
        hints_use_amount=payload.hints_use_amount,
        is_default=payload.is_default,
        words=words or [],
        words_set=words_sets or [],
        hints_available=hints or [],
    )
    session.add(cfg)
    await session.flush()

    if payload.is_default:
        celery_app.send_task(
            DELETE_PREVIOUS_EX_CONF,
            args=[str(cfg.id), str(user_id), str(ex.id), payload.is_default],
        )
    await session.commit()
    await session.refresh(cfg)

    return ExerciseConfigurationOut(
        id=cfg.id,
        exercise_id=cfg.exercise_id,
        exercise_slug=getattr(ex, 'slug', None),
        author_id=cfg.author_id,
        input_mode=getattr(cfg, 'input_mode', None),
        answer_time_limit=cfg.answer_time_limit,
        time_limit_mode=getattr(cfg, 'time_limit_mode', None),
        repetitions_amount=getattr(cfg, 'repetitions_amount', None),
        translations_mode=getattr(cfg, 'translations_mode', None),
        definitions_mode=getattr(cfg, 'definitions_mode', None),
        hints_use_amount=cfg.hints_use_amount,
        is_default=cfg.is_default,
        words=[w.id for w in cfg.words],
        words_set=[ws.id for ws in cfg.words_set],
        hints_available=[h.id for h in cfg.hints_available],
    )


async def exercise_configuration_detail_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    config_id: UUID,
    models: dict = EXERCISE_MODELS,
) -> ExerciseConfigurationOut:
    ExerciseConfiguration = models['ExerciseConfiguration']
    cfg = (
        await session.execute(
            select(ExerciseConfiguration)
            .options(
                selectinload(ExerciseConfiguration.words),
                selectinload(ExerciseConfiguration.words_set),
                selectinload(ExerciseConfiguration.hints_available),
                selectinload(ExerciseConfiguration.exercise),
            )
            .where(
                ExerciseConfiguration.id == config_id,
                ExerciseConfiguration.author_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail='Configuration not found')

    return ExerciseConfigurationOut(
        id=cfg.id,
        exercise_id=cfg.exercise_id,
        exercise_slug=getattr(cfg.exercise, 'slug', None),
        author_id=cfg.author_id,
        input_mode=getattr(cfg, 'input_mode', None),
        answer_time_limit=cfg.answer_time_limit,
        time_limit_mode=getattr(cfg, 'time_limit_mode', None),
        repetitions_amount=getattr(cfg, 'repetitions_amount', None),
        translations_mode=getattr(cfg, 'translations_mode', None),
        definitions_mode=getattr(cfg, 'definitions_mode', None),
        hints_use_amount=cfg.hints_use_amount,
        is_default=cfg.is_default,
        words=[w.id for w in cfg.words],
        words_set=[ws.id for ws in cfg.words_set],
        hints_available=[h.id for h in cfg.hints_available],
    )


async def exercise_configuration_words_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    config_id: UUID,
    page: int = 1,
    limit: int = 32,
    models: dict = EXERCISE_MODELS,
    vocab_models: dict = VOCAB_MODELS,
) -> PageOut:
    ExerciseConfiguration = models['ExerciseConfiguration']
    Word = vocab_models['Word']

    cfg = (
        await session.execute(
            select(ExerciseConfiguration.id).where(
                ExerciseConfiguration.id == config_id,
                ExerciseConfiguration.author_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail='Configuration not found')

    page, limit, offset = normalize_pagination(page, limit)
    association = ExerciseConfiguration.words.property.secondary

    stmt = (
        select(Word)
        .join(association, association.c.word_id == Word.id)
        .where(association.c.exerciseconfiguration_id == config_id)
        .order_by(Word.created.desc())
    )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    results = [map_word(w) for w in rows]
    return PageOut(page=page, limit=limit, count=total, results=results)


async def random_exercise_configuration_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    words_limit: int | None = None,
    models: dict = EXERCISE_MODELS,
    vocab_models: dict = VOCAB_MODELS,
    lang_models: dict = LANGUAGE_MODELS,
) -> ExerciseConfigurationOut:
    Exercise = models['Exercise']
    ExerciseConfiguration = models['ExerciseConfiguration']

    ex = (
        (
            await session.execute(
                select(Exercise)
                .where(Exercise.available.is_(True))
                .order_by(func.random())
            )
        )
        .scalars()
        .first()
    )
    if not ex:
        raise HTTPException(status_code=404, detail='No exercises available')

    limit = words_limit or 32
    available_page = await exercise_available_words_service(
        session=session,
        user_id=user_id,
        slug=ex.slug,
        page=1,
        limit=limit,
        models=models,
        vocab_models=vocab_models,
        lang_models=lang_models,
        random_order=True,
    )
    word_ids = [w.id for w in available_page.results]

    cfg = ExerciseConfiguration(
        author_id=user_id,
        exercise_id=ex.id,
        is_default=False,
    )
    if word_ids:
        Word = vocab_models['Word']
        words = (
            (await session.execute(select(Word).where(Word.id.in_(word_ids))))
            .scalars()
            .all()
        )
        cfg.words.extend(words)

    # attach hints (all available)
    if getattr(ex, 'hints_available', None):
        cfg.hints_available.extend(ex.hints_available)

    session.add(cfg)
    await session.commit()
    await session.refresh(cfg)

    return ExerciseConfigurationOut(
        id=cfg.id,
        exercise_id=cfg.exercise_id,
        exercise_slug=getattr(ex, 'slug', None),
        author_id=cfg.author_id,
        input_mode=getattr(cfg, 'input_mode', None),
        answer_time_limit=cfg.answer_time_limit,
        time_limit_mode=getattr(cfg, 'time_limit_mode', None),
        repetitions_amount=getattr(cfg, 'repetitions_amount', None),
        translations_mode=getattr(cfg, 'translations_mode', None),
        definitions_mode=getattr(cfg, 'definitions_mode', None),
        hints_use_amount=cfg.hints_use_amount,
        is_default=cfg.is_default,
        words=[w.id for w in cfg.words],
        words_set=[ws.id for ws in cfg.words_set],
        hints_available=[h.id for h in cfg.hints_available],
    )


# ------------------------------
# Available words/collections
# ------------------------------


# ------------------------------
# Available words/collections
# ------------------------------


def _base_words_query(models):
    Word = models['Word']
    WordTranslations = models['WordTranslations']
    return select(Word).options(
        selectinload(Word.tags),
        selectinload(Word.types),
        selectinload(Word.language),
        # Eager-load translations via through model to match Published behavior
        selectinload(Word.wordtranslations).selectinload(WordTranslations.translation),
    )


async def exercise_available_words_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    page: int = 1,
    limit: int = 32,
    models: dict = EXERCISE_MODELS,
    vocab_models: dict = VOCAB_MODELS,
    lang_models: dict = LANGUAGE_MODELS,
    random_order: bool = False,
) -> PageOut:
    Exercise = models['Exercise']
    Word = vocab_models['Word']
    WordTranslations = vocab_models['WordTranslations']
    WordTranslation = vocab_models['WordTranslation']
    WordDefinitions = vocab_models['WordDefinitions']
    WordImageAssociations = vocab_models['WordImageAssociations']
    UserNativeLanguage = lang_models['UserNativeLanguage']

    ex = (
        await session.execute(select(Exercise).where(Exercise.slug == slug))
    ).scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail='Exercise not found')

    page, limit, offset = normalize_pagination(page, limit)

    stmt = _base_words_query(vocab_models).where(Word.author_id == user_id)

    match ex.slug:
        case exercises_lookups.TRANSLATOR_EXERCISE_SLUG:
            native_lang_ids = select(UserNativeLanguage.language_id).where(
                UserNativeLanguage.user_id == user_id
            )
            stmt = (
                stmt.join(WordTranslations, WordTranslations.word_id == Word.id)
                .join(
                    WordTranslation,
                    WordTranslation.id == WordTranslations.translation_id,
                )
                .where(WordTranslation.language_id.in_(native_lang_ids))
            )
        case exercises_lookups.ASSOCIATE_EXERCISE_SLUG:
            stmt = stmt.join(
                WordImageAssociations, WordImageAssociations.word_id == Word.id
            )
        case exercises_lookups.WITH_LETTER_EXERCISE_SLUG:
            stmt = stmt.where(func.length(Word.text) > 1)
        case exercises_lookups.DEFINITIONS_TIME_EXERCISE_SLUG:
            stmt = stmt.join(WordDefinitions, WordDefinitions.word_id == Word.id)
        case _:
            # If exercise not recognized, return empty page
            return PageOut(page=page, limit=limit, count=0, results=[])

    if random_order:
        stmt = stmt.order_by(func.random())
    else:
        stmt = stmt.order_by(Word.created.desc())
    stmt = stmt.distinct()

    # Paginate and map to vocabulary word DTOs
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    results = [map_word(w) for w in rows]
    return PageOut(page=page, limit=limit, count=total, results=results)


async def exercise_last_approach_incorrects_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = EXERCISE_MODELS,
) -> list:
    # Placeholder: no history implemented yet
    return []


async def exercise_last_approach_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = EXERCISE_MODELS,
) -> dict:
    # Placeholder: no history implemented yet
    return {}


async def exercise_shared_session_results_service(
    *,
    session: AsyncSession,
    share_key: str,
    models: dict = EXERCISE_MODELS,
) -> dict:
    # Placeholder
    return {}


async def exercise_update_share_link_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = EXERCISE_MODELS,
) -> dict:
    return {'share_link': None}


async def exercise_remove_share_link_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    models: dict = EXERCISE_MODELS,
) -> dict:
    return {'status': 'ok'}


async def exercise_available_collections_service(
    *,
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    page: int = 1,
    limit: int = 32,
    models: dict = EXERCISE_MODELS,
    vocab_models: dict = VOCAB_MODELS,
    lang_models: dict = LANGUAGE_MODELS,
) -> PageOut:
    Exercise = models['Exercise']
    Collection = vocab_models['Collection']
    Word = vocab_models['Word']
    WordsInCollections = vocab_models['WordsInCollections']
    WordTranslations = vocab_models['WordTranslations']
    WordTranslation = vocab_models['WordTranslation']
    WordDefinitions = vocab_models['WordDefinitions']
    WordImageAssociations = vocab_models['WordImageAssociations']
    UserNativeLanguage = lang_models['UserNativeLanguage']

    ex = (
        await session.execute(select(Exercise).where(Exercise.slug == slug))
    ).scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail='Exercise not found')

    page, limit, offset = normalize_pagination(page, limit)

    stmt = select(Collection).where(Collection.author_id == user_id)

    # Join words via WordsInCollections to ensure collections have eligible words
    stmt = stmt.join(
        WordsInCollections, WordsInCollections.collection_id == Collection.id
    )
    stmt = stmt.join(Word, Word.id == WordsInCollections.word_id)

    match ex.slug:
        case exercises_lookups.TRANSLATOR_EXERCISE_SLUG:
            native_lang_ids = select(UserNativeLanguage.language_id).where(
                UserNativeLanguage.user_id == user_id
            )
            stmt = (
                stmt.join(WordTranslations, WordTranslations.word_id == Word.id)
                .join(
                    WordTranslation,
                    WordTranslation.id == WordTranslations.translation_id,
                )
                .where(WordTranslation.language_id.in_(native_lang_ids))
            )
        case exercises_lookups.ASSOCIATE_EXERCISE_SLUG:
            stmt = stmt.join(
                WordImageAssociations, WordImageAssociations.word_id == Word.id
            )
        case exercises_lookups.WITH_LETTER_EXERCISE_SLUG:
            stmt = stmt.where(func.length(Word.text) > 1)
        case exercises_lookups.DEFINITIONS_TIME_EXERCISE_SLUG:
            stmt = stmt.join(WordDefinitions, WordDefinitions.word_id == Word.id)
        case _:
            return PageOut(page=page, limit=limit, count=0, results=[])

    stmt = stmt.order_by(Collection.created.desc()).distinct()

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    results = [map_collection(c, include_words=False) for c in rows]
    return PageOut(page=page, limit=limit, count=total, results=results)


async def words_sets_list_service(
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    page: int,
    limit: int,
    search: str | None,
):
    Exercise = EXERCISE_MODELS['Exercise']
    WordsSet = EXERCISE_MODELS['WordsSet']

    ex = (
        await session.execute(select(Exercise).where(Exercise.slug == slug))
    ).scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail='Exercise not found')

    page, limit, offset = normalize_pagination(page, limit)
    stmt = select(WordsSet).where(
        WordsSet.exercise_id == ex.id, WordsSet.author_id == user_id
    )
    stmt = apply_search(stmt, WordsSet, search, ['name'])
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    results = [
        WordsSetOut(
            id=ws.id,
            slug=ws.slug,
            name=ws.name,
            words=[w.id for w in ws.words],
            created=ws.created,
        )
        for ws in rows
    ]
    return PageOut(page=page, limit=limit, count=total, results=results)


async def words_set_create_service(
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    payload: WordsSetIn,
):
    Exercise = EXERCISE_MODELS['Exercise']
    WordsSet = EXERCISE_MODELS['WordsSet']
    Word = VOCAB_MODELS['Word']

    ex = (
        await session.execute(select(Exercise).where(Exercise.slug == slug))
    ).scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail='Exercise not found')

    words = []
    if payload.words:
        words = (
            (
                await session.execute(
                    select(Word).where(
                        Word.id.in_(payload.words), Word.author_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        missing = set(payload.words) - {w.id for w in words}
        if missing:
            raise HTTPException(status_code=400, detail='Some words not found')

    ws = WordsSet(name=payload.name, author_id=user_id, exercise_id=ex.id)
    session.add(ws)
    await session.flush()
    if words:
        ws.words = words
    await session.commit()
    await session.refresh(ws)
    return WordsSetOut(
        id=ws.id,
        slug=ws.slug,
        name=ws.name,
        words=[w.id for w in ws.words],
        created=ws.created,
    )


async def words_set_detail_service(
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    word_set_slug: str,
):
    WordsSet = EXERCISE_MODELS['WordsSet']
    ws = (
        await session.execute(
            select(WordsSet).where(
                WordsSet.slug == word_set_slug, WordsSet.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail='Words set not found')
    return WordsSetOut(
        id=ws.id,
        slug=ws.slug,
        name=ws.name,
        words=[w.id for w in ws.words],
        created=ws.created,
    )


async def words_set_update_service(
    session: AsyncSession,
    user_id: UUID,
    slug: str,
    word_set_slug: str,
    payload: WordsSetIn,
):
    WordsSet = EXERCISE_MODELS['WordsSet']
    Word = VOCAB_MODELS['Word']

    ws = (
        await session.execute(
            select(WordsSet).where(
                WordsSet.slug == word_set_slug, WordsSet.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail='Words set not found')

    if payload.name:
        ws.name = payload.name
    if payload.words:
        words = (
            (
                await session.execute(
                    select(Word).where(
                        Word.id.in_(payload.words), Word.author_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        ws.words = words

    await session.commit()
    await session.refresh(ws)
    return WordsSetOut(
        id=ws.id,
        slug=ws.slug,
        name=ws.name,
        words=[w.id for w in ws.words],
        created=ws.created,
    )


async def words_set_delete_service(
    session: AsyncSession, user_id: UUID, word_set_slug: str
):
    WordsSet = EXERCISE_MODELS['WordsSet']
    ws = (
        await session.execute(
            select(WordsSet).where(
                WordsSet.slug == word_set_slug, WordsSet.author_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail='Words set not found')
    await session.delete(ws)
    await session.commit()
