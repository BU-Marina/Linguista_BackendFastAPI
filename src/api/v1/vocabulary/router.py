"""Vocabulary api endpoints (simplified)."""

from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user

from .schemas import (
    WordIn,
    WordReadOut,
    PageOut,
    MultipleWordsIn,
    MultipleWordsCreateOut,
    RelatedWordsOut,
    TagOut,
    TypeOut,
)
from .params import (
    build_words_list_params,
)
from .services import (
    words_list_service,
    word_create_service,
    word_retrieve_service,
    word_update_service,
    word_delete_service,
    multiple_words_create_service,
    word_favorite_toggle_service,
    tags_list_service,
    types_list_service,
    synonyms_list_service,
    synonyms_add_service,
    synonyms_remove_service,
    antonyms_list_service,
    antonyms_add_service,
    antonyms_remove_service,
    similars_list_service,
    similars_add_service,
    similars_remove_service,
)

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("/words", response_model=PageOut)
async def words_list(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    favorite_only: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        languages=languages,
        tags=tags,
        types=types,
        favorite_only=favorite_only,
    )
    return await words_list_service(session=session, user_id=user.id, params=params)


@router.post("/words", response_model=WordReadOut)
async def word_create(
    payload: WordIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await word_create_service(session=session, user_id=user.id, payload=payload)


@router.post("/multiple-create", response_model=MultipleWordsCreateOut)
async def words_multiple_create(
    payload: MultipleWordsIn,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        languages=languages,
        tags=tags,
        types=types,
    )
    return await multiple_words_create_service(
        session=session,
        user_id=user.id,
        payload=payload,
        params=params,
    )


@router.get("/words/{slug}", response_model=WordReadOut)
async def word_retrieve(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await word_retrieve_service(session=session, user_id=user.id, slug=slug)


@router.patch("/words/{slug}", response_model=WordReadOut)
async def word_update(
    slug: str,
    payload: WordIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await word_update_service(
        session=session, user_id=user.id, slug=slug, payload=payload
    )


@router.delete("/words/{slug}", status_code=204)
async def word_delete(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await word_delete_service(session=session, user_id=user.id, slug=slug)


@router.post("/words/{slug}/favorite", response_model=WordReadOut)
async def word_favorite_toggle(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await word_favorite_toggle_service(
        session=session, user_id=user.id, slug=slug
    )


# Tags & Types


@router.get("/tags", response_model=list[TagOut])
async def tags_list(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await tags_list_service(session=session, user_id=user.id)


@router.get("/types", response_model=list[TypeOut])
async def types_list(
    session: AsyncSession = Depends(get_async_session),
):
    return await types_list_service(session=session)


# Synonyms / Antonyms / Similars


def _slug_body(word_slugs: list[str] = Body(..., embed=True)) -> list[str]:
    return word_slugs


@router.get("/words/{slug}/synonyms", response_model=RelatedWordsOut)
async def word_synonyms(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await synonyms_list_service(session=session, user_id=user.id, slug=slug)


@router.post("/words/{slug}/synonyms", response_model=RelatedWordsOut)
async def word_synonyms_add(
    slug: str,
    word_slugs: list[str] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await synonyms_add_service(
        session=session, user_id=user.id, slug=slug, target_slugs=word_slugs
    )


@router.post("/words/{slug}/synonyms/remove", response_model=RelatedWordsOut)
async def word_synonyms_remove(
    slug: str,
    word_slugs: list[str] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await synonyms_remove_service(
        session=session, user_id=user.id, slug=slug, target_slugs=word_slugs
    )


@router.get("/words/{slug}/antonyms", response_model=RelatedWordsOut)
async def word_antonyms(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await antonyms_list_service(session=session, user_id=user.id, slug=slug)


@router.post("/words/{slug}/antonyms", response_model=RelatedWordsOut)
async def word_antonyms_add(
    slug: str,
    word_slugs: list[str] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await antonyms_add_service(
        session=session, user_id=user.id, slug=slug, target_slugs=word_slugs
    )


@router.post("/words/{slug}/antonyms/remove", response_model=RelatedWordsOut)
async def word_antonyms_remove(
    slug: str,
    word_slugs: list[str] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await antonyms_remove_service(
        session=session, user_id=user.id, slug=slug, target_slugs=word_slugs
    )


@router.get("/words/{slug}/similars", response_model=RelatedWordsOut)
async def word_similars(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await similars_list_service(session=session, user_id=user.id, slug=slug)


@router.post("/words/{slug}/similars", response_model=RelatedWordsOut)
async def word_similars_add(
    slug: str,
    word_slugs: list[str] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await similars_add_service(
        session=session, user_id=user.id, slug=slug, target_slugs=word_slugs
    )


@router.post("/words/{slug}/similars/remove", response_model=RelatedWordsOut)
async def word_similars_remove(
    slug: str,
    word_slugs: list[str] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await similars_remove_service(
        session=session, user_id=user.id, slug=slug, target_slugs=word_slugs
    )
