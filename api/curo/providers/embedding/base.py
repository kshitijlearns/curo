"""EmbeddingProvider: text → a fixed-size vector (MVP doc §5).

One model per table: ``reel_embeddings.model`` records which model made each vector, and
vectors from different models are never compared. Switching models means re-embedding.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

DIM = 768


class EmbeddingProvider(ABC):
    name: str = "abstract"
    model: str = "abstract"
    dim: int = DIM

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """One L2-normalised vector of length ``dim`` per text."""
