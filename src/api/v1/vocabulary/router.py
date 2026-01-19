"""Vocabulary api endpoints (simplified)."""

from fastapi import APIRouter, Depends, Query, Body
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user

from .schemas import (
    WordIn,
    WordReadOut,
    SynonymReadOut,
    PageOut,
    MultipleWordsIn,
    MultipleWordsCreateOut,
    RelatedWordsOut,
    TagOut,
    TypeOut,
    WordResolveOut,
    WordCollectionsIn,
    WordsIdsIn,
    WordAccessLevelUpdateIn,
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
    word_resolve_slug_service,
    synonym_retrieve_service,
    word_add_to_collections_service,
    words_data_to_update_service,
    words_set_access_level_service,
    word_allow_comments_switch_service,
    words_random_service,
)

router = APIRouter(prefix='/vocabulary', tags=['vocabulary'])


@router.get('/words', response_model=PageOut)
async def words_list(
    # Pagination
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=500),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    # Basic filters
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    activity_status: str | None = Query(None),
    is_problematic: bool | None = Query(None),
    first_letter: str | None = Query(None),
    last_letter: str | None = Query(None),
    have_associations: bool | None = Query(None),
    read_access: str | None = Query(None),
    add_access: str | None = Query(None),
    borrowed: bool | None = Query(None),
    # Include filters
    words: str | None = Query(None),
    collections: str | None = Query(None),
    translations: str | None = Query(None),
    images: str | None = Query(None),
    definitions: str | None = Query(None),
    examples: str | None = Query(None),
    # Exclude filters
    words_exclude: str | None = Query(None),
    collections_exclude: str | None = Query(None),
    translations_exclude: str | None = Query(None),
    images_exclude: str | None = Query(None),
    definitions_exclude: str | None = Query(None),
    examples_exclude: str | None = Query(None),
    suggested_words_exclude: str | None = Query(None),
    # Count filters
    translations_count: int | None = Query(None),
    translations_count_gt: int | None = Query(None, alias='translations_count__gt'),
    translations_count_lt: int | None = Query(None, alias='translations_count__lt'),
    examples_count: int | None = Query(None),
    examples_count_gt: int | None = Query(None, alias='examples_count__gt'),
    examples_count_lt: int | None = Query(None, alias='examples_count__lt'),
    definitions_count: int | None = Query(None),
    definitions_count_gt: int | None = Query(None, alias='definitions_count__gt'),
    definitions_count_lt: int | None = Query(None, alias='definitions_count__lt'),
    images_count: int | None = Query(None, alias='image_associations_count'),
    images_count_gt: int | None = Query(None, alias='image_associations_count__gt'),
    images_count_lt: int | None = Query(None, alias='image_associations_count__lt'),
    synonyms_count: int | None = Query(None),
    synonyms_count_gt: int | None = Query(None, alias='synonyms_count__gt'),
    synonyms_count_lt: int | None = Query(None, alias='synonyms_count__lt'),
    # Favorite
    favorite_only: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        # Basic filters
        languages=languages,
        tags=tags,
        types=types,
        activity_status=activity_status,
        is_problematic=is_problematic,
        first_letter=first_letter,
        last_letter=last_letter,
        have_associations=have_associations,
        read_access=read_access,
        add_access=add_access,
        borrowed=borrowed,
        # Include filters
        words=words,
        collections=collections,
        translations=translations,
        images=images,
        definitions=definitions,
        examples=examples,
        # Exclude filters
        words_exclude=words_exclude,
        collections_exclude=collections_exclude,
        translations_exclude=translations_exclude,
        images_exclude=images_exclude,
        definitions_exclude=definitions_exclude,
        examples_exclude=examples_exclude,
        suggested_words_exclude=suggested_words_exclude,
        # Count filters
        translations_count=translations_count,
        translations_count_gt=translations_count_gt,
        translations_count_lt=translations_count_lt,
        examples_count=examples_count,
        examples_count_gt=examples_count_gt,
        examples_count_lt=examples_count_lt,
        definitions_count=definitions_count,
        definitions_count_gt=definitions_count_gt,
        definitions_count_lt=definitions_count_lt,
        images_count=images_count,
        images_count_gt=images_count_gt,
        images_count_lt=images_count_lt,
        synonyms_count=synonyms_count,
        synonyms_count_gt=synonyms_count_gt,
        synonyms_count_lt=synonyms_count_lt,
        # Favorite
        favorite_only=favorite_only,
    )
    return await words_list_service(session=session, user_id=user.id, params=params)


@router.post('/words', response_model=WordReadOut)
async def word_create(
    payload: WordIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await word_create_service(session=session, user_id=user.id, payload=payload)


@router.post('/multiple-create', response_model=MultipleWordsCreateOut)
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


@router.get('/words/slug/{slug}', response_model=WordResolveOut)
async def word_resolve_slug(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await word_resolve_slug_service(session=session, user_id=user.id, slug=slug)


@router.get('/words/{word_id}', response_model=WordReadOut)
async def word_retrieve(
    word_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await word_retrieve_service(
        session=session, user_id=user.id, word_id=word_id
    )


@router.get('/words/synonyms/{synonym_id}', response_model=SynonymReadOut)
async def synonym_retrieve(
    synonym_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await synonym_retrieve_service(
        session=session, user_id=user.id, synonym_id=synonym_id
    )


@router.patch('/words/{word_id}', response_model=WordReadOut)
async def word_update(
    word_id: UUID,
    payload: WordIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await word_update_service(
        session=session, user_id=user.id, word_id=word_id, payload=payload
    )


@router.post('/words/{word_id}/collections', response_model=WordReadOut)
async def word_add_to_collections(
    word_id: UUID,
    payload: WordCollectionsIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await word_add_to_collections_service(
        session=session, user_id=user.id, word_id=word_id, payload=payload
    )


@router.delete('/words/{word_id}', status_code=204)
async def word_delete(
    word_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await word_delete_service(session=session, user_id=user.id, word_id=word_id)


@router.post('/words/{word_id}/favorite', response_model=WordReadOut)
async def word_favorite_toggle(
    word_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await word_favorite_toggle_service(
        session=session, user_id=user.id, word_id=word_id
    )


@router.post('/words/{word_id}/allow-comments-switch', response_model=WordReadOut)
async def word_allow_comments_switch(
    word_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await word_allow_comments_switch_service(
        session=session, user_id=user.id, word_id=word_id
    )


# Tags & Types


@router.get('/tags', response_model=list[TagOut])
async def tags_list(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await tags_list_service(session=session, user_id=user.id)


@router.get('/types', response_model=list[TypeOut])
async def types_list(
    session: AsyncSession = Depends(get_async_session),
):
    return await types_list_service(session=session)


@router.get('/words/random', response_model=PageOut)
async def words_random(
    limit: int = Query(1, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await words_random_service(session=session, user_id=user.id, limit=limit)


@router.post('/words/data-to-update', response_model=list[WordReadOut])
async def words_data_to_update(
    payload: WordsIdsIn,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await words_data_to_update_service(
        session=session, user_id=user.id, payload=payload
    )


@router.patch('/words/set-access-level', status_code=201)
async def words_set_access_level(
    payload: list[WordAccessLevelUpdateIn],
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    await words_set_access_level_service(
        session=session, user_id=user.id, updates=payload
    )
    return {'updated': len(payload)}


# Synonyms / Antonyms / Similars


def _slug_body(word_slugs: list[str] = Body(..., embed=True)) -> list[str]:
    return word_slugs


@router.get('/words/{word_id}/synonyms', response_model=RelatedWordsOut)
async def word_synonyms(
    word_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await synonyms_list_service(
        session=session, user_id=user.id, word_id=word_id
    )


@router.post('/words/{word_id}/synonyms', response_model=RelatedWordsOut)
async def word_synonyms_add(
    word_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await synonyms_add_service(
        session=session, user_id=user.id, word_id=word_id, target_ids=word_ids
    )


@router.post('/words/{word_id}/synonyms/remove', response_model=RelatedWordsOut)
async def word_synonyms_remove(
    word_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await synonyms_remove_service(
        session=session, user_id=user.id, word_id=word_id, target_ids=word_ids
    )


@router.get('/words/{word_id}/antonyms', response_model=RelatedWordsOut)
async def word_antonyms(
    word_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await antonyms_list_service(
        session=session, user_id=user.id, word_id=word_id
    )


@router.post('/words/{word_id}/antonyms', response_model=RelatedWordsOut)
async def word_antonyms_add(
    word_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await antonyms_add_service(
        session=session, user_id=user.id, word_id=word_id, target_ids=word_ids
    )


@router.post('/words/{word_id}/antonyms/remove', response_model=RelatedWordsOut)
async def word_antonyms_remove(
    word_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await antonyms_remove_service(
        session=session, user_id=user.id, word_id=word_id, target_ids=word_ids
    )


@router.get('/words/{word_id}/similars', response_model=RelatedWordsOut)
async def word_similars(
    word_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await similars_list_service(
        session=session, user_id=user.id, word_id=word_id
    )


@router.post('/words/{word_id}/similars', response_model=RelatedWordsOut)
async def word_similars_add(
    word_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await similars_add_service(
        session=session, user_id=user.id, word_id=word_id, target_ids=word_ids
    )


@router.post('/words/{word_id}/similars/remove', response_model=RelatedWordsOut)
async def word_similars_remove(
    word_id: UUID,
    word_ids: list[UUID] = Body(..., embed=True),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    return await similars_remove_service(
        session=session, user_id=user.id, word_id=word_id, target_ids=word_ids
    )
