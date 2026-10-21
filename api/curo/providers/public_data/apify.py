"""Apify implementation of PublicDataProvider — NOT IMPLEMENTED YET (needs APIFY_TOKEN).

TODO when the key arrives (see docs/INTEGRATION.md):
1. Pick and pin the actors (APIFY_PROFILE_ACTOR_ID, APIFY_REELS_ACTOR_ID with share counts
   enabled, APIFY_COMMENTS_ACTOR_ID, APIFY_HASHTAG_ACTOR_ID). Test two or three reel actors
   on the same 20 reels and keep the most complete (MVP doc §5).
2. Call actors through the REST API (run-sync-get-dataset-items for small runs; start a run
   with a webhook to /v1/webhooks/apify for large ones), logged out, never with a login.
3. Map every item to ProfileData / ReelData / CommentData / HashtagPageData, validating each
   field: a missing count is None (hidden likes, no share count, comments off), never 0.
4. Raise PrivateAccount for private profiles, AccountNotFound for missing ones, and
   TransientError for timeouts / rate limits / failed runs (FailoverProvider retries).
5. get_reels_by_shortcodes must be ONE run for all requested reels (snapshots are batched
   per account; every snapshot is a paid result).
6. Record real responses with tools/record_contracts.py and add contract tests.
"""

from __future__ import annotations

from typing import Any

from .base import CommentData, HashtagPageData, ProfileData, PublicDataProvider, ReelData

_TODO = "Apify provider not implemented yet: set PUBLIC_DATA_PROVIDER=mock (see INTEGRATION.md)"


class ApifyProvider(PublicDataProvider):
    name = "apify"

    def __init__(self, token: str, actors: dict[str, str]):
        self.token = token
        self.actors = actors

    def get_profile(self, username):
        raise NotImplementedError(_TODO)

    def get_reels(self, username, limit=50):
        raise NotImplementedError(_TODO)

    def get_reels_by_shortcodes(self, username, shortcodes):
        raise NotImplementedError(_TODO)

    def get_comments(self, permalink, limit=100, since=None):
        raise NotImplementedError(_TODO)

    def get_hashtag_page(self, tag, limit=50):
        raise NotImplementedError(_TODO)

    def download(self, url):
        # TODO: plain HTTPS GET of the media URL the actor returned (httpx, 60 s timeout,
        # 100 MB cap); 403/404/410 → MediaUnavailable (link expired: re-fetch the reel to get
        # a fresh URL), timeouts/5xx → TransientError.
        raise NotImplementedError(_TODO)


# ---------------------------------------------------------------- reading Apify's items
# Pure functions from the vendor's raw items to CURO's models: the provider calls them, and
# tests/test_contracts.py replays responses recorded with tools/record_contracts.py through
# them. Their mapping depends on the actors you pick, so they are written with it.
# Rules for every one: a count that isn't shown is None (never 0); likes_hidden /
# comments_disabled where the item says so; owner handles of commenters are read only for
# CommentData.author_handle (never stored).


def parse_profile(items: list[dict[str, Any]]) -> ProfileData:
    raise NotImplementedError(_TODO)


def parse_reels(items: list[dict[str, Any]]) -> list[ReelData]:
    raise NotImplementedError(_TODO)


def parse_comments(items: list[dict[str, Any]]) -> list[CommentData]:
    raise NotImplementedError(_TODO)


def parse_hashtag_page(tag: str, items: list[dict[str, Any]]) -> HashtagPageData:
    raise NotImplementedError(_TODO)
