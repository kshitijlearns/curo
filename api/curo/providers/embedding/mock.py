"""Mock embeddings: deterministic feature hashing (D9).

Words, character 4-grams and a small concept lexicon are hashed into 768 signed buckets and
L2-normalised. The same text always gives the same vector (no drift between runs), texts
that share words and concepts land close together, and nothing is trained or downloaded.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter

import numpy as np

from curo.providers.mock_text import concepts, content_words

from .base import DIM, EmbeddingProvider


def _bucket(feature: str) -> tuple[int, float]:
    h = int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")
    return h % DIM, (1.0 if (h >> 40) & 1 else -1.0)


class MockEmbeddingProvider(EmbeddingProvider):
    name = "mock"
    model = "mock-hash-768-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        v = np.zeros(DIM)

        def add(feature: str, weight: float) -> None:
            i, sign = _bucket(feature)
            v[i] += sign * weight

        for word, n in Counter(content_words(text)).items():
            w = 1.0 + math.log(n)
            add(f"w:{word}", w)
            padded = f"<{word}>"
            for k in range(len(padded) - 3):
                add(f"c:{padded[k : k + 4]}", 0.15 * w)
        for concept, n in concepts(text).items():
            add(f"k:{concept}", 1.5 * (1.0 + math.log(n)))
        norm = float(np.linalg.norm(v))
        if norm == 0:
            v[0] = 1.0  # empty text: a fixed unit vector rather than zeros
            norm = 1.0
        return (v / norm).round(6).tolist()
