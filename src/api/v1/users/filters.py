"""Users filters."""

from sqlalchemy import and_


def apply_users_filters(
    stmt, params, *, User, City, Interest, Language, UserLearningLanguage
):
    U = User

    if params.learning_languages:
        stmt = stmt.where(
            U.learning_languages.any(Language.isocode.in_(params.learning_languages))
        )

    if params.native_languages:
        stmt = stmt.where(
            U.native_languages.any(Language.isocode.in_(params.native_languages))
        )

    if params.taught_languages:
        stmt = stmt.where(
            U.learning_languages_detail.any(
                and_(
                    UserLearningLanguage.is_taught.is_(True),
                    UserLearningLanguage.language.has(
                        Language.isocode.in_(params.taught_languages)
                    ),
                )
            )
        )

    if params.levels:
        stmt = stmt.where(
            U.learning_languages_detail.any(
                UserLearningLanguage.level.in_(params.levels)
            )
        )

    if params.levels_exclude:
        stmt = stmt.where(
            ~U.learning_languages_detail.any(
                UserLearningLanguage.level.in_(params.levels_exclude)
            )
        )

    if params.is_confirmed is True:
        stmt = stmt.where(
            U.learning_languages_detail.any(UserLearningLanguage.is_confirmed.is_(True))
        )

    if params.interests:
        stmt = stmt.where(U.interests.any(Interest.name.in_(params.interests)))

    if params.interests_exclude:
        stmt = stmt.where(~U.interests.any(Interest.name.in_(params.interests_exclude)))

    if params.cities:
        stmt = stmt.where(U.cities.any(City.name.in_(params.cities)))

    return stmt
