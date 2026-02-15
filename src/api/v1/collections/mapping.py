"""Collections mapping helpers."""

from __future__ import annotations

from api.v1.vocabulary.mapping import map_word

from .schemas import CollectionShortOut, CollectionReadOut, AuthorShortOut


def map_collection(coll, include_words: bool = False, for_published: bool = False):
    """
    Map collection ORM object to response schema.

    Args:
        coll: Collection ORM object
        include_words: Whether to include full word list
        for_published: Whether this is for published API (includes author details)
    """
    words_count = getattr(coll, '_words_count', None)
    # Avoid triggering lazy-load in async context: only use in-memory state
    if words_count is None:
        wic = coll.__dict__.get('words_in_collections')
        if wic is not None:
            words_count = len(wic)

    # Get author (either author object or author_id)
    author = getattr(coll, 'author', None)
    if author:
        author_value = (
            {
                'slug': getattr(author, 'slug', None),
                'username': getattr(author, 'username', None),
                'first_name': getattr(author, 'first_name', None),
                'profile_image_url': getattr(author, 'profile_image_url', None),
            }
            if for_published
            else str(author.id)
        )
    else:
        author_value = str(getattr(coll, 'author_id', ''))

    # Get words languages (unique language codes from words in collection)
    words_languages = getattr(coll, '_words_languages', [])

    # Get last 4 words for preview
    last_4_words = getattr(coll, '_last_4_words', [])

    result = CollectionShortOut(
        id=coll.id,
        slug=coll.slug,
        author=author_value,
        title=coll.title,
        description=coll.description,
        words_count=words_count or 0,
        words_languages=words_languages,
        last_4_words=last_4_words,
        available_words_count=getattr(coll, '_available_words_count', None),
        read_access_level=getattr(coll, 'read_access_level', None),
        add_access_level=getattr(coll, 'add_access_level', None),
        favorite=getattr(coll, '_favorite', False),
        created=coll.created,
        modified=coll.modified,
    )

    if not include_words:
        return result

    words = [
        map_word(w.word if hasattr(w, 'word') else w)
        for w in getattr(coll, 'words_in_collections', []) or []
    ]

    # CollectionReadOut requires author to be AuthorShortOut, not a string
    result_dict = result.model_dump()
    if isinstance(result_dict.get('author'), dict):
        result_dict['author'] = AuthorShortOut(**result_dict['author'])
    elif isinstance(result_dict.get('author'), str) and for_published:
        # If author is a string but we need AuthorShortOut, we need to load it
        # This shouldn't happen if for_published=True, but handle it just in case
        if author:
            result_dict['author'] = AuthorShortOut(
                slug=getattr(author, 'slug', ''),
                username=getattr(author, 'username', ''),
                first_name=getattr(author, 'first_name', None),
                profile_image_url=getattr(author, 'profile_image_url', None),
            )

    return CollectionReadOut(**result_dict, words=words)
