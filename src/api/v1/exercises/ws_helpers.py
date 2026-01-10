"""Exercises websocket helpers (SQLAlchemy-based)."""

from __future__ import annotations

import random
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import update, func

from api.v1.vocabulary.models import VOCAB_MODELS
from apps.exercises.constants import (
    exercises_lookups,
    ExercisesInputModeEnum,
    ExercisesAnswerEnum,
    TaskTypesEnum,
    hints_codes,
    TimeLimitModeEnum,
)
from apps.exercises.models import (
    ExerciseConfiguration,
    ExerciseSessionHistory,
    ExerciseSessionTasksHistory,
    Hint,
)


def get_session_channel(user_id: UUID) -> str:
    return f'exercise_session:{user_id}'


async def load_config(session: AsyncSession, conf_id: str) -> ExerciseConfiguration:
    cfg = (
        await session.execute(
            select(ExerciseConfiguration)
            .where(ExerciseConfiguration.id == conf_id)
            .options(
                selectinload(ExerciseConfiguration.words),
                selectinload(ExerciseConfiguration.hints_available),
                selectinload(ExerciseConfiguration.exercise),
            )
        )
    ).scalar_one_or_none()
    if not cfg:
        raise ValueError('config_not_found')
    return cfg


async def fetch_config_words(session: AsyncSession, cfg: ExerciseConfiguration):
    Word = VOCAB_MODELS['Word']
    rows = (
        (
            await session.execute(
                select(Word)
                .where(Word.id.in_([w.id for w in cfg.words]))
                .options(
                    selectinload(Word.translations),
                    selectinload(Word.language),
                    selectinload(Word.definitions),
                    selectinload(Word.similars),
                    selectinload(Word.image_associations),
                )
            )
        )
        .scalars()
        .all()
    )
    return rows


def _shuffle_words(words):
    words_shuffled = list(words)
    random.shuffle(words_shuffled)
    return words_shuffled


def _pick_word_translations(word):
    translations = getattr(word, 'translations', []) or []
    return [
        (str(getattr(t, 'id', '')), t.text, getattr(t.language, 'isocode', None))
        for t in translations
    ]


def _pick_word_definitions(word):
    definitions = getattr(word, 'definitions', []) or []
    return [
        (str(getattr(d, 'id', '')), d.text, getattr(d.language, 'isocode', None))
        for d in definitions
    ]


def _random_input_modes(base_mode: str, size: int) -> list[str] | None:
    if base_mode == ExercisesInputModeEnum.ALTERNATELY:
        choices = (
            ExercisesInputModeEnum.FREE_INPUT,
            ExercisesInputModeEnum.VARIANTS,
        )
        return [random.choice(choices) for _ in range(size)]
    if base_mode == ExercisesInputModeEnum.ALTERNATELY_MAX:
        choices = (
            ExercisesInputModeEnum.FREE_INPUT,
            ExercisesInputModeEnum.FREE_INPUT_MAX,
            ExercisesInputModeEnum.VARIANTS,
        )
        return [random.choice(choices) for _ in range(size)]
    return None


def _random_translations_modes(base_mode: str, size: int) -> list[str] | None:
    if base_mode == 'ALTERNATELY':
        choices = ('L', 'N')
        return [random.choice(choices) for _ in range(size)]
    return None


def _random_definitions_modes(base_mode: str, size: int) -> list[str] | None:
    if base_mode == 'ALTERNATELY':
        choices = ('WBDEF', 'DEFBYWORD')
        return [random.choice(choices) for _ in range(size)]
    return None


async def build_tasks(cfg: ExerciseConfiguration, words, user) -> list[dict[str, Any]]:
    """
    Rebuild tasks roughly matching DRF behavior:
    - respects repetitions_amount and problematic duplication
    - randomizes input_mode/translations_mode/definitions_mode where configured
    - builds variants for variants modes
    """
    task_words = list(words)
    # repetitions
    for _ in range(max(cfg.repetitions_amount or 1, 1) - 1):
        task_words.extend(words)
    # duplicate problematic twice
    task_words.extend([w for w in words if getattr(w, 'is_problematic', False)])
    task_words.extend([w for w in words if getattr(w, 'is_problematic', False)])
    task_words = _shuffle_words(task_words)

    random_input_modes = _random_input_modes(cfg.input_mode, len(task_words))
    random_trans_modes = _random_translations_modes(
        cfg.translations_mode, len(task_words)
    )
    random_def_modes = _random_definitions_modes(cfg.definitions_mode, len(task_words))

    tasks = []
    for idx, w in enumerate(task_words):
        input_mode = (
            random_input_modes[idx]
            if random_input_modes
            else (cfg.input_mode or ExercisesInputModeEnum.FREE_INPUT)
        )
        translations_mode = (
            random_trans_modes[idx] if random_trans_modes else cfg.translations_mode
        )
        definitions_mode = (
            random_def_modes[idx] if random_def_modes else cfg.definitions_mode
        )
        if cfg.time_limit_mode == TimeLimitModeEnum.RANDOM and cfg.answer_time_limit:
            answer_time_limit = random.choice([None, cfg.answer_time_limit])
        else:
            answer_time_limit = cfg.answer_time_limit

        # build right answers and task based on exercise slug
        task_language = getattr(w.language, 'isocode', None)
        task_type = TaskTypesEnum.TEXT
        right_answers: list[str] = []
        variants: list[str] = []
        task_value: Any = w.text
        task_related_id = None
        image_width = None
        image_height = None
        right_answers_words_data: list[dict[str, Any]] = []
        right_answers_translations_data: list[dict[str, Any]] = []
        right_answers_definitions_data: list[dict[str, Any]] = []
        similars_texts: list[str] = [
            sw.text
            for sw in getattr(w, 'similars', []) or []
            if getattr(sw, 'text', None)
        ]

        if cfg.exercise.slug == exercises_lookups.TRANSLATOR_EXERCISE_SLUG:
            translations = _pick_word_translations(w)
            right_answers = [t[1] for t in translations]
            if translations_mode == 'L':
                pass
            right_answers_translations_data = [
                {'id': tid, 'text': ttext, 'language': tlang}
                for tid, ttext, tlang in translations
            ]
        elif cfg.exercise.slug == exercises_lookups.ASSOCIATE_EXERCISE_SLUG:
            imgs = getattr(w, 'image_associations', []) or []
            if imgs:
                img = random.choice(imgs)
                task_type = TaskTypesEnum.IMAGE
                task_value = img.image_url
                image_width = img.width
                image_height = img.height
                task_related_id = str(img.id)
            right_answers = [w.text]
        elif cfg.exercise.slug == exercises_lookups.WITH_LETTER_EXERCISE_SLUG:
            task_value = w.text[0] if w.text else ''
            task_type = TaskTypesEnum.TEXT
            task_language = getattr(w.language, 'isocode', None)
            right_answers = [w.text] if w.text else []
            # include words list as serialized texts for convenience
            right_answers_words_data = [
                {'id': str(word.id), 'text': word.text}
                for word in task_words
                if word.text.startswith(task_value)
            ]
        elif cfg.exercise.slug == exercises_lookups.DEFINITIONS_TIME_EXERCISE_SLUG:
            defs = _pick_word_definitions(w)
            if definitions_mode == 'WBDEF':
                task_value = w.text
                right_answers = [d[1] for d in defs]
                right_answers_definitions_data = [
                    {'id': did, 'text': dtext, 'language': dlang}
                    for did, dtext, dlang in defs
                ]
            else:
                if defs:
                    did, dtext, dlang = random.choice(defs)
                    task_value = dtext
                    right_answers = [w.text]
                    right_answers_words_data = [{'id': str(w.id), 'text': w.text}]

        # variants
        if input_mode in (
            ExercisesInputModeEnum.VARIANTS,
            ExercisesInputModeEnum.VARIANTS_MAX,
        ):
            pool = set()
            pool.update(right_answers)
            # add similars and other words as distractors
            pool.update(similars_texts)
            while len(pool) < max(4, len(right_answers) + 1):
                pool.add(random.choice(task_words).text)
            variants = _shuffle_words(list(pool))

        task = {
            'task': task_value,
            'task_type': task_type,
            'task_language': task_language,
            'task_word': str(w.id),
            'task_related_id': task_related_id,
            'variants': variants,
            'input_mode': input_mode,
            'translations_mode': translations_mode,
            'definitions_mode': definitions_mode,
            'answer_time_limit': answer_time_limit,
            'right_answers': right_answers,
            'right_answers_words_data': right_answers_words_data,
            'right_answers_translations_data': right_answers_translations_data,
            'right_answers_definitions_data': right_answers_definitions_data,
            'hints_available': [h.code for h in cfg.hints_available]
            if getattr(cfg, 'hints_available', None)
            else [],
            'image_width': image_width,
            'image_height': image_height,
            'similars': similars_texts,
        }
        tasks.append(task)

    random.shuffle(tasks)
    return tasks


def verdict_for_answer(answer: str, right_answers: Iterable[str]) -> str:
    ans = (answer or '').strip().lower()
    for r in right_answers:
        if ans == (r or '').strip().lower():
            return ExercisesAnswerEnum.CORRECT
    return ExercisesAnswerEnum.INCORRECT


async def create_session_history(
    session: AsyncSession,
    cfg: ExerciseConfiguration,
    words_count: int,
    tasks_count: int,
    user_id: UUID,
) -> ExerciseSessionHistory:
    hist = ExerciseSessionHistory(
        user_id=user_id,
        exercise_id=cfg.exercise_id,
        words_amount=words_count,
        tasks_amount=tasks_count,
    )
    session.add(hist)
    await session.commit()
    await session.refresh(hist)
    return hist


async def persist_task_history(
    session: AsyncSession,
    hist: ExerciseSessionHistory,
    task_index: int,
    task: dict[str, Any],
    answers_list: list[str],
    verdicts_list: list[str],
    answer_time: float,
    hints_used: list[str],
    existing_id: UUID | None = None,
):
    if existing_id:
        obj = (
            await session.execute(
                select(ExerciseSessionTasksHistory).where(
                    ExerciseSessionTasksHistory.id == existing_id
                )
            )
        ).scalar_one_or_none()
    else:
        obj = None

    if obj is None:
        obj = ExerciseSessionTasksHistory(
            session_id=hist.id,
            task=task.get('task'),
            task_type=task.get('task_type'),
            task_language=task.get('task_language'),
            task_index=task_index,
            answer=answers_list[-1] if answers_list else '',
            verdict=verdicts_list[-1]
            if verdicts_list
            else ExercisesAnswerEnum.INCORRECT,
            answers_list=str(answers_list),
            verdicts_list=str(verdicts_list),
            answer_time=answer_time,
            answer_time_limit=task.get('answer_time_limit'),
            image_width=task.get('image_width'),
            image_height=task.get('image_height'),
            task_word_id=task.get('task_word'),
            task_translation_id=None,
        )
        session.add(obj)
    else:
        obj.answer = answers_list[-1] if answers_list else obj.answer
        obj.verdict = verdicts_list[-1] if verdicts_list else obj.verdict
        obj.answers_list = str(answers_list)
        obj.verdicts_list = str(verdicts_list)
        obj.answer_time = (obj.answer_time or 0) + answer_time
        obj.answer_time_limit = task.get('answer_time_limit')
        obj.image_width = task.get('image_width')
        obj.image_height = task.get('image_height')

    # right answers relationships
    Word = VOCAB_MODELS['Word']
    if task.get('right_answers'):
        words = (
            (
                await session.execute(
                    select(Word).where(
                        Word.text.in_(task['right_answers']),
                        Word.author_id == hist.user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        if words:
            obj.right_answers_words.extend(words)
    if task.get('right_answers_translations_data'):
        WordTranslation = VOCAB_MODELS['WordTranslation']
        trs = (
            (
                await session.execute(
                    select(WordTranslation).where(
                        WordTranslation.id.in_(
                            [
                                UUID(t['id'])
                                for t in task['right_answers_translations_data']
                                if t.get('id')
                            ]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        obj.right_answers_translations.extend(trs)
    if task.get('right_answers_definitions_data'):
        Definition = VOCAB_MODELS['Definition']
        defs = (
            (
                await session.execute(
                    select(Definition).where(
                        Definition.id.in_(
                            [
                                UUID(d['id'])
                                for d in task['right_answers_definitions_data']
                                if d.get('id')
                            ]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        obj.right_answers_definitions.extend(defs)
    # hints used
    if hints_used:
        HintModel = Hint
        hints = (
            (
                await session.execute(
                    select(HintModel).where(HintModel.code.in_(hints_used))
                )
            )
            .scalars()
            .all()
        )
        obj.hints_used.extend(hints)

    await session.commit()
    await session.refresh(obj)
    return obj


async def update_history_totals(
    session: AsyncSession,
    hist: ExerciseSessionHistory,
    verdict: str | None,
    complete_time: float | None = None,
):
    if verdict:
        if verdict == ExercisesAnswerEnum.CORRECT:
            hist.corrects_amount += 1
        elif verdict == ExercisesAnswerEnum.SEMI_CORRECT:
            hist.semi_corrects_amount += 1
        else:
            hist.incorrects_amount += 1
    if complete_time is not None:
        hist.complete_time = complete_time
    await session.commit()
    await session.refresh(hist)


async def finalize_history(
    session: AsyncSession, hist: ExerciseSessionHistory, complete_time: float
):
    hist.complete_time = complete_time
    await session.commit()
    await session.refresh(hist)
    return hist


def build_hint_response(
    task: dict[str, Any], hint_code: str, used_keys: list[str]
) -> dict[str, Any]:
    """
    Hint generation aligned with original behaviors:
    - FIRST_LETTER: returns next letter of an unseen right answer (word/translation/definition)
    - LETTERS_AMOUNT: returns length of a right answer
    - REMOVE_INCORRECT: returns index of an incorrect variant to remove
    - SYNONYM: returns one similar text if present
    - IMAGE: returns image metadata if present
    """
    right_answers = task.get('right_answers', []) or []
    variants = task.get('variants', []) or []
    similars = task.get('similars', []) or []
    hint_payload: dict[str, Any] = {'hint_code': hint_code}

    if hint_code == hints_codes.FIRST_LETTER and right_answers:
        # find first right answer with unused prefix
        for ra in right_answers:
            if ra:
                # used_keys may store already revealed prefixes; we reveal next char
                already_revealed = len(used_keys)
                if already_revealed < len(ra):
                    hint_payload['hint_data'] = {'letter': ra[already_revealed]}
                    hint_payload['last_hint'] = already_revealed + 1 >= len(ra)
                    return hint_payload
        hint_payload['last_hint'] = True
        return hint_payload

    if hint_code == hints_codes.LETTERS_AMOUNT and right_answers:
        hint_payload['hint_data'] = {'letters_amount': len(right_answers[0])}
        hint_payload['last_hint'] = True
        return hint_payload

    if hint_code == hints_codes.REMOVE_INCORRECT and variants:
        incorrect = [v for v in variants if v not in right_answers]
        if incorrect:
            victim = random.choice(incorrect)
            hint_payload['hint_data'] = {'incorrect_index': variants.index(victim)}
        else:
            hint_payload['hint_data'] = {}
        hint_payload['last_hint'] = True
        return hint_payload

    if hint_code == hints_codes.SYNONYM and similars:
        hint_payload['hint_data'] = {'synonym': random.choice(similars)}
        hint_payload['last_hint'] = len(similars) <= 1
        return hint_payload

    if hint_code == hints_codes.IMAGE and task.get('task_type') == TaskTypesEnum.IMAGE:
        hint_payload['hint_data'] = {
            'image_id': task.get('task_related_id'),
            'image_url': task.get('task'),
        }
        hint_payload['last_hint'] = True
        return hint_payload

    hint_payload['hint_data'] = {}
    hint_payload['last_hint'] = True
    return hint_payload


async def update_words_last_exercise_date(session: AsyncSession, word_ids: list[UUID]):
    Word = VOCAB_MODELS['Word']
    await session.execute(
        update(Word).where(Word.id.in_(word_ids)).values(last_exercise_date=func.now())
    )
    await session.commit()
