"""Bright Data implementation of PublicDataProvider (backup vendor) — NOT IMPLEMENTED YET.

TODO when BRIGHTDATA_API_KEY arrives: same contract as apify.py (map to the base models,
None for missing counts, PrivateAccount / AccountNotFound / TransientError). It is used as
the backup in FailoverProvider, or as primary with PUBLIC_DATA_PRIMARY=brightdata.
"""

from __future__ import annotations

from typing import Any

from .base import CommentData, HashtagPageData, ProfileData, PublicDataProvider, ReelData

_TODO = "Bright Data provider not implemented yet: set PUBLIC_DATA_PROVIDER=mock"


class BrightDataProvider(PublicDataProvider):
    name = "brightdata"

    def __init__(self, api_key: str):
        self.api_key = api_key

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
        raise NotImplementedError(_TODO)


# ---------------------------------------------------------------- reading Bright Data's items
# Pure functions from the vendor's raw items to CURO's models: the provider calls them, and
# tests/test_contracts.py replays responses recorded with tools/record_contracts.py through
# them. Their mapping depends on the datasets you pick, so they are written with it.
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
