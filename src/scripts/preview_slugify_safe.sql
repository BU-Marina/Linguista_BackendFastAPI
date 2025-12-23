WITH affected AS (
  SELECT id, username
  FROM users_user
  WHERE (slug IS NULL OR slug = '')
  ORDER BY id
  LIMIT 200
)
SELECT
  id,
  username,
  CASE
    WHEN username IS NULL OR trim(username) = '' OR username ~ '^\s*<.*>\s*$' OR lower(username) LIKE '%django.db.models.%' OR username ILIKE '%field%' THEN
      'user-' || id::text
    ELSE
      trim(both '-' FROM regexp_replace(regexp_replace(lower(COALESCE(username, '')), '[^a-z0-9]+', '-', 'g'), '-{2,}', '-', 'g'))
  END AS candidate_base
FROM affected;