"""Published resources endpoints."""

from fastapi import APIRouter, Depends, Query
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_async_session
from auth.setup import current_user, optional_current_user
from api.v1.vocabulary.params import (
    build_words_list_params,
    build_collections_list_params,
)
from .schemas import (
    WordsPageOut,
    WordsWithAuthorPageOut,
    WordReadOut,
    WordPublishedProfileOut,
    CollectionsPageOut,
    CollectionReadOut,
    CollectionPublishedProfileOut,
    TranslationsPageOut,
    TranslationOut,
    DefinitionsPageOut,
    DefinitionOut,
    ExamplesPageOut,
    ExampleOut,
    ImagesPageOut,
    ImageOut,
    SynonymsPageOut,
    CollectionCommentsPageOut,
    CollectionCommentOut,
    CollectionCommentIn,
    WordCommentsPageOut,
    WordCommentOut,
    WordCommentIn,
    CollectionSuggestedWordsPageOut,
)
from api.v1.vocabulary.schemas import WordsIdsIn, WordResolveOut
from api.v1.collections.schemas import CollectionResolveOut
from .services import (
    published_words_list_service,
    published_word_detail_service,
    published_word_resolve_slug_service,
    published_collections_list_service,
    published_collection_detail_service,
    published_collection_resolve_slug_service,
    _get_friend_ids,
    _get_subscription_author_ids,
    published_word_borrow_service,
    published_word_favorite_toggle_service,
    published_collection_borrow_service,
    published_collection_favorite_toggle_service,
    published_collection_words_service,
    published_translations_list_service,
    published_definitions_list_service,
    published_examples_list_service,
    published_images_list_service,
    published_translation_detail_service,
    published_definition_detail_service,
    published_example_detail_service,
    published_image_detail_service,
    published_synonyms_list_service,
    published_synonym_detail_service,
    published_collection_subscribe_service,
    published_collection_comments_list_service,
    published_collection_comment_create_service,
    published_collection_comment_patch_service,
    published_collection_comment_delete_service,
    published_collection_comment_like_service,
    published_collection_comment_dislike_service,
    published_collection_comment_author_like_service,
    published_collection_comment_answers_list_service,
    published_collection_comment_answer_create_service,
    published_word_comments_list_service,
    published_word_comment_create_service,
    published_word_comment_patch_service,
    published_word_comment_delete_service,
    published_word_comment_like_service,
    published_word_comment_dislike_service,
    published_word_comment_author_like_service,
    published_word_comment_answers_list_service,
    published_word_comment_answer_create_service,
    published_collection_suggested_words_list_service,
    published_collection_suggested_words_add_service,
    published_collection_suggested_words_accept_service,
    published_collection_suggested_words_reject_service,
    published_collection_suggested_words_destroy_service,
)
from core.celery.app import celery_app
from tasks.constants import UPDATE_WORD_VIEWS, UPDATE_COLLECTION_VIEWS

router = APIRouter(prefix='/published', tags=['published'])


@router.get('/translations', response_model=TranslationsPageOut)
async def published_translations(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    collections: str | None = Query(None),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    collection_ids = [UUID(c) for c in collections.split(',')] if collections else None
    return await published_translations_list_service(
        session=session,
        user_id=user.id if user else None,
        page=page,
        limit=limit,
        collections=collection_ids,
    )


@router.get('/definitions', response_model=DefinitionsPageOut)
async def published_definitions(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    collections: str | None = Query(None),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    collection_ids = [UUID(c) for c in collections.split(',')] if collections else None
    return await published_definitions_list_service(
        session=session,
        user_id=user.id if user else None,
        page=page,
        limit=limit,
        collections=collection_ids,
    )


@router.get('/examples', response_model=ExamplesPageOut)
async def published_examples(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    collections: str | None = Query(None),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    collection_ids = [UUID(c) for c in collections.split(',')] if collections else None
    return await published_examples_list_service(
        session=session,
        user_id=user.id if user else None,
        page=page,
        limit=limit,
        collections=collection_ids,
    )


@router.get('/images', response_model=ImagesPageOut)
async def published_images(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    collections: str | None = Query(None),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    collection_ids = [UUID(c) for c in collections.split(',')] if collections else None
    return await published_images_list_service(
        session=session,
        user_id=user.id if user else None,
        page=page,
        limit=limit,
        collections=collection_ids,
    )


# ------------------------
# Collection comments (ID-based)
# ------------------------


@router.get(
    '/collections/{collection_id}/comments',
    response_model=CollectionCommentsPageOut,
)
async def published_collection_comments(
    collection_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=200),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_comments_list_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
        page=page,
        limit=limit,
    )


@router.post(
    '/collections/{collection_id}/comments',
    response_model=CollectionCommentOut,
)
async def published_collection_comment_create(
    collection_id: UUID,
    payload: CollectionCommentIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_comment_create_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
        text=payload.text,
    )


@router.patch('/comments/{comment_id}', response_model=CollectionCommentOut)
async def published_collection_comment_patch(
    comment_id: UUID,
    payload: CollectionCommentIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_comment_patch_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
        text=payload.text,
    )


@router.delete('/comments/{comment_id}')
async def published_collection_comment_delete(
    comment_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    await published_collection_comment_delete_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
    )
    return {'status': 'ok'}


@router.post('/comments/{comment_id}/like', response_model=CollectionCommentOut)
async def published_collection_comment_like(
    comment_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_comment_like_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
    )


@router.post('/comments/{comment_id}/dislike', response_model=CollectionCommentOut)
async def published_collection_comment_dislike(
    comment_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_comment_dislike_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
    )


@router.post('/comments/{comment_id}/author-like', response_model=CollectionCommentOut)
async def published_collection_comment_author_like(
    comment_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_comment_author_like_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
    )


@router.get(
    '/comments/{comment_id}/answers',
    response_model=CollectionCommentsPageOut,
)
async def published_collection_comment_answers(
    comment_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=200),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_comment_answers_list_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
        page=page,
        limit=limit,
    )


# ------------------------
# Word comments (ID-based)
# ------------------------


@router.get(
    '/words/{word_id}/comments',
    response_model=WordCommentsPageOut,
)
async def published_word_comments(
    word_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=200),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_word_comments_list_service(
        session=session,
        user_id=user.id,
        word_id=word_id,
        page=page,
        limit=limit,
    )


@router.post(
    '/words/{word_id}/comments',
    response_model=WordCommentOut,
)
async def published_word_comment_create(
    word_id: UUID,
    payload: WordCommentIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_word_comment_create_service(
        session=session,
        user_id=user.id,
        word_id=word_id,
        text=payload.text,
    )


@router.patch('/word-comments/{comment_id}', response_model=WordCommentOut)
async def published_word_comment_patch(
    comment_id: UUID,
    payload: WordCommentIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_word_comment_patch_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
        text=payload.text,
    )


@router.delete('/word-comments/{comment_id}')
async def published_word_comment_delete(
    comment_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    await published_word_comment_delete_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
    )
    return {'status': 'ok'}


@router.post('/word-comments/{comment_id}/like', response_model=WordCommentOut)
async def published_word_comment_like(
    comment_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_word_comment_like_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
    )


@router.post('/word-comments/{comment_id}/dislike', response_model=WordCommentOut)
async def published_word_comment_dislike(
    comment_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_word_comment_dislike_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
    )


@router.post('/word-comments/{comment_id}/author-like', response_model=WordCommentOut)
async def published_word_comment_author_like(
    comment_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_word_comment_author_like_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
    )


@router.get(
    '/word-comments/{comment_id}/answers',
    response_model=WordCommentsPageOut,
)
async def published_word_comment_answers(
    comment_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=200),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_word_comment_answers_list_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
        page=page,
        limit=limit,
    )


@router.post(
    '/word-comments/{comment_id}/answers',
    response_model=WordCommentOut,
)
async def published_word_comment_answer_create(
    comment_id: UUID,
    payload: WordCommentIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_word_comment_answer_create_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
        text=payload.text,
    )


# ------------------------
# Collection suggested words (ID-based)
# ------------------------


@router.get(
    '/collections/{collection_id}/suggested-words',
    response_model=CollectionSuggestedWordsPageOut,
)
async def published_collection_suggested_words(
    collection_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=200),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_suggested_words_list_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
        page=page,
        limit=limit,
    )


@router.post(
    '/collections/{collection_id}/suggested-words',
    response_model=CollectionSuggestedWordsPageOut,
)
async def published_collection_suggested_words_add(
    collection_id: UUID,
    payload: WordsIdsIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_suggested_words_add_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
        word_ids=payload.word_ids,
    )


@router.delete(
    '/collections/{collection_id}/suggested-words',
    response_model=CollectionSuggestedWordsPageOut,
)
async def published_collection_suggested_words_destroy(
    collection_id: UUID,
    payload: WordsIdsIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_suggested_words_destroy_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
        word_ids=payload.word_ids,
    )


@router.post(
    '/collections/{collection_id}/suggested-words/accept',
    response_model=CollectionSuggestedWordsPageOut,
)
async def published_collection_suggested_words_accept(
    collection_id: UUID,
    payload: WordsIdsIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_suggested_words_accept_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
        word_ids=payload.word_ids,
    )


@router.post(
    '/collections/{collection_id}/suggested-words/reject',
    response_model=CollectionSuggestedWordsPageOut,
)
async def published_collection_suggested_words_reject(
    collection_id: UUID,
    payload: WordsIdsIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_suggested_words_reject_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
        word_ids=payload.word_ids,
    )


@router.post(
    '/comments/{comment_id}/answers',
    response_model=CollectionCommentOut,
)
async def published_collection_comment_answer_create(
    comment_id: UUID,
    payload: CollectionCommentIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_comment_answer_create_service(
        session=session,
        user_id=user.id,
        comment_id=comment_id,
        text=payload.text,
    )


@router.get('/translations/{translation_id}', response_model=TranslationOut)
async def published_translation_detail(
    translation_id: UUID,
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_translation_detail_service(
        session=session,
        user_id=user.id if user else None,
        translation_id=translation_id,
    )


@router.get('/definitions/{definition_id}', response_model=DefinitionOut)
async def published_definition_detail(
    definition_id: UUID,
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_definition_detail_service(
        session=session,
        user_id=user.id if user else None,
        definition_id=definition_id,
    )


@router.get('/examples/{example_id}', response_model=ExampleOut)
async def published_example_detail(
    example_id: UUID,
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_example_detail_service(
        session=session,
        user_id=user.id if user else None,
        example_id=example_id,
    )


@router.get('/images/{image_id}', response_model=ImageOut)
async def published_image_detail(
    image_id: UUID,
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_image_detail_service(
        session=session,
        user_id=user.id if user else None,
        image_id=image_id,
    )


@router.get('/synonyms', response_model=SynonymsPageOut)
async def published_synonyms(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_synonyms_list_service(
        session=session,
        user_id=user.id if user else None,
        page=page,
        limit=limit,
    )


@router.get('/synonyms/{word_id}', response_model=WordReadOut)
async def published_synonym_detail(
    word_id: UUID,
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_synonym_detail_service(
        session=session,
        user_id=user.id if user else None,
        word_id=word_id,
    )


@router.get('/words', response_model=WordsWithAuthorPageOut)
async def published_words(
    # Pagination
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    # Basic filters
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    first_letter: str | None = Query(None),
    last_letter: str | None = Query(None),
    have_associations: bool | None = Query(None),
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
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    collection_ids = [UUID(c) for c in collections.split(',')] if collections else None
    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        # Basic filters
        languages=languages,
        tags=tags,
        types=types,
        first_letter=first_letter,
        last_letter=last_letter,
        have_associations=have_associations,
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
    )
    params, total, results = await published_words_list_service(
        session=session,
        user_id=user.id if user else None,
        params=params,
        collections=collection_ids,
    )

    # Build pagination links
    from api.v1.utils.pagination import build_pagination_links

    next_link, previous_link = build_pagination_links(
        base_url='/published/words',
        page=params.page,
        limit=params.limit,
        total=total,
        query_params={
            'ordering': ordering,
            'search': search,
            'languages': languages,
            'tags': tags,
            'types': types,
            'first_letter': first_letter,
            'last_letter': last_letter,
            'have_associations': have_associations,
            'words': words,
            'collections': collections,
            'translations': translations,
            'images': images,
            'definitions': definitions,
            'examples': examples,
            'words_exclude': words_exclude,
            'collections_exclude': collections_exclude,
            'translations_exclude': translations_exclude,
            'images_exclude': images_exclude,
            'definitions_exclude': definitions_exclude,
            'examples_exclude': examples_exclude,
            'translations_count': translations_count,
            'translations_count__gt': translations_count_gt,
            'translations_count__lt': translations_count_lt,
            'examples_count': examples_count,
            'examples_count__gt': examples_count_gt,
            'examples_count__lt': examples_count_lt,
            'definitions_count': definitions_count,
            'definitions_count__gt': definitions_count_gt,
            'definitions_count__lt': definitions_count_lt,
            'image_associations_count': images_count,
            'image_associations_count__gt': images_count_gt,
            'image_associations_count__lt': images_count_lt,
        },
    )

    return WordsPageOut(
        page=params.page,
        limit=params.limit,
        count=total,
        results=results,
        next=next_link,
        previous=previous_link,
    )


@router.get('/words/slug/{slug}', response_model=WordResolveOut)
async def published_word_resolve_slug(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
):
    return await published_word_resolve_slug_service(session=session, slug=slug)


@router.get('/words/new', response_model=WordsWithAuthorPageOut)
async def published_words_new(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    search: str | None = Query(None),
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering='-created',
        search=search,
        languages=languages,
        tags=tags,
        types=types,
    )
    params, total, results = await published_words_list_service(
        session=session,
        user_id=user.id if user else None,
        params=params,
        ordering_override='-created',
    )
    return WordsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get('/words/friends', response_model=WordsWithAuthorPageOut)
async def published_words_friends(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    friend_ids = await _get_friend_ids(session, user.id)
    if not friend_ids:
        return WordsPageOut(page=page, limit=limit, count=0, results=[])

    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        languages=languages,
        tags=tags,
        types=types,
    )
    params, total, results = await published_words_list_service(
        session=session,
        user_id=user.id,
        params=params,
        author_ids=friend_ids,
    )
    return WordsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get('/words/subscriptions', response_model=WordsWithAuthorPageOut)
async def published_words_subscriptions(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    author_ids = await _get_subscription_author_ids(session, user.id)
    if not author_ids:
        return WordsPageOut(page=page, limit=limit, count=0, results=[])

    params = build_words_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        languages=languages,
        tags=tags,
        types=types,
    )
    params, total, results = await published_words_list_service(
        session=session,
        user_id=user.id,
        params=params,
        author_ids=author_ids,
    )
    return WordsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get('/words/favorites', response_model=WordsWithAuthorPageOut)
async def published_words_favorites(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    languages: str | None = Query(None),
    tags: str | None = Query(None),
    types: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
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
    params, total, results = await published_words_list_service(
        session=session,
        user_id=user.id,
        params=params,
        favorite_only=True,
    )
    return WordsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get('/words/{word_id}', response_model=WordPublishedProfileOut)
async def published_word_detail(
    word_id: UUID,
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    result = await published_word_detail_service(
        session=session,
        user_id=user.id if user else None,
        word_id=word_id,
    )
    if user:
        celery_app.send_task(UPDATE_WORD_VIEWS, args=[str(user.id), str(result.id)])
    return result


@router.post('/words/{word_id}/borrow', response_model=WordReadOut)
async def published_word_borrow(
    word_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_word_borrow_service(
        session=session,
        user_id=user.id,
        word_id=word_id,
    )


@router.post('/words/{word_id}/favorite', response_model=WordReadOut)
async def published_word_favorite(
    word_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_word_favorite_toggle_service(
        session=session,
        user_id=user.id,
        word_id=word_id,
    )


@router.get('/collections', response_model=CollectionsPageOut)
async def published_collections(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    tags: str | None = Query(None),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_collections_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        tags=tags,
    )
    params, total, results = await published_collections_list_service(
        session=session,
        user_id=user.id if user else None,
        params=params,
    )

    # Build pagination links
    from api.v1.utils.pagination import build_pagination_links

    next_link, previous_link = build_pagination_links(
        base_url='/published/collections',
        page=params.page,
        limit=params.limit,
        total=total,
        query_params={
            'ordering': ordering,
            'search': search,
            'tags': tags,
        },
    )

    return CollectionsPageOut(
        page=params.page,
        limit=params.limit,
        count=total,
        results=results,
        next=next_link,
        previous=previous_link,
    )


@router.get('/collections/slug/{slug}', response_model=CollectionResolveOut)
async def published_collection_resolve_slug(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_resolve_slug_service(session=session, slug=slug)


@router.get('/collections/new', response_model=CollectionsPageOut)
async def published_collections_new(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    search: str | None = Query(None),
    tags: str | None = Query(None),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_collections_list_params(
        page=page,
        limit=limit,
        ordering='-created',
        search=search,
        tags=tags,
    )
    params, total, results = await published_collections_list_service(
        session=session,
        user_id=user.id if user else None,
        params=params,
        ordering_override='-created',
    )
    return CollectionsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get('/collections/friends', response_model=CollectionsPageOut)
async def published_collections_friends(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    tags: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    friend_ids = await _get_friend_ids(session, user.id)
    if not friend_ids:
        return CollectionsPageOut(page=page, limit=limit, count=0, results=[])

    params = build_collections_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        tags=tags,
    )
    params, total, results = await published_collections_list_service(
        session=session,
        user_id=user.id,
        params=params,
        author_ids=friend_ids,
    )
    return CollectionsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get('/collections/subscriptions', response_model=CollectionsPageOut)
async def published_collections_subscriptions(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    tags: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    author_ids = await _get_subscription_author_ids(session, user.id)
    if not author_ids:
        return CollectionsPageOut(page=page, limit=limit, count=0, results=[])

    params = build_collections_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        tags=tags,
    )
    params, total, results = await published_collections_list_service(
        session=session,
        user_id=user.id,
        params=params,
        author_ids=author_ids,
    )
    return CollectionsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get('/collections/favorites', response_model=CollectionsPageOut)
async def published_collections_favorites(
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    ordering: str | None = Query(None),
    search: str | None = Query(None),
    tags: str | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    params = build_collections_list_params(
        page=page,
        limit=limit,
        ordering=ordering,
        search=search,
        tags=tags,
    )
    params, total, results = await published_collections_list_service(
        session=session,
        user_id=user.id,
        params=params,
        favorite_only=True,
    )
    return CollectionsPageOut(
        page=params.page, limit=params.limit, count=total, results=results
    )


@router.get(
    '/collections/{collection_id}', response_model=CollectionPublishedProfileOut
)
async def published_collection_detail(
    collection_id: UUID,
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    result = await published_collection_detail_service(
        session=session,
        user_id=user.id if user else None,
        collection_id=collection_id,
    )
    if user:
        celery_app.send_task(
            UPDATE_COLLECTION_VIEWS, args=[str(user.id), str(result.id)]
        )
    return result


@router.post('/collections/{collection_id}/borrow', response_model=CollectionReadOut)
async def published_collection_borrow(
    collection_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_borrow_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
    )


@router.post('/collections/{collection_id}/favorite', response_model=CollectionReadOut)
async def published_collection_favorite(
    collection_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_favorite_toggle_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
    )


@router.post('/collections/{collection_id}/subscribe', response_model=CollectionReadOut)
async def published_collection_subscribe(
    collection_id: UUID,
    enable_notifications: bool | None = Query(None),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_subscribe_service(
        session=session,
        user_id=user.id,
        collection_id=collection_id,
        enable_notifications=enable_notifications,
    )


@router.get('/collections/{collection_id}/words', response_model=WordsWithAuthorPageOut)
async def published_collection_words(
    collection_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(32, ge=1, le=100),
    user=Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await published_collection_words_service(
        session=session,
        user_id=user.id if user else None,
        collection_id=collection_id,
        page=page,
        limit=limit,
    )
