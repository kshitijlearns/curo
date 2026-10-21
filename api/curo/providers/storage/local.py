"""Local-disk storage (LOCAL_STORAGE_DIR, default .data/storage): the development stand-in
for Supabase Storage. Same interface; buckets are folders.

Signed uploads point at the API itself (``PUT /v1/uploads/local/{token}``). The token names
the bucket, path and content type, expires, and is signed with HMAC-SHA256 under the API's
JWT secret, so it works for exactly one path and nothing else.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from curo import clock

from .base import SignedUpload, StorageError, StorageProvider, StoredObject


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class LocalStorage(StorageProvider):
    name = "local"

    def __init__(self, root: Path | str, secret: str = ""):
        self.root = Path(root).resolve()
        self._secret = secret.encode("utf-8")

    def _file(self, bucket: str, path: str) -> Path:
        target = (self.root / bucket / path).resolve()
        if self.root / bucket not in target.parents:
            raise StorageError(f"path escapes bucket {bucket!r}: {path!r}")
        return target

    def put(self, bucket: str, path: str, data: bytes, content_type: str) -> str:
        target = self._file(bucket, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return path

    def get(self, bucket: str, path: str) -> bytes:
        target = self._file(bucket, path)
        if not target.exists():
            raise StorageError(f"not found: {bucket}/{path}")
        return target.read_bytes()

    def delete(self, bucket: str, path: str) -> None:
        self._file(bucket, path).unlink(missing_ok=True)

    def exists(self, bucket: str, path: str) -> bool:
        return self._file(bucket, path).exists()

    def list(self, bucket: str, prefix: str) -> list[StoredObject]:
        base = self.root / bucket
        start = self._file(bucket, prefix) if prefix else base
        folder = start if start.is_dir() else start.parent
        if not folder.exists():
            return []
        out = []
        for f in sorted(folder.rglob("*")):
            rel = f.relative_to(base).as_posix()
            if f.is_file() and rel.startswith(prefix):
                out.append(StoredObject(rel, datetime.fromtimestamp(f.stat().st_mtime, UTC)))
        return out

    # ------------------------------------------------------------------ signed uploads

    def _sign(self, payload: bytes) -> str:
        if not self._secret:
            raise StorageError("local storage has no signing secret")
        return _b64(hmac.new(self._secret, payload, hashlib.sha256).digest())

    def signed_upload(
        self, bucket: str, path: str, content_type: str, expires_in_s: int = 900
    ) -> SignedUpload:
        self._file(bucket, path)  # refuses a path outside the bucket
        expires = clock.now() + timedelta(seconds=expires_in_s)
        claims = {"b": bucket, "p": path, "t": content_type, "e": int(expires.timestamp())}
        payload = json.dumps(claims, separators=(",", ":")).encode("utf-8")
        token = f"{_b64(payload)}.{self._sign(payload)}"
        return SignedUpload(
            url=f"/v1/uploads/local/{token}",
            expires_at=expires,
            headers={"Content-Type": content_type},
        )

    def accept_upload(self, token: str, data: bytes) -> tuple[str, str]:
        body, _, signature = token.partition(".")
        try:
            payload = _unb64(body)
            claims = json.loads(payload)
        except (ValueError, json.JSONDecodeError) as exc:
            raise StorageError("This upload link isn't valid.") from exc
        if not signature or not hmac.compare_digest(signature, self._sign(payload)):
            raise StorageError("This upload link isn't valid.")
        if datetime.fromtimestamp(claims["e"], UTC) < clock.now():
            raise StorageError("This upload link has expired. Start the upload again.")
        self.put(claims["b"], claims["p"], data, claims["t"])
        return claims["b"], claims["p"]
