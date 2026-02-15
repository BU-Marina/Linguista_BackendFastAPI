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
from core.utils.urls import get_full_media_url
from apps.exercises.constants import (
    exercises_lookups,
    ExercisesInputModeEnum,
    ExercisesAnswerEnum,
    TaskTypesEnum,
    hints_codes,
    TimeLimitModeEnum,
    TranslationsModeEnum,
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
    WordTranslations = VOCAB_MODELS['WordTranslations']
    WordTranslation = VOCAB_MODELS['WordTranslation']
    WordDefinitions = VOCAB_MODELS['WordDefinitions']
    Definition = VOCAB_MODELS['Definition']
    WordImageAssociations = VOCAB_MODELS['WordImageAssociations']
    ImageAssociation = VOCAB_MODELS['ImageAssociation']

    rows = (
        (
            await session.execute(
                select(Word)
                .where(Word.id.in_([w.id for w in cfg.words]))
                .options(
                    selectinload(Word.language),
                    # Eager load translations via through model and cache on word
                    selectinload(Word.wordtranslations)
                    .selectinload(WordTranslations.translation)
                    .selectinload(WordTranslation.language),
                    # Eager load definitions via through model and cache on word
                    selectinload(Word.worddefinitions)
                    .selectinload(WordDefinitions.definition)
                    .selectinload(Definition.language),
                    # Eager load image associations via through model and cache on word
                    selectinload(Word.wordimageassociations)
                    .selectinload(WordImageAssociations.image)
                    .selectinload(ImageAssociation.author),
                )
            )
        )
        .scalars()
        .all()
    )

    # Attach convenient attributes so downstream helpers can keep using
    # `word.translations`, `word.definitions`, and `word.image_associations`
    # just like in the original DRF-based code.
    for w in rows:
        w.translations = [
            wt.translation
            for wt in getattr(w, 'wordtranslations', []) or []
            if getattr(wt, 'translation', None)
        ]
        w.definitions = [
            wd.definition
            for wd in getattr(w, 'worddefinitions', []) or []
            if getattr(wd, 'definition', None)
        ]
        w.image_associations = [
            ia.image
            for ia in getattr(w, 'wordimageassociations', []) or []
            if getattr(ia, 'image', None)
        ]

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
    # Match DRF TranslationsModeEnum.ALTERNATELY: randomly pick FROM_LEARNING / FROM_NATIVE
    if base_mode == TranslationsModeEnum.ALTERNATELY:
        choices = (TranslationsModeEnum.FROM_LEARNING, TranslationsModeEnum.FROM_NATIVE)
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
    # Build task words list based strictly on repetitions_amount:
    # each chosen word appears `repetitions_amount` times. This keeps the
    # total tasks count predictable for the UI: len(words) * repetitions_amount.
    reps = max(cfg.repetitions_amount or 1, 1)
    task_words = []
    for _ in range(reps):
        task_words.extend(words)
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
        right_answers_list: list[str] = []
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
            # Partition translations into "learning" vs "native" based on word.language.
            word_lang = getattr(getattr(w, 'language', None), 'isocode', None)
            native_translations = [
                t for t in translations if t[2] and t[2] != word_lang
            ]

            # FROM_NATIVE: task is a native translation, answer is the word itself.
            if (
                translations_mode == TranslationsModeEnum.FROM_NATIVE
                and native_translations
            ):
                tid, ttext, tlang = random.choice(native_translations)
                task_value = ttext
                task_language = tlang
                task_type = TaskTypesEnum.TEXT
                right_answers_list = [w.text]
                right_answers_words_data = [
                    {
                        'id': str(w.id),
                        'text': w.text,
                        'language': word_lang,
                    }
                ]
            # FROM_LEARNING_TO_LEARNING: simplified port – show translation in learning language,
            # expect another learning-language translation or the base word as answer.
            elif translations_mode == TranslationsModeEnum.FROM_LEARNING_TO_LEARNING:
                learning_translations = [
                    t for t in translations if t[2] == word_lang
                ] or translations
                tid, ttext, tlang = random.choice(learning_translations)
                task_value = ttext
                task_language = tlang
                task_type = TaskTypesEnum.TEXT
                # Treat the base word as the primary right answer, plus other learning variants.
                right_answers_list = [w.text] + [
                    t[1] for t in learning_translations if t[1] != w.text
                ]
                right_answers_words_data = [
                    {
                        'id': str(w.id),
                        'text': w.text,
                        'language': word_lang,
                    }
                ]
            # Default / FROM_LEARNING: task is the word, answers are its native translations.
            else:
                task_value = w.text
                task_language = word_lang
                translations_native = native_translations or translations
                right_answers_list = [t[1] for t in translations_native]
                right_answers_translations_data = [
                    {'id': tid, 'text': ttext, 'language': tlang}
                    for tid, ttext, tlang in translations_native
                ]
        elif cfg.exercise.slug == exercises_lookups.ASSOCIATE_EXERCISE_SLUG:
            imgs = getattr(w, 'image_associations', []) or []
            if imgs:
                img = random.choice(imgs)
                task_type = TaskTypesEnum.IMAGE
                # Convert relative image path to full URL, matching DRF behavior
                task_value = get_full_media_url(img.image_url) or img.image_url
                image_width = img.width
                image_height = img.height
                task_related_id = str(img.id)
            right_answers_list = [w.text]
        elif cfg.exercise.slug == exercises_lookups.WITH_LETTER_EXERCISE_SLUG:
            task_value = w.text[0] if w.text else ''
            task_type = TaskTypesEnum.TEXT
            task_language = getattr(w.language, 'isocode', None)
            right_answers_list = [w.text] if w.text else []
            # include words list with language for convenience (DRF uses WordStandartCardSerializer)
            right_answers_words_data = [
                {
                    'id': str(word.id),
                    'text': word.text,
                    'language': getattr(word.language, 'isocode', None),
                }
                for word in task_words
                if word.text and task_value and word.text.startswith(task_value)
            ]
        elif cfg.exercise.slug == exercises_lookups.DEFINITIONS_TIME_EXERCISE_SLUG:
            defs = _pick_word_definitions(w)
            if definitions_mode == 'WBDEF':
                # user must type a matching definition text
                task_value = w.text
                right_answers_list = [d[1] for d in defs]
                right_answers_definitions_data = [
                    {'id': did, 'text': dtext, 'language': dlang}
                    for did, dtext, dlang in defs
                ]
            else:
                # user must type the word given a definition
                if defs:
                    did, dtext, dlang = random.choice(defs)
                    task_value = dtext
                    right_answers_list = [w.text]
                    right_answers_words_data = [
                        {
                            'id': str(w.id),
                            'text': w.text,
                            'language': getattr(w.language, 'isocode', None),
                        }
                    ]

        # DRF invariant: for every task, at least one of the right_answers_*_data
        # collections must be non‑empty for non‑variants modes. If relationship‑
        # based lookups above produced no data but we still have textual answers,
        # use them as a fallback structured payload so the frontend can render.
        if (
            not right_answers_words_data
            and not right_answers_translations_data
            and not right_answers_definitions_data
        ):
            if cfg.exercise.slug == exercises_lookups.TRANSLATOR_EXERCISE_SLUG:
                right_answers_translations_data = [
                    {'id': '', 'text': txt, 'language': task_language}
                    for txt in right_answers_list
                ]
            elif cfg.exercise.slug == exercises_lookups.DEFINITIONS_TIME_EXERCISE_SLUG:
                right_answers_definitions_data = [
                    {'id': '', 'text': txt, 'language': task_language}
                    for txt in right_answers_list
                ]
            else:
                right_answers_words_data = [
                    {'id': '', 'text': txt, 'language': task_language}
                    for txt in right_answers_list
                ]

        # variants
        if input_mode in (
            ExercisesInputModeEnum.VARIANTS,
            ExercisesInputModeEnum.VARIANTS_MAX,
        ):
            pool = set()
            pool.update(right_answers_list)
            # add similars and other words as distractors
            pool.update(similars_texts)
            while len(pool) < max(4, len(right_answers_list) + 1):
                pool.add(random.choice(task_words).text)
            variants = _shuffle_words(list(pool))

        # compute task-specific hints_available mirroring DRF get_task_hints_available
        hints_available_ids: list[str] = []
        config_hints: Iterable[Hint] = getattr(cfg, 'hints_available', []) or []
        task_related_ids: list[str] = [task_related_id] if task_related_id else []
        for hint in config_hints:
            # If hint is not tied to mode or word customization, always allow
            if not (
                hint.variants_mode
                or hint.free_input_mode
                or hint.word_customization_content_needed
            ):
                hints_available_ids.append(str(hint.id))
                continue

            # Check mode compatibility
            mode_ok = False
            if hint.variants_mode and input_mode in (
                ExercisesInputModeEnum.VARIANTS,
                ExercisesInputModeEnum.VARIANTS_MAX,
            ):
                mode_ok = True
            if hint.free_input_mode and input_mode in (
                ExercisesInputModeEnum.FREE_INPUT,
                ExercisesInputModeEnum.FREE_INPUT_MAX,
            ):
                mode_ok = True
            if not mode_ok:
                continue

            # If no word customization required, allow for this mode
            if not hint.word_customization_content_needed:
                hints_available_ids.append(str(hint.id))
                continue

            attr_name = hint.word_customization_content_needed
            # DRF logic branches by translations_mode; for our purposes we apply
            # a simplified but equivalent check using prebuilt right_answers_*_data.
            if translations_mode == 'L':
                # FROM_LEARNING: rely on the main word having the attribute
                if getattr(w, attr_name, None):
                    hints_available_ids.append(str(hint.id))
            else:
                # FROM_NATIVE or default: look for the attribute on any right answer,
                # excluding the current task_related_id when applicable.
                candidate_ids: list[str] = [
                    wd['id']
                    for wd in right_answers_words_data
                    if wd.get('id') and wd.get('id') not in task_related_ids
                ]
                if candidate_ids:
                    hints_available_ids.append(str(hint.id))

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
            'right_answers_list': right_answers_list,
            'right_answers_words_data': right_answers_words_data,
            'right_answers_translations_data': right_answers_translations_data,
            'right_answers_definitions_data': right_answers_definitions_data,
            # Per-task hints_available, DRF-aligned: list of hint IDs as strings
            'hints_available': hints_available_ids,
            'image_width': image_width,
            'image_height': image_height,
            'similars': similars_texts,
        }
        tasks.append(task)

    random.shuffle(tasks)
    return tasks


async def verdict_for_answer(
    answer: str,
    answers_list: list[str],
    task: dict[str, Any],
    word=None,
) -> str:
    """
    Port of DRF verdict logic (get_verdict) to keep behavior identical.
    """
    right_answers_list: list[str] = task.get('right_answers_list', [])
    right_answers_translations_data: list[dict[str, Any]] = task.get(
        'right_answers_translations_data', []
    )
    right_answers_words_data: list[dict[str, Any]] = task.get(
        'right_answers_words_data', []
    )
    right_answers_definitions_data: list[dict[str, Any]] = task.get(
        'right_answers_definitions_data', []
    )

    verdict = ExercisesAnswerEnum.INCORRECT

    if word and (
        answer.lower() == getattr(word, 'text', '').lower()
        or (
            answers_list
            and answers_list[0].lower() == getattr(word, 'text', '').lower()
        )
        and len(answers_list) == 1
    ):
        verdict = ExercisesAnswerEnum.CORRECT
    else:
        right_answers = (
            [ra.lower() for ra in right_answers_list]
            + [ra['text'].lower() for ra in right_answers_translations_data]
            + [ra['text'].lower() for ra in right_answers_words_data]
            + [ra['text'].lower() for ra in right_answers_definitions_data]
        )

        if answer.lower() in right_answers:
            verdict = ExercisesAnswerEnum.CORRECT
        elif (
            answers_list
            and len(answers_list) == len(right_answers)
            and all(a.lower() in right_answers for a in answers_list)
        ):
            verdict = ExercisesAnswerEnum.CORRECT
        elif answers_list and any(a.lower() in right_answers for a in answers_list):
            verdict = ExercisesAnswerEnum.SEMI_CORRECT

    return verdict


async def create_session_history(
    session: AsyncSession,
    cfg: ExerciseConfiguration,
    words_count: int,
    tasks_count: int,
    user_id: UUID,
) -> ExerciseSessionHistory:
    # Explicitly initialize counters to avoid NOT NULL violations even if
    # legacy DB schema lacks defaults.
    hist = ExerciseSessionHistory(
        user_id=user_id,
        exercise_id=cfg.exercise_id,
        words_amount=words_count,
        tasks_amount=tasks_count,
        corrects_amount=0,
        incorrects_amount=0,
        semi_corrects_amount=0,
        complete_time=None,
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
            # Ensure input_mode is always stored to satisfy NOT NULL constraint
            input_mode=task.get('input_mode') or ExercisesInputModeEnum.FREE_INPUT,
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

    # right answers relationships: attach via plain association inserts to avoid
    # triggering async lazy-load on relationship attributes
    Word = VOCAB_MODELS['Word']
    if task.get('right_answers_list'):
        words = (
            (
                await session.execute(
                    select(Word.id).where(
                        Word.text.in_(task['right_answers_list']),
                        Word.author_id == hist.user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        if words:
            from apps.exercises.models import (
                exercises_exercisesessiontaskshistory_right_answers_words,
            )

            await session.execute(
                exercises_exercisesessiontaskshistory_right_answers_words.insert(),
                [
                    {
                        'exercisesessiontaskshistory_id': obj.id,
                        'word_id': wid,
                    }
                    for wid in words
                ],
            )
    if task.get('right_answers_translations_data'):
        tr_ids = [
            UUID(t['id'])
            for t in task['right_answers_translations_data']
            if t.get('id')
        ]
        if tr_ids:
            from apps.exercises.models import (
                exercises_exercisesessiontaskshistory_right_answers_translations,
            )

            await session.execute(
                exercises_exercisesessiontaskshistory_right_answers_translations.insert(),
                [
                    {
                        'exercisesessiontaskshistory_id': obj.id,
                        'translation_id': tid,
                    }
                    for tid in tr_ids
                ],
            )
    if task.get('right_answers_definitions_data'):
        def_ids = [
            UUID(d['id']) for d in task['right_answers_definitions_data'] if d.get('id')
        ]
        if def_ids:
            from apps.exercises.models import (
                exercises_exercisesessiontaskshistory_right_answers_definitions,
            )

            await session.execute(
                exercises_exercisesessiontaskshistory_right_answers_definitions.insert(),
                [
                    {
                        'exercisesessiontaskshistory_id': obj.id,
                        'definition_id': did,
                    }
                    for did in def_ids
                ],
            )
    # hints used: insert into M2M table directly to avoid async lazy-load
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
        if hints:
            from apps.exercises.models import (
                exercises_exercisesessiontaskshistory_hints_used,
            )

            await session.execute(
                exercises_exercisesessiontaskshistory_hints_used.insert(),
                [
                    {
                        'exercisesessiontaskshistory_id': obj.id,
                        'hint_id': h.id,
                    }
                    for h in hints
                ],
            )

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
    # Our task dict uses `right_answers_list` and the *_data collections,
    # so derive a unified list of answer texts from those instead of a
    # non‑existent `right_answers` key.
    right_answers: list[str] = task.get('right_answers_list') or []
    if not right_answers:
        right_answers = [
            *[w.get('text', '') for w in task.get('right_answers_words_data', [])],
            *[
                t.get('text', '')
                for t in task.get('right_answers_translations_data', [])
            ],
            *[
                d.get('text', '')
                for d in task.get('right_answers_definitions_data', [])
            ],
        ]
    variants = task.get('variants', []) or []
    similars = task.get('similars', []) or []
    hint_payload: dict[str, Any] = {'hint_code': hint_code}

    # First-letter hint (DRF: FIRST_LETTER_HINT_CODE)
    if hint_code == hints_codes.FIRST_LETTER_HINT_CODE and right_answers:
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

    # Letters-amount hint (DRF: LETTERS_AMOUNT_HINT_CODE)
    if hint_code == hints_codes.LETTERS_AMOUNT_HINT_CODE and right_answers:
        hint_payload['hint_data'] = {'letters_amount': len(right_answers[0])}
        hint_payload['last_hint'] = True
        return hint_payload

    # Remove-incorrect hint (DRF: REMOVE_INCORRECT_HINT_CODE / REMOVE_HALF_HINT_CODE)
    if hint_code == hints_codes.REMOVE_INCORRECT_HINT_CODE and variants:
        incorrect = [v for v in variants if v not in right_answers]
        if incorrect:
            victim = random.choice(incorrect)
            hint_payload['hint_data'] = {'incorrect_index': variants.index(victim)}
        else:
            hint_payload['hint_data'] = {}
        hint_payload['last_hint'] = True
        return hint_payload

    # Synonym hint (DRF: SYNONYM_HINT_CODE)
    if hint_code == hints_codes.SYNONYM_HINT_CODE and similars:
        hint_payload['hint_data'] = {'synonym': random.choice(similars)}
        hint_payload['last_hint'] = len(similars) <= 1
        return hint_payload

    # Association/image hint (DRF: ASSOCIATION_HINT_CODE)
    if (
        hint_code == hints_codes.ASSOCIATION_HINT_CODE
        and task.get('task_type') == TaskTypesEnum.IMAGE
    ):
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
