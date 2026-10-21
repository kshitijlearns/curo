"""Gemini embeddings — NOT IMPLEMENTED YET (needs GEMINI_API_KEY).

TODO when the key arrives (see docs/INTEGRATION.md):
1. Call the embedContent / batchEmbedContents endpoint with model GEMINI_EMBEDDING_MODEL and
   outputDimensionality = 768 (EMBEDDING_DIM; the pgvector column is fixed at 768).
2. L2-normalise each vector (reduced-dimension outputs are not normalised by the API).
3. Batch up to 100 texts per request; TransientError-style retry on 429/5xx.
4. Set ``model`` to the exact model name: reel_embeddings.model records it, and switching
   models means re-embedding every reel (never mix models in one table).
5. Read the answer with ``parse_embeddings`` (below, already real; contract-tested).
"""

from __future__ import annotations

import math
from typing import Any

from .base import DIM, EmbeddingProvider

_TODO = "Gemini embeddings not implemented yet: set EMBEDDING_PROVIDER=mock (see INTEGRATION.md)"


class GeminiEmbeddingProvider(EmbeddingProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def embed(self, texts):
        raise NotImplementedError(_TODO)


class EmbeddingError(Exception):
    pass


def parse_embeddings(raw: dict[str, Any], dim: int = DIM) -> list[list[float]]:
    """A batchEmbedContents (or embedContent) answer: one vector per text, checked for the
    fixed size and L2-normalised (reduced-size Gemini vectors come back unnormalised)."""
    items = raw.get("embeddings")
    if items is None and "embedding" in raw:
        items = [raw["embedding"]]
    out = []
    for item in items or []:
        values = [float(v) for v in item.get("values", [])]
        if len(values) != dim:
            raise EmbeddingError(
                f"expected {dim} values, got {len(values)}: set outputDimensionality"
            )
        norm = math.sqrt(sum(v * v for v in values))
        if norm == 0:
            raise EmbeddingError("an all-zero vector")
        out.append([v / norm for v in values])
    return out
