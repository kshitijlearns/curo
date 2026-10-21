"""StorageProvider: reel videos, thumbnails and uploads (MVP doc §5–6).

Instagram's media links expire, so ``process_reel`` copies each video and thumbnail into
storage straight away. Peers' videos are deleted once their DNA is extracted.

The Simulator's uploads go from the phone straight to storage through a signed upload URL
(``POST /v1/uploads/sign``): the API never streams the video itself.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


class StorageError(Exception):
    pass


@dataclass(frozen=True)
class StoredObject:
    path: str
    created_at: datetime


@dataclass(frozen=True)
class SignedUpload:
    """Where the app sends the file: ``method`` to ``url`` with ``headers``. A URL starting
    with "/" is on CURO's API (local storage); otherwise it is the storage service's own."""

    url: str
    expires_at: datetime
    method: str = "PUT"
    headers: dict[str, str] = field(default_factory=dict)


class StorageProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def put(self, bucket: str, path: str, data: bytes, content_type: str) -> str:
        """Store ``data`` and return its path."""

    @abstractmethod
    def get(self, bucket: str, path: str) -> bytes: ...

    @abstractmethod
    def delete(self, bucket: str, path: str) -> None:
        """Remove the object; a missing object is not an error."""

    @abstractmethod
    def exists(self, bucket: str, path: str) -> bool: ...

    @abstractmethod
    def list(self, bucket: str, prefix: str) -> list[StoredObject]:
        """Every object under a prefix ("uploads/<creator id>/"), for deletion and cleanup."""

    @abstractmethod
    def signed_upload(
        self, bucket: str, path: str, content_type: str, expires_in_s: int = 900
    ) -> SignedUpload:
        """A short-lived URL the app can upload one file to, at exactly this path."""

    def accept_upload(self, token: str, data: bytes) -> tuple[str, str]:
        """Store a file sent to a signed URL on CURO's API; returns (bucket, path). Only
        storage whose signed URLs point at the API receives files this way."""
        raise StorageError("uploads go straight to the storage service")
