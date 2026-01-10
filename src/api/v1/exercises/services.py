"""Exercises services (simplified FastAPI port)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.v1.utils.searching import apply_search
from api.v1.utils.pagination import normalize_pagination
from api.v1.vocabulary.models import VOCAB_MODELS
from core.celery.app import celery_app
from tasks.constants import DELETE_PREVIOUS_EX_CONF

from .models import EXERCISE_MODELS
from .schemas import (
    ExerciseListOut,
    ExerciseDetailOut,
    ExerciseConfigurationIn,
    ExerciseConfigurationOut,
    WordsSetIn,
    WordsSetOut,
    PageOut,
)


async def exercises_list_service(
    session: AsyncSession, user_id: UUID | None
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
            name=ex.name,
            icon=ex.icon,
            available=ex.available,
            favorite=ex.favorite,
            hints_available=[h.id for h in ex.hints_available],
            created=ex.created,
            modified=ex.modified,
        )
        if ex.available:
            available.append(data)
        else:
            unavailable.append(data)

    return ExerciseListOut(available=available, unavailable=unavailable)


async def exercise_detail_service(
    session: AsyncSession, slug: str, user_id: UUID | None
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
        name=ex.name,
        icon=ex.icon,
        available=ex.available,
        favorite=ex.favorite,
        hints_available=[h.id for h in ex.hints_available],
        created=ex.created,
        modified=ex.modified,
    )


async def exercise_favorite_toggle_service(
    session: AsyncSession, slug: str, user_id: UUID
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
    return await exercise_detail_service(session, slug, user_id)


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
        author_id=cfg.author_id,
        answer_time_limit=cfg.answer_time_limit,
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

    cfg = ExerciseConfiguration(
        author_id=user_id,
        exercise_id=ex.id,
        answer_time_limit=payload.answer_time_limit,
        hints_use_amount=payload.hints_use_amount,
        is_default=payload.is_default,
    )
    session.add(cfg)
    await session.flush()

    if words:
        cfg.words = words
    if words_sets:
        cfg.words_set = words_sets
    if hints:
        cfg.hints_available = hints

    await session.commit()
    await session.refresh(cfg)

    if payload.is_default:
        celery_app.send_task(
            DELETE_PREVIOUS_EX_CONF,
            args=[str(cfg.id), str(user_id), str(ex.id), payload.is_default],
        )

    return ExerciseConfigurationOut(
        id=cfg.id,
        exercise_id=cfg.exercise_id,
        author_id=cfg.author_id,
        answer_time_limit=cfg.answer_time_limit,
        hints_use_amount=cfg.hints_use_amount,
        is_default=cfg.is_default,
        words=[w.id for w in cfg.words],
        words_set=[ws.id for ws in cfg.words_set],
        hints_available=[h.id for h in cfg.hints_available],
    )


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
