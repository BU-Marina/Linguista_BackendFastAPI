"""Schemas for published resources."""

from __future__ import annotations

from typing import List

from api.v1.vocabulary.schemas import WordListOut, WordReadOut, PageOut as WordsPageBase
from api.v1.collections.schemas import (
    CollectionShortOut,
    CollectionReadOut,
    PageOut as CollectionsPageBase,
)


class WordsPageOut(WordsPageBase):
    results: List[WordListOut]


class CollectionsPageOut(CollectionsPageBase):
    results: List[CollectionShortOut]


__all__ = [
    "WordListOut",
    "WordReadOut",
    "WordsPageOut",
    "CollectionShortOut",
    "CollectionReadOut",
    "CollectionsPageOut",
]
