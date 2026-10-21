"""Failover wrapper (MVP doc §4 data-quality rule): retry once, then try the backup
vendor, then give up so the snapshot is marked missed.

Definitive answers (account not found, account private) are never retried.
Every provider, the mock included, is wrapped, so tests exercise the same path.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import (
    AccountNotFound,
    CollectionFailed,
    MediaUnavailable,
    PrivateAccount,
    PublicDataProvider,
    TransientError,
)

log = logging.getLogger("curo.collection")


class FailoverProvider(PublicDataProvider):
    def __init__(self, primary: PublicDataProvider, backup: PublicDataProvider | None = None):
        self.primary = primary
        self.backup = backup
        self.name = f"{primary.name}+{backup.name}" if backup else primary.name

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        attempts = [self.primary, self.primary] + ([self.backup] if self.backup else [])
        last: Exception | None = None
        for i, provider in enumerate(attempts):
            try:
                return getattr(provider, method)(*args, **kwargs)
            except (AccountNotFound, PrivateAccount, MediaUnavailable):
                raise
            except TransientError as exc:
                last = exc
                log.warning("%s.%s failed (attempt %d): %s", provider.name, method, i + 1, exc)
        raise CollectionFailed(f"{method} failed after retry and backup: {last}") from last

    def get_profile(self, username):
        return self._call("get_profile", username)

    def get_reels(self, username, limit=50):
        return self._call("get_reels", username, limit)

    def get_reels_by_shortcodes(self, username, shortcodes):
        return self._call("get_reels_by_shortcodes", username, shortcodes)

    def get_comments(self, permalink, limit=100, since=None):
        return self._call("get_comments", permalink, limit, since)

    def get_hashtag_page(self, tag, limit=50):
        return self._call("get_hashtag_page", tag, limit)

    def download(self, url):
        # A media link belongs to the vendor that returned it: retry, but no backup vendor.
        return FailoverProvider(self.primary)._call("download", url)
