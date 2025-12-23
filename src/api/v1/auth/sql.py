"""Sql requests to use in services."""

SQL_USER_PROFILE = """
SELECT
  u.id,
  u.slug,
  u.username,
  u.first_name,
  u.image,
  u.profile_header_image,
  u.profile_description,
  u.is_teacher,
  u.teaching_goal,
  u.onboarding_passed,
  -- interests: array of names
  COALESCE((
    SELECT json_agg(i.name ORDER BY i.name)
    FROM users_user_interests ui
    JOIN users_interest i ON ui.interest_id = i.id
    WHERE ui.user_id = u.id
  ), '[]') AS interests,
  -- cities
  COALESCE((
    SELECT json_agg(c.name ORDER BY c.name)
    FROM users_user_cities uc
    JOIN users_city c ON uc.city_id = c.id
    WHERE uc.user_id = u.id
  ), '[]') AS cities,
  -- native_languages isocode array
  COALESCE((
    SELECT json_agg(l.isocode ORDER BY l.isocode)
    FROM languages_usernativelanguage nl
    JOIN languages_language l ON nl.language_id = l.id
    WHERE nl.user_id = u.id
  ), '[]') AS native_languages,
  -- learning_languages: json array of {language, level, is_confirmed, words_count}
  COALESCE((
    SELECT json_agg(json_build_object(
      'language', lang.isocode,
      'level', ull.level,
      'is_confirmed', ull.is_confirmed,
      'words_count', (
         SELECT count(*) FROM vocabulary_word w WHERE w.author_id = u.id AND w.language_id = lang.id
      )
    ) ORDER BY lang.isocode)
    FROM languages_userlearninglanguage ull
    JOIN languages_language lang ON ull.language_id = lang.id
    WHERE ull.user_id = u.id
  ), '[]') AS learning_languages,
  -- taught_languages = filter learning_languages where is_taught true (if you store is_taught)
  COALESCE((
    SELECT json_agg(json_build_object(
      'language', lang.isocode,
      'level', ull.level,
      'is_confirmed', ull.is_confirmed,
      'words_count', (
         SELECT count(*) FROM vocabulary_word w WHERE w.author_id = u.id AND w.language_id = lang.id
      )
    ) ORDER BY lang.isocode)
    FROM languages_userlearninglanguage ull
    JOIN languages_language lang ON ull.language_id = lang.id
    WHERE ull.user_id = u.id AND ull.is_taught = true
  ), '[]') AS taught_languages,
  -- settings: if small, fetch as json object
  COALESCE((
    SELECT row_to_json(us.*) FROM users_usersettings us WHERE us.user_id = u.id
  ), 'null') AS settings_json
FROM users_user u
WHERE u.id = :user_id
LIMIT 1;
"""
