"""SQLAlchemy query builders for languages API."""

from sqlalchemy import select, func, literal, distinct, exists, or_
from sqlalchemy.sql import Select


def build_learning_languages_base_stmt(
    *, user_id, models, ordering: str | None, isocode: str | None = None
) -> Select:
    Language = models['Language']
    LanguageCoverImage = models['LanguageCoverImage']
    UserLearningLanguage = models['UserLearningLanguage']
    Word = models['Word']

    words_count = (
        select(func.count())
        .where(
            Word.author_id == user_id,
            Word.language_id == UserLearningLanguage.language_id,
        )
        .correlate(UserLearningLanguage)
        .scalar_subquery()
    )
    inactive_words_count = (
        select(func.count())
        .where(
            Word.author_id == user_id,
            Word.language_id == UserLearningLanguage.language_id,
            Word.activity_status == 'I',
        )
        .correlate(UserLearningLanguage)
        .scalar_subquery()
    )
    active_words_count = (
        select(func.count())
        .where(
            Word.author_id == user_id,
            Word.language_id == UserLearningLanguage.language_id,
            Word.activity_status == 'A',
        )
        .correlate(UserLearningLanguage)
        .scalar_subquery()
    )
    mastered_words_count = (
        select(func.count())
        .where(
            Word.author_id == user_id,
            Word.language_id == UserLearningLanguage.language_id,
            Word.activity_status == 'M',
        )
        .correlate(UserLearningLanguage)
        .scalar_subquery()
    )

    stmt = (
        select(
            UserLearningLanguage.id,
            UserLearningLanguage.slug,
            UserLearningLanguage.level,
            UserLearningLanguage.is_confirmed,
            UserLearningLanguage.is_taught,
            UserLearningLanguage.cover_id,
            Language.id.label('language_id'),
            Language.isocode,
            Language.name_local,
            Language.name_en,
            Language.name_ru,
            Language.country_ru,
            Language.country_en,
            Language.flag_icon,
            Language.learning_available,
            Language.interface_available,
            Language.sorting,
            LanguageCoverImage.image_url.label('cover_url'),
            words_count.label('words_count'),
            inactive_words_count.label('inactive_words_count'),
            active_words_count.label('active_words_count'),
            mastered_words_count.label('mastered_words_count'),
        )
        .select_from(UserLearningLanguage)
        .join(Language, Language.id == UserLearningLanguage.language_id)
        .outerjoin(
            LanguageCoverImage, LanguageCoverImage.id == UserLearningLanguage.cover_id
        )
        .where(UserLearningLanguage.user_id == user_id)
    )
    if isocode:
        stmt = stmt.where(Language.isocode == isocode)

    ordering_map = {
        '-words_count': words_count.desc(),
        'words_count': words_count,
        '-created': UserLearningLanguage.created.desc(),
        'created': UserLearningLanguage.created,
        '-sorting': Language.sorting.desc(),
        'sorting': Language.sorting,
        '-name': Language.name_local.desc(),
        'name': Language.name_local,
    }
    if ordering and ordering in ordering_map:
        stmt = stmt.order_by(ordering_map[ordering])
    else:
        stmt = stmt.order_by(
            words_count.desc(), UserLearningLanguage.created.desc(), Language.name_local
        )
    return stmt


def build_native_languages_stmt(*, user_id, models) -> Select:
    Language = models['Language']
    UserNativeLanguage = models['UserNativeLanguage']
    stmt = (
        select(
            UserNativeLanguage.id,
            Language.id.label('language_id'),
            Language.isocode,
            Language.name_local,
            Language.name_en,
            Language.name_ru,
            Language.country_ru,
            Language.country_en,
            Language.flag_icon,
            literal(True).label('is_native'),
        )
        .select_from(UserNativeLanguage)
        .join(Language, Language.id == UserNativeLanguage.language_id)
        .where(UserNativeLanguage.user_id == user_id)
        .order_by(Language.name_local)
    )
    return stmt


def build_all_languages_stmt(*, user_id, models) -> Select:
    Language = models['Language']
    UserLearningLanguage = models['UserLearningLanguage']
    UserNativeLanguage = models['UserNativeLanguage']
    Word = models['Word']

    words_count = (
        select(func.count(distinct(Word.id)))
        .where(Word.language_id == Language.id)
        .correlate(Language)
        .scalar_subquery()
    )

    learning_exists = exists().where(
        UserLearningLanguage.user_id == user_id,
        UserLearningLanguage.language_id == Language.id,
    )
    native_exists = exists().where(
        UserNativeLanguage.user_id == user_id,
        UserNativeLanguage.language_id == Language.id,
    )

    return (
        select(
            Language.id,
            Language.isocode,
            Language.name_local,
            Language.name_en,
            Language.name_ru,
            Language.country_ru,
            Language.country_en,
            Language.flag_icon,
            Language.learning_available,
            Language.interface_available,
            Language.sorting,
            words_count.label('words_count'),
            learning_exists.label('is_learning'),
            native_exists.label('is_native'),
        )
        .select_from(Language)
        .order_by(Language.sorting.desc(), Language.name_local)
    )


def build_learning_available_stmt(
    *, user_id, models, ordering: str | None, search: str | None
) -> Select:
    Language = models['Language']
    UserLearningLanguage = models['UserLearningLanguage']
    Word = models['Word']

    words_count = (
        select(func.count(distinct(Word.id)))
        .where(Word.language_id == Language.id)
        .correlate(Language)
        .scalar_subquery()
    )

    base = (
        select(
            Language.id,
            Language.isocode,
            Language.name_local,
            Language.name_en,
            Language.name_ru,
            Language.country_ru,
            Language.country_en,
            Language.flag_icon,
            Language.learning_available,
            Language.interface_available,
            Language.sorting,
            words_count.label('words_count'),
        )
        .select_from(Language)
        .where(Language.learning_available.is_(True))
    )

    if user_id:
        base = base.where(
            ~exists().where(
                UserLearningLanguage.user_id == user_id,
                UserLearningLanguage.language_id == Language.id,
            )
        )

    if search:
        pattern = f'%{search}%'
        base = base.where(
            or_(
                Language.name_local.ilike(pattern),
                Language.name_en.ilike(pattern),
                Language.name_ru.ilike(pattern),
            )
        )

    if ordering == '-words_count':
        base = base.order_by(
            words_count.desc(), Language.sorting.desc(), Language.name_local
        )
    elif ordering == 'words_count':
        base = base.order_by(words_count, Language.sorting.desc(), Language.name_local)
    elif ordering in ('sorting', '-sorting'):
        base = base.order_by(
            Language.sorting.desc() if ordering.startswith('-') else Language.sorting,
            Language.name_local,
        )
    else:
        base = base.order_by(Language.sorting.desc(), Language.name_local)

    return base


def build_cover_choices_stmt(*, user_id, isocode: str, models) -> Select:
    Language = models['Language']
    LanguageCoverImage = models['LanguageCoverImage']
    UserLearningLanguage = models['UserLearningLanguage']

    current_cover_sq = (
        select(UserLearningLanguage.cover_id)
        .where(
            UserLearningLanguage.user_id == user_id,
            UserLearningLanguage.language_id == Language.id,
        )
        .scalar_subquery()
    )

    return (
        select(
            LanguageCoverImage.id,
            LanguageCoverImage.image_url,
            LanguageCoverImage.default,
            (LanguageCoverImage.id == current_cover_sq).label('is_current_cover'),
        )
        .select_from(LanguageCoverImage)
        .join(Language, Language.id == LanguageCoverImage.language_id)
        .where(Language.isocode == isocode)
        .order_by(
            literal(True).desc(),
            LanguageCoverImage.default.desc(),
            LanguageCoverImage.created.desc(),
        )
    )


def build_collections_by_language_stmt(*, user_id, isocode: str, models) -> Select:
    Collection = models['Collection']
    WordsInCollections = models['WordsInCollections']
    Word = models['Word']
    Language = models['Language']

    collections_words_sq = (
        select(
            WordsInCollections.collection_id.label('collection_id'),
            func.count(distinct(WordsInCollections.word_id)).label('words_count'),
        )
        .select_from(WordsInCollections)
        .join(Word, Word.id == WordsInCollections.word_id)
        .join(Language, Language.id == Word.language_id)
        .where(Word.author_id == user_id, Language.isocode == isocode)
        .group_by(WordsInCollections.collection_id)
        .subquery()
    )

    return (
        select(
            Collection.id,
            Collection.slug,
            Collection.title,
            func.coalesce(collections_words_sq.c.words_count, 0).label('words_count'),
        )
        .select_from(Collection)
        .join(
            collections_words_sq, collections_words_sq.c.collection_id == Collection.id
        )
        .where(Collection.author_id == user_id)
        .order_by(Collection.created.desc(), Collection.title)
    )


def build_global_languages_stmt(
    *, interface_only: bool, search: str | None, ordering: str | None, models
) -> Select:
    Language = models['Language']
    Word = models['Word']

    # Use LEFT JOIN with GROUP BY for better performance instead of correlated subquery
    stmt = (
        select(
            Language.id,
            Language.isocode,
            Language.name_local,
            Language.name_en,
            Language.name_ru,
            Language.country_ru,
            Language.country_en,
            Language.flag_icon,
            Language.learning_available,
            Language.interface_available,
            Language.sorting,
            func.count(distinct(Word.id)).label('words_count'),
        )
        .select_from(Language)
        .outerjoin(Word, Word.language_id == Language.id)
        .group_by(
            Language.id,
            Language.isocode,
            Language.name_local,
            Language.name_en,
            Language.name_ru,
            Language.country_ru,
            Language.country_en,
            Language.flag_icon,
            Language.learning_available,
            Language.interface_available,
            Language.sorting,
        )
    )

    if interface_only:
        stmt = stmt.where(Language.interface_available.is_(True))
    if search:
        pattern = f'%{search}%'
        stmt = stmt.where(
            or_(
                Language.name_local.ilike(pattern),
                Language.name_en.ilike(pattern),
                Language.name_ru.ilike(pattern),
            )
        )

    if ordering == '-words_count':
        stmt = stmt.order_by(
            func.count(distinct(Word.id)).desc(),
            Language.sorting.desc(),
            Language.name_local,
        )
    elif ordering == 'words_count':
        stmt = stmt.order_by(
            func.count(distinct(Word.id)), Language.sorting.desc(), Language.name_local
        )
    else:
        stmt = stmt.order_by(Language.sorting.desc(), Language.name_local)

    return stmt
