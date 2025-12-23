"""..."""

from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyUserDatabaseUsernameOrEmail(SQLAlchemyUserDatabase):
    """
    Подкласс SQLAlchemyUserDatabase, который при get_by_email(email_or_username)
    сначала ищет по email, а если не найден — пытает по username.
    Работает с AsyncSession (fastapi-users async setup).
    """

    async def get_by_email(self, email: str):
        # 1) стандартный поиск по email
        user = await super().get_by_email(email)
        if user:
            return user

        # 2) fallback: поиск по username
        # self.user_table может быть либо ORM model class либо Table; ниже мы пытаемся работать с ORM-столбцом.
        # Попробуем составить селект с учётом разных возможных типов self.user_table.
        async_session: AsyncSession = self.session  # fastapi-users обычно хранит sessionmaker/session тут
        try:
            # Если self.user_table — ORM mapped class:
            stmt = select(self.user_table).where(self.user_table.username == email)
            result = await async_session.execute(stmt)
            row = result.scalar_one_or_none()
            return row

        except Exception:
            # Если fail — попробуем через table.c.username (для Table objects)
            try:
                stmt = select(self.user_table).where(self.user_table.c.username == email)
                result = await async_session.execute(stmt)
                row = result.scalar_one_or_none()
                return row
            except Exception:
                return None
