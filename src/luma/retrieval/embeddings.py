from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from itertools import pairwise
from typing import Protocol

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class EmbeddingProvider(Protocol):
    """Provider-neutral interface used by indexing and query paths."""

    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class HashingEmbeddingProvider:
    """Offline deterministic dense baseline for plumbing and regression tests.

    This is feature hashing, not a claim of semantic-model quality. The production
    provider can be swapped through ``EmbeddingProvider`` without changing storage
    or ranking code.
    """

    def __init__(self, dimensions: int = 768) -> None:
        self._dimensions = dimensions

    @property
    def model_name(self) -> str:
        return f"luma-feature-hash-{self._dimensions}-v1"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _embed(self, text: str) -> list[float]:
        tokens = TOKEN_PATTERN.findall(text.lower())
        features = tokens + [f"{left}_{right}" for left, right in pairwise(tokens)]
        vector = [0.0] * self._dimensions
        for feature in features:
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            value = int.from_bytes(digest)
            index = value % self._dimensions
            sign = 1.0 if value & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
