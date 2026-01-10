"""Users api SQL builders."""

from sqlalchemy import select, func, distinct, literal, case, and_, or_, exists
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import Select

# - `build_users_page_stmt` (jsonb_agg по странице)
# - `build_users_list_base_stmt` (User поля + where)
# - `build_user_profile_stmt` (retrieve by slug)


def build_users_page_stmt(
    *,
    base_filtered_stmt,  # select(User.*fields...) with WHERE+ORDER+LIMIT applied
    request_user_id,
    models,
):
    User = models["User"]  # noqa: F841 - kept for clarity of models mapping
    UserSettings = models["UserSettings"]  # noqa: F841
    Language = models["Language"]
    City = models["City"]
    Interest = models["Interest"]
    UserLearningLanguage = models["UserLearningLanguage"]
    UserNativeLanguage = models["UserNativeLanguage"]
    Subscription = models["Subscription"]
    Friend = models["Friend"]
    FriendRequest = models["FriendRequest"]
    users_user_cities = models["users_user_cities"]  # Table
    users_user_interests = models["users_user_interests"]  # Table

    page = base_filtered_stmt.cte("page_users")
    empty_jsonb_array = func.cast(literal("[]"), JSONB)

    # cities
    cities_sq = (
        select(
            users_user_cities.c.user_id.label("user_id"),
            func.coalesce(
                func.jsonb_agg(distinct(City.name)).filter(City.name.isnot(None)),
                empty_jsonb_array,
            ).label("cities"),
        )
        .select_from(users_user_cities)
        .join(City, City.id == users_user_cities.c.city_id)
        .where(users_user_cities.c.user_id.in_(select(page.c.id)))
        .group_by(users_user_cities.c.user_id)
        .subquery()
    )

    # interests
    interests_sq = (
        select(
            users_user_interests.c.user_id.label("user_id"),
            func.coalesce(
                func.jsonb_agg(distinct(Interest.name)).filter(
                    Interest.name.isnot(None)
                ),
                empty_jsonb_array,
            ).label("interests"),
        )
        .select_from(users_user_interests)
        .join(Interest, Interest.id == users_user_interests.c.interest_id)
        .where(users_user_interests.c.user_id.in_(select(page.c.id)))
        .group_by(users_user_interests.c.user_id)
        .subquery()
    )

    # native_languages: через ORM UserNativeLanguage
    native_langs_sq = (
        select(
            UserNativeLanguage.user_id.label("user_id"),
            func.coalesce(
                func.jsonb_agg(distinct(Language.isocode)).filter(
                    Language.isocode.isnot(None)
                ),
                empty_jsonb_array,
            ).label("native_languages"),
        )
        .select_from(UserNativeLanguage)
        .join(Language, Language.id == UserNativeLanguage.language_id)
        .where(UserNativeLanguage.user_id.in_(select(page.c.id)))
        .group_by(UserNativeLanguage.user_id)
        .subquery()
    )

    # learning languages (detail)
    ll_obj = func.jsonb_build_object(
        "isocode",
        Language.isocode,
        "level",
        UserLearningLanguage.level,
        "is_confirmed",
        UserLearningLanguage.is_confirmed,
        "is_taught",
        UserLearningLanguage.is_taught,
    )
    learning_langs_sq = (
        select(
            UserLearningLanguage.user_id.label("user_id"),
            func.coalesce(func.jsonb_agg(distinct(ll_obj)), empty_jsonb_array).label(
                "learning_languages"
            ),
            func.coalesce(
                func.jsonb_agg(distinct(ll_obj)).filter(
                    UserLearningLanguage.is_taught.is_(True)
                ),
                empty_jsonb_array,
            ).label("taught_languages"),
        )
        .select_from(UserLearningLanguage)
        .join(Language, Language.id == UserLearningLanguage.language_id)
        .where(UserLearningLanguage.user_id.in_(select(page.c.id)))
        .group_by(UserLearningLanguage.user_id)
        .subquery()
    )

    # subscribers_count
    subscribers_sq = (
        select(
            Subscription.user_id.label("user_id"),
            func.count(Subscription.subscriber_id).label("subscribers_count"),
        )
        .where(Subscription.user_id.in_(select(page.c.id)))
        .group_by(Subscription.user_id)
        .subquery()
    )

    # is_subscribed
    if request_user_id:
        is_subscribed_sq = (
            select(
                Subscription.user_id.label("user_id"),
                literal(True).label("is_subscribed"),
            )
            .where(
                and_(
                    Subscription.subscriber_id == request_user_id,
                    Subscription.user_id.in_(select(page.c.id)),
                )
            )
            .subquery()
        )
        is_friend_expr = exists().where(
            or_(
                and_(Friend.user_id == request_user_id, Friend.friend_id == page.c.id),
                and_(Friend.friend_id == request_user_id, Friend.user_id == page.c.id),
            )
        )
        friend_request_sent_expr = exists().where(
            and_(
                FriendRequest.requester_id == request_user_id,
                FriendRequest.target_id == page.c.id,
            )
        )
    else:
        is_subscribed_sq = None
        is_friend_expr = literal(False)
        friend_request_sent_expr = literal(False)

    # overlap percents
    if request_user_id:
        req_langs_count_sq = (
            select(func.count(distinct(UserLearningLanguage.language_id)))
            .where(UserLearningLanguage.user_id == request_user_id)
            .scalar_subquery()
        )
        req_interests_count_sq = (
            select(func.count(distinct(users_user_interests.c.interest_id)))
            .where(users_user_interests.c.user_id == request_user_id)
            .scalar_subquery()
        )

        req_lang_ids = (
            select(UserLearningLanguage.language_id)
            .where(UserLearningLanguage.user_id == request_user_id)
            .subquery()
        )
        req_interest_ids = (
            select(users_user_interests.c.interest_id)
            .where(users_user_interests.c.user_id == request_user_id)
            .subquery()
        )

        overlap_langs_sq = (
            select(
                UserLearningLanguage.user_id.label("user_id"),
                func.count(distinct(UserLearningLanguage.language_id)).label(
                    "overlap_langs_count"
                ),
            )
            .where(
                and_(
                    UserLearningLanguage.user_id.in_(select(page.c.id)),
                    UserLearningLanguage.language_id.in_(
                        select(req_lang_ids.c.language_id)
                    ),
                )
            )
            .group_by(UserLearningLanguage.user_id)
            .subquery()
        )

        overlap_interests_sq = (
            select(
                users_user_interests.c.user_id.label("user_id"),
                func.count(distinct(users_user_interests.c.interest_id)).label(
                    "overlap_interests_count"
                ),
            )
            .where(
                and_(
                    users_user_interests.c.user_id.in_(select(page.c.id)),
                    users_user_interests.c.interest_id.in_(
                        select(req_interest_ids.c.interest_id)
                    ),
                )
            )
            .group_by(users_user_interests.c.user_id)
            .subquery()
        )

        learning_languages_overlap_percent = case(
            (
                req_langs_count_sq > 0,
                (
                    func.coalesce(overlap_langs_sq.c.overlap_langs_count, 0)
                    / func.nullif(req_langs_count_sq, 0)
                )
                * 100.0,
            ),
            else_=literal(0.0),
        ).label("learning_languages_overlap_percent")

        interests_overlap_percent = case(
            (
                req_interests_count_sq > 0,
                (
                    func.coalesce(overlap_interests_sq.c.overlap_interests_count, 0)
                    / func.nullif(req_interests_count_sq, 0)
                )
                * 100.0,
            ),
            else_=literal(0.0),
        ).label("interests_overlap_percent")
    else:
        learning_languages_overlap_percent = literal(0.0).label(
            "learning_languages_overlap_percent"
        )
        interests_overlap_percent = literal(0.0).label("interests_overlap_percent")

    stmt = (
        select(
            page.c.id,
            page.c.slug,
            page.c.username,
            page.c.first_name,
            page.c.profile_image_url,
            page.c.profile_header_image_url,
            page.c.profile_description,
            page.c.is_teacher,
            page.c.teaching_goal,
            page.c.created,
            page.c.last_login,
            func.coalesce(interests_sq.c.interests, empty_jsonb_array).label(
                "interests"
            ),
            func.coalesce(cities_sq.c.cities, empty_jsonb_array).label("cities"),
            func.coalesce(native_langs_sq.c.native_languages, empty_jsonb_array).label(
                "native_languages"
            ),
            func.coalesce(
                learning_langs_sq.c.learning_languages, empty_jsonb_array
            ).label("learning_languages"),
            func.coalesce(
                learning_langs_sq.c.taught_languages, empty_jsonb_array
            ).label("taught_languages"),
            func.coalesce(subscribers_sq.c.subscribers_count, 0).label(
                "subscribers_count"
            ),
            (
                func.coalesce(is_subscribed_sq.c.is_subscribed, literal(False))
                if is_subscribed_sq is not None
                else literal(False)
            ).label("is_subscribed"),
            (is_friend_expr if request_user_id else literal(False)).label("is_friend"),
            (friend_request_sent_expr if request_user_id else literal(False)).label(
                "is_friend_request_sent"
            ),
            learning_languages_overlap_percent,
            interests_overlap_percent,
        )
        .select_from(page)
        .outerjoin(interests_sq, interests_sq.c.user_id == page.c.id)
        .outerjoin(cities_sq, cities_sq.c.user_id == page.c.id)
        .outerjoin(native_langs_sq, native_langs_sq.c.user_id == page.c.id)
        .outerjoin(learning_langs_sq, learning_langs_sq.c.user_id == page.c.id)
        .outerjoin(subscribers_sq, subscribers_sq.c.user_id == page.c.id)
    )
    if is_subscribed_sq is not None:
        stmt = stmt.outerjoin(is_subscribed_sq, is_subscribed_sq.c.user_id == page.c.id)

    return stmt


def build_users_list_base_stmt(
    *,
    User,
    UserSettings,
    params,
) -> Select:
    """
    Строит базовый SELECT для users_list: только поля User + базовые WHERE.
    Фильтры по interests/cities/languages и т.п. сюда НЕ кладём — это отдельным слоем
    (apply_search/apply_users_filters), чтобы было проще тестировать и поддерживать.

    Ожидает, что params имеет как минимум:
      - search (str|None)  -> сюда не применяем (это apply_search)
      - ordering (str|None)-> сюда не применяем (apply_ordering)
      - offset (int), limit (int) -> сюда не применяем (пагинация тоже снаружи)
    """

    # ВАЖНО: только реальные поля User
    stmt = (
        select(
            User.id,
            User.slug,
            User.username,
            User.first_name,
            User.profile_image_url,
            User.profile_header_image_url,
            User.profile_description,
            User.is_teacher,
            User.teaching_goal,
            User.created,
            User.last_login,
        )
        .select_from(User)
        .outerjoin(UserSettings, UserSettings.user_id == User.id)
        # скрытые профили: private_account=True не показываем
        .where(func.coalesce(UserSettings.private_account, literal(False)).is_(False))
    )

    # ---- Базовые ограничения "кого вообще показываем" ----

    # 1) не показываем удалённых / заблокированных
    if hasattr(User, "is_deleted"):
        stmt = stmt.where(User.is_deleted.is_(False))
    if hasattr(User, "is_blocked"):
        stmt = stmt.where(User.is_blocked.is_(False))

    # 2) показываем только активных
    if hasattr(User, "is_active"):
        stmt = stmt.where(User.is_active.is_(True))
    elif hasattr(User, "active"):
        stmt = stmt.where(User.active.is_(True))

    # 4) "пустой slug" (редко, но бывает в миграциях)
    if hasattr(User, "slug"):
        stmt = stmt.where(User.slug.isnot(None)).where(User.slug != "")

    return stmt


def build_user_profile_stmt(
    *,
    slug: str,
    request_user_id,
    User,
    UserSettings,
    City,
    Interest,
    Language,
    UserLearningLanguage,
    UserNativeLanguage,
    Subscription,
    Friend,
    FriendRequest,
    users_user_cities,  # Table
    users_user_interests,  # Table
) -> Select:
    """
    Профиль другого пользователя по slug.
    Возвращает row (mappings) со всеми полями, нужными UserReadOut.

    Очистка Subscription new_* делается в service (celery), не тут.
    """

    empty_jsonb_array = func.cast(literal("[]"), JSONB)

    # cities
    cities_sq = (
        select(
            users_user_cities.c.user_id.label("user_id"),
            func.coalesce(
                func.jsonb_agg(distinct(City.name)).filter(City.name.isnot(None)),
                empty_jsonb_array,
            ).label("cities"),
        )
        .select_from(users_user_cities)
        .join(City, City.id == users_user_cities.c.city_id)
        .group_by(users_user_cities.c.user_id)
        .subquery()
    )

    # interests
    interests_sq = (
        select(
            users_user_interests.c.user_id.label("user_id"),
            func.coalesce(
                func.jsonb_agg(distinct(Interest.name)).filter(
                    Interest.name.isnot(None)
                ),
                empty_jsonb_array,
            ).label("interests"),
        )
        .select_from(users_user_interests)
        .join(Interest, Interest.id == users_user_interests.c.interest_id)
        .group_by(users_user_interests.c.user_id)
        .subquery()
    )

    # native_languages (через ORM UserNativeLanguage)
    native_langs_sq = (
        select(
            UserNativeLanguage.user_id.label("user_id"),
            func.coalesce(
                func.jsonb_agg(distinct(Language.isocode)).filter(
                    Language.isocode.isnot(None)
                ),
                empty_jsonb_array,
            ).label("native_languages"),
        )
        .select_from(UserNativeLanguage)
        .join(Language, Language.id == UserNativeLanguage.language_id)
        .group_by(UserNativeLanguage.user_id)
        .subquery()
    )

    # learning_languages detail + taught subset
    ll_obj = func.jsonb_build_object(
        "isocode",
        Language.isocode,
        "level",
        UserLearningLanguage.level,
        "is_confirmed",
        UserLearningLanguage.is_confirmed,
        "is_taught",
        UserLearningLanguage.is_taught,
    )

    learning_langs_sq = (
        select(
            UserLearningLanguage.user_id.label("user_id"),
            func.coalesce(func.jsonb_agg(distinct(ll_obj)), empty_jsonb_array).label(
                "learning_languages"
            ),
            func.coalesce(
                func.jsonb_agg(distinct(ll_obj)).filter(
                    UserLearningLanguage.is_taught.is_(True)
                ),
                empty_jsonb_array,
            ).label("taught_languages"),
        )
        .select_from(UserLearningLanguage)
        .join(Language, Language.id == UserLearningLanguage.language_id)
        .group_by(UserLearningLanguage.user_id)
        .subquery()
    )

    # subscribers_count
    subscribers_sq = (
        select(
            Subscription.user_id.label("user_id"),
            func.count(Subscription.subscriber_id).label("subscribers_count"),
        )
        .group_by(Subscription.user_id)
        .subquery()
    )

    # subscription detail for viewer (is_subscribed, enable_notifications, new_*, updated_*)
    if request_user_id:
        viewer_sub_sq = (
            select(
                Subscription.user_id.label("user_id"),
                literal(True).label("is_subscribed"),
                Subscription.enable_notifications.label("enable_notifications"),
                Subscription.new_words.label("new_words"),
                Subscription.updated_words.label("updated_words"),
                Subscription.new_collections.label("new_collections"),
            )
            .where(Subscription.subscriber_id == request_user_id)
            .subquery()
        )
        is_friend_expr = exists().where(
            or_(
                and_(Friend.user_id == request_user_id, Friend.friend_id == User.id),
                and_(Friend.friend_id == request_user_id, Friend.user_id == User.id),
            )
        )
        friend_request_sent_expr = exists().where(
            and_(
                FriendRequest.requester_id == request_user_id,
                FriendRequest.target_id == User.id,
            )
        )
    else:
        viewer_sub_sq = None
        is_friend_expr = literal(False)
        friend_request_sent_expr = literal(False)

    stmt = (
        select(
            User.id.label("id"),
            User.slug.label("slug"),
            User.username.label("username"),
            User.first_name.label("first_name"),
            User.profile_image_url.label("profile_image_url"),
            User.profile_header_image_url.label("profile_header_image_url"),
            User.profile_description.label("profile_description"),
            User.is_teacher.label("is_teacher"),
            User.teaching_goal.label("teaching_goal"),
            User.image_height.label("image_height"),
            User.image_width.label("image_width"),
            func.coalesce(interests_sq.c.interests, empty_jsonb_array).label(
                "interests"
            ),
            func.coalesce(cities_sq.c.cities, empty_jsonb_array).label("cities"),
            func.coalesce(native_langs_sq.c.native_languages, empty_jsonb_array).label(
                "native_languages"
            ),
            func.coalesce(
                learning_langs_sq.c.learning_languages, empty_jsonb_array
            ).label("learning_languages"),
            func.coalesce(
                learning_langs_sq.c.taught_languages, empty_jsonb_array
            ).label("taught_languages"),
            func.coalesce(subscribers_sq.c.subscribers_count, 0).label(
                "subscribers_count"
            ),
            func.coalesce(UserSettings.allow_subscriptions, literal(False)).label(
                "allow_subscriptions"
            ),
            func.coalesce(UserSettings.allow_buddy_search, literal(False)).label(
                "allow_buddy_search"
            ),
            # viewer subscription fields
            (
                func.coalesce(viewer_sub_sq.c.is_subscribed, literal(False))
                if viewer_sub_sq is not None
                else literal(False)
            ).label("is_subscribed"),
            (
                func.coalesce(viewer_sub_sq.c.enable_notifications, literal(False))
                if viewer_sub_sq is not None
                else literal(False)
            ).label("enable_notifications"),
            (
                viewer_sub_sq.c.new_words
                if viewer_sub_sq is not None
                else literal(None)
            ).label("new_words"),
            (
                viewer_sub_sq.c.updated_words
                if viewer_sub_sq is not None
                else literal(None)
            ).label("updated_words"),
            (
                viewer_sub_sq.c.new_collections
                if viewer_sub_sq is not None
                else literal(None)
            ).label("new_collections"),
            (is_friend_expr if request_user_id else literal(False)).label("is_friend"),
            (friend_request_sent_expr if request_user_id else literal(False)).label(
                "is_friend_request_sent"
            ),
            # TODO later:
            literal(None).label("collections_count"),
        )
        .select_from(User)
        .outerjoin(UserSettings, UserSettings.user_id == User.id)
        .outerjoin(interests_sq, interests_sq.c.user_id == User.id)
        .outerjoin(cities_sq, cities_sq.c.user_id == User.id)
        .outerjoin(native_langs_sq, native_langs_sq.c.user_id == User.id)
        .outerjoin(learning_langs_sq, learning_langs_sq.c.user_id == User.id)
        .outerjoin(subscribers_sq, subscribers_sq.c.user_id == User.id)
        .where(User.slug == slug)
        # скрытые профили не отдаём:
        .where(func.coalesce(UserSettings.private_account, literal(False)).is_(False))
    )

    if viewer_sub_sq is not None:
        stmt = stmt.outerjoin(viewer_sub_sq, viewer_sub_sq.c.user_id == User.id)

    # базовые ограничения
    if hasattr(User, "is_deleted"):
        stmt = stmt.where(User.is_deleted.is_(False))
    if hasattr(User, "is_blocked"):
        stmt = stmt.where(User.is_blocked.is_(False))
    if hasattr(User, "is_active"):
        stmt = stmt.where(User.is_active.is_(True))
    elif hasattr(User, "active"):
        stmt = stmt.where(User.active.is_(True))

    return stmt
