"""Collections mapping helpers."""

from __future__ import annotations

from api.v1.vocabulary.mapping import map_word
from .schemas import CollectionShortOut, CollectionReadOut


def map_collection(coll, include_words: bool = False):
    words_count = getattr(coll, "_words_count", None)
    if words_count is None and getattr(coll, "words_in_collections", None):
        words_count = len(coll.words_in_collections)
    result = CollectionShortOut(
        id=coll.id,
        slug=coll.slug,
        title=coll.title,
        description=coll.description,
        words_count=words_count or 0,
        favorite=getattr(coll, "_favorite", False),
        created=coll.created,
        modified=coll.modified,
    )
    if not include_words:
        return result
    words = [
        map_word(w.word if hasattr(w, "word") else w)
        for w in getattr(coll, "words_in_collections", []) or []
    ]
    return CollectionReadOut(**result.model_dump(), words=words)
