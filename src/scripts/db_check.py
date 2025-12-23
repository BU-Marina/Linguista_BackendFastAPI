# scripts/db_check.py
import os

from sqlalchemy import create_engine, text

from dotenv import load_dotenv

load_dotenv()

# Берём URL из окружения
db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise SystemExit("Set DATABASE_URL env var first")

# Если у тебя async URL, конвертируем его для использования sync драйвера в миграциях/проверках
if "+asyncpg" in db_url:
    db_url = db_url.replace("+asyncpg", "+psycopg2")

engine = create_engine(db_url)
with engine.connect() as conn:
    r = conn.execute(text("SELECT 1"))
    print("DB responded:", r.scalar())
