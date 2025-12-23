-- slugify_users_safe.sql
-- Безопасно заполняет пустые slug (slug IS NULL OR slug = '') на основе username,
-- не будет записывать repr-подобные значения вида '<...>' или содержащие 'django.db.models'/'Field'.
-- Настрой max_len при необходимости.

DO $$
DECLARE
  rec RECORD;
  base TEXT;
  candidate TEXT;
  i INT;
  has_unaccent BOOLEAN;
  max_len INT := 64;  -- поменяй при необходимости
BEGIN
  -- Проверка наличия unaccent
  SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'unaccent') INTO has_unaccent;

  FOR rec IN
    SELECT id, username
    FROM users_user
    WHERE (slug IS NULL OR slug = '')
      -- Не будем брать username NULL/пустой; но обработаем такие записи ниже (fallback)
    ORDER BY id
  LOOP
    -- Если username пустой или выглядит опасно (repr-like или содержит django Field), использовать fallback
    IF rec.username IS NULL OR trim(rec.username) = ''
       OR rec.username ~ '^\s*<.*>\s*$'                       -- <...>
       OR lower(rec.username) LIKE '%django.db.models.%'     -- содержит django model repr
       OR rec.username ILIKE '%field%'                       -- содержит Field (чтобы ловить 'CharField' и т.п.)
    THEN
      base := 'user-' || rec.id::text;
    ELSE
      IF has_unaccent THEN
        base := unaccent(rec.username);
      ELSE
        base := rec.username;
      END IF;
      base := lower(base);
      base := regexp_replace(base, '[^a-z0-9]+', '-', 'g');   -- оставить только a-z0-9 и '-'
      base := regexp_replace(base, '-{2,}', '-', 'g');        -- сжать повторные '-'
      base := trim(both '-' FROM base);
      IF base = '' THEN
        base := 'user-' || rec.id::text;
      END IF;
    END IF;

    -- Обрезка базовой части по max_len с учётом возможного суффикса
    IF char_length(base) > max_len THEN
      base := left(base, max_len);
      base := regexp_replace(base, '-$','', 'g');
      IF base = '' THEN
        base := 'user-' || rec.id::text;
      END IF;
    END IF;

    candidate := base;
    i := 1;

    -- Обеспечить уникальность: пока такой slug существует у другой записи, добавлять суффикс
    WHILE EXISTS (
      SELECT 1 FROM users_user u
      WHERE u.slug = candidate
        AND u.id <> rec.id
    ) LOOP
      -- формируем кандидат с суффиксом, обрезая базу при необходимости
      IF char_length(base) + 1 + char_length(i::text) > max_len THEN
        candidate := left(base, max_len - 1 - char_length(i::text)) || '-' || i::text;
      ELSE
        candidate := base || '-' || i::text;
      END IF;
      i := i + 1;
    END LOOP;

    -- обновляем только если slug действительно пуст (дополнительная защита от гонок)
    UPDATE users_user
    SET slug = candidate
    WHERE id = rec.id
      AND (slug IS NULL OR slug = '');
  END LOOP;
END
$$;