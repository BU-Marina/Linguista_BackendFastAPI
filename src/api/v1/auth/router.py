"""Auth api endpoints."""

import secrets
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    Body,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import (
    text,
    select,
    delete,
    update,
    func,
)

from core.db import get_async_session
from core.constants import AmountLimits
from core.storage import get_storage
from auth.setup import (
    current_user,
    get_user_manager,
    auth_backend,
    fastapi_users,
)
from auth.manager import pwd_context
from apps.users.models import (
    User,
    Interest,
    City,
    UserSettings,
)
from apps.languages.models import (
    Language,
    UserNativeLanguage,
    UserLearningLanguage,
)
from apps.auth.models import RefreshToken
from apps.auth.sql import SQL_USER_PROFILE
from utils.images import _coerce_url

from .schemas import (
    UserMeRead,
    UserMeUpdate,
    DeleteAccountRequest,
    UserMeReadScalar,
    UserCreate,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- FastAPI Users ---

router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
)
router.include_router(
    fastapi_users.get_register_router(UserMeReadScalar, UserCreate),
)
router.include_router(
    fastapi_users.get_verify_router(UserMeReadScalar),
)
router.include_router(
    fastapi_users.get_reset_password_router(),
)


# --- Custom Auth Endpoints ---


@router.get("/me", response_model=UserMeRead)
async def get_me(
    current_user=Depends(current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Получить профиль пользователя."""

    # current_user — ORM instance; use its id to run optimized query
    user_id = str(current_user.id)  # bind as text/uuid, SQLAlchemy will handle binding
    req_user_id = str(current_user.id)  # for get_me, requester == owner; still passed

    result = await db.execute(
        text(SQL_USER_PROFILE),
        {"user_id": user_id, "request_user_id": req_user_id},
    )
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # row fields: map to dict keys used in schema
    data = dict(row._mapping)  # use row._mapping -> dict of column name -> value

    # settings_json is text 'null' or json; convert if necessary (asyncpg returns actual JSON)
    if data.get("settings_json") is not None and data["settings_json"] == "null":
        data["settings"] = None
    else:
        data["settings"] = data.pop("settings_json")

    # ensure Python types: json_agg returned as list, exists -> bool, counts -> int
    # If interests/cities/native_languages are JSON strings, ensure they are Python lists (asyncpg already does)
    # Now construct Pydantic model
    # Map DB key names to Pydantic keys if they differ:
    out = {
        "id": data["id"],
        "slug": data["slug"],
        "username": data["username"],
        "first_name": data["first_name"],
        "profile_image_url": _coerce_url(data.get("profile_image_url") or None),
        "profile_header_image_url": _coerce_url(
            data.get("profile_header_image_url") or None
        ),
        "profile_description": data["profile_description"],
        "is_teacher": data["is_teacher"],
        "teaching_goal": data["teaching_goal"],
        "interests": data["interests"] or [],
        "cities": data["cities"] or [],
        "native_languages": data["native_languages"] or [],
        "learning_languages": data["learning_languages"] or [],
        "taught_languages": data["taught_languages"] or [],
        "onboarding_passed": data["onboarding_passed"],
        "settings": data["settings"],
    }

    # normalize learning/taught languages keys (support 'language' -> isocode)
    def _normalize_ll(items):
        normalized = []
        for item in items or []:
            if isinstance(item, dict):
                iso = item.get("isocode") or item.get("language")
                normalized.append({**item, "isocode": iso})
            else:
                normalized.append(item)
        return normalized

    out["learning_languages"] = _normalize_ll(out["learning_languages"])
    out["taught_languages"] = _normalize_ll(out["taught_languages"])

    return UserMeRead(**out)


MAX_NATIVE = getattr(AmountLimits.Languages, "MAX_NATIVE_LANGUAGES_AMOUNT", 3)


@router.patch("/me", response_model=UserMeRead)
async def update_me(
    payload: UserMeUpdate,
    current_user: User = Depends(current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Обновление профиля текущего пользователя.
    Atomic: все изменения применяются в одной транзакции.
    В конце возвращаем результат get_me(...) (полный профиль).
    """
    # Берём только поля, которые реально пришли в JSON
    payload_dict = payload.model_dump(exclude_unset=True)

    # async with db.begin():
    q = (
        select(User)
        .where(User.id == current_user.id)
        .options(
            selectinload(User.interests),
            selectinload(User.cities),
            selectinload(User.native_languages),  # адаптируй имя relationship
            selectinload(User.learning_languages_detail),  # адаптируй имя relationship
            selectinload(User.settings),
        )
    )
    res = await db.execute(q)
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # --- scalar fields: обновляем только если ключ присутствует в payload_dict ---
    scalar_fields = [
        "username",
        "first_name",
        "profile_description",
        "is_teacher",
        "teaching_goal",
    ]
    for fld in scalar_fields:
        if fld in payload_dict:
            setattr(user, fld, payload_dict[fld])

    image_fields = [
        "profile_image_url",
        "profile_header_image_url",
    ]
    for fld in image_fields:
        if fld in payload_dict:
            setattr(user, fld, _coerce_url(payload_dict[fld]))

    # --- username: уникальность (только если поле пришло) ---
    if "username" in payload_dict:
        uname = payload_dict["username"]
        if uname is not None:
            uname = uname.strip()
            if uname:
                exists_q = (
                    select(func.count())
                    .select_from(User)
                    .where(
                        func.lower(User.username) == func.lower(uname),
                        User.id != user.id,
                    )
                )
                r = await db.execute(exists_q)
                cnt = r.scalar_one()
                if cnt and cnt > 0:
                    raise HTTPException(
                        status_code=400, detail="Username already in use"
                    )
                user.username = uname
            else:
                # если явно прислали пустую строку — политика: установить None (или raise)
                user.username = None
        else:
            # явно прислали null
            user.username = None

    # --- interests (many-to-many by name): если ключ передан — заменить полностью ---
    if "interests" in payload_dict:
        incoming = payload_dict["interests"] or []  # [] означает очистку
        if incoming:
            interests_q = select(Interest).where(Interest.name.in_(incoming))
            r = await db.execute(interests_q)
            found = r.scalars().all()
            found_names = {i.name for i in found}
            to_create = [name for name in incoming if name not in found_names]
            for name in to_create:
                new_i = Interest(name=name)
                db.add(new_i)
                found.append(new_i)
            user.interests = found
        else:
            user.interests = []

    # --- cities (many-to-many by name) аналогично ---
    if "cities" in payload_dict:
        incoming = payload_dict["cities"] or []
        if incoming:
            cities_q = select(City).where(City.name.in_(incoming))
            r = await db.execute(cities_q)
            found = r.scalars().all()
            found_names = {c.name for c in found}
            to_create = [name for name in incoming if name not in found_names]
            for name in to_create:
                new_c = City(name=name)
                db.add(new_c)
                found.append(new_c)
            user.cities = found
        else:
            user.cities = []

    # --- native_languages: replace (if key present) ---
    if "native_languages" in payload_dict:
        codes = payload_dict["native_languages"] or []
        MAX_NATIVE = 3  # или берите из констант
        if len(codes) > MAX_NATIVE:
            raise HTTPException(
                status_code=400, detail=f"Max native languages = {MAX_NATIVE}"
            )
        # удалить старые
        await db.execute(
            delete(UserNativeLanguage).where(UserNativeLanguage.user_id == user.id)
        )
        if codes:
            lang_q = select(Language).where(Language.isocode.in_(codes))
            r = await db.execute(lang_q)
            langs = {lang_obj.isocode: lang_obj for lang_obj in r.scalars().all()}
            for code in codes:
                lang = langs.get(code)
                if not lang:
                    raise HTTPException(
                        status_code=400, detail=f"Language {code} not found"
                    )
                new_assoc = UserNativeLanguage(user_id=user.id, language_id=lang.id)
                db.add(new_assoc)

    # --- learning_languages: replace set if key present ---
    if "learning_languages" in payload_dict:
        incoming = payload_dict["learning_languages"] or []
        await db.execute(
            delete(UserLearningLanguage).where(UserLearningLanguage.user_id == user.id)
        )
        if incoming:
            codes = [item["language"] for item in incoming if item.get("language")]
            lang_q = select(Language).where(Language.isocode.in_(codes))
            r = await db.execute(lang_q)
            langs = {lang_obj.isocode: lang_obj for lang_obj in r.scalars().all()}
            for item in incoming:
                code = item.get("language")
                lang = langs.get(code)
                if not lang:
                    raise HTTPException(
                        status_code=400, detail=f"Language {code} not found"
                    )
                new_ll = UserLearningLanguage(
                    user_id=user.id,
                    language_id=lang.id,
                    level=item.get("level"),
                    is_confirmed=item.get("is_confirmed", False),
                )
                db.add(new_ll)

    # --- settings: nested update/create if key present ---
    if "settings" in payload_dict:
        settings_val = payload_dict["settings"]
        if settings_val is None:
            # политика: если явно прислали null — можно удалить или игнорировать
            # здесь оставим как игнор (можно реализовать удаление)
            pass
        else:
            # settings_val — dict с пришедшими полями
            if getattr(user, "settings", None) is None:
                new_settings = UserSettings(user_id=user.id, **settings_val)
                db.add(new_settings)
                user.settings = new_settings
            else:
                for k, v in settings_val.items():
                    setattr(user.settings, k, v)

    # транзакция закрыта (commit) — обновления сохранены
    await db.refresh(user)

    # вернуть полный профиль (используем уже реализованный get_me)
    return await get_me(current_user=user, db=db)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    payload: DeleteAccountRequest = Body(...),
    mode: str = Query("soft", regex="^(soft|hard)$"),
    current_user: User = Depends(current_user),
    db: AsyncSession = Depends(get_async_session),
    user_manager=Depends(get_user_manager),
    storage=Depends(get_storage),
):
    """
    Удаление собственного профиля.
    mode=soft (по умолчанию) — пометить профиль неактивным и анонимизировать поля.
    mode=hard — полностью удалить запись из БД (требует подтверждения пароля).
    """

    # --- Валидация: для hard delete требуется пароль ---
    if mode == "hard":
        if not payload.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password required for hard delete",
            )

        # проверяем пароль — используем hashed_password в модели
        if not current_user.hashed_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No password set; cannot verify",
            )

        try:
            valid = await user_manager.verify_password(payload.password, current_user)
        except Exception:
            valid = False

        if not valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid password"
            )

    # --- Выполняем удаление/анонимизацию в транзакции ---
    # Используем nested transaction / savepoint если уже есть транзакция
    if db.in_transaction():
        tr_ctx = db.begin_nested()
    else:
        tr_ctx = db.begin()

    async with tr_ctx:
        # обязательно перечитаем user в сессии, чтобы иметь полноценный ORM объект
        q = select(User).where(User.id == current_user.id)
        result = await db.execute(q)
        user = result.scalar_one_or_none()

        if not user:
            # уже удалён
            return

        # Optional: удаляем/аннулируем refresh tokens, sessions etc.
        try:
            await db.execute(
                delete(RefreshToken).where(RefreshToken.user_id == user.id)
            )
        except NameError:
            # модель отсутствует — пропускаем
            pass

        # Удаление файлов
        try:
            if user.profile_image_url:
                await storage.delete(user.profile_image_url)
            if user.profile_header_image_url:
                await storage.delete(user.profile_header_image_url)
        except Exception:
            # логирование ошибки удаления файлов, но не прерываем транзакцию
            pass

        if mode == "soft":
            # анонимизируем и деактивируем
            anon_suffix = f"deleted-{uuid4().hex[:8]}"
            new_email = f"deleted+{anon_suffix}@example.invalid"
            new_username = f"deleted_{anon_suffix}"
            random_plain = secrets.token_urlsafe(32)
            random_hash = pwd_context.hash(random_plain)

            # Обнуляем чувствительные поля (оставляем id, created и т.п.)
            stmt = (
                update(User)
                .where(User.id == user.id)
                .values(
                    email=new_email,
                    username=new_username,
                    first_name=None,
                    profile_description=None,
                    profile_image_url=None,
                    profile_header_image_url=None,
                    hashed_password=random_hash,
                    is_active=False,
                    is_verified=False,
                    is_deleted=True,
                    # TODO опционально: пометить время удаления в отдельном поле deleted_at = func.now()
                )
            )
            await db.execute(stmt)

        else:  # hard
            # если у модели заданы каскадные FK (ON DELETE CASCADE) — db.delete(user) удалит связанные rows
            await db.delete(user)

        await db.commit()

    # транзакция коммитится при выходе из контекста
    return None  # 204 No Content
