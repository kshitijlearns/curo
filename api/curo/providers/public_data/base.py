"""PublicDataProvider: the one interface for public Instagram data (MVP doc §4–5).

Features never call a vendor directly. Every implementation — the fixture mock now,
Apify and Bright Data later — returns these models, logged-out and public only:

* refuses private accounts (raises PrivateAccount) and never logs in;
* returns ``None`` for counts that aren't public (hidden likes, no share count,
  comments turned off). Missing means unknown, never zero.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field


class ProfileData(BaseModel):
    username: str
    full_name: str | None = None
    bio: str | None = None
    followers: int | None = None
    following: int | None = None
    posts: int | None = None
    category: str | None = None
    is_private: bool = False


class ReelData(BaseModel):
    ig_media_id: str
    shortcode: str
    permalink: str
    owner_username: str | None = None
    posted_at: datetime
    duration_s: float | None = None
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    audio_name: str | None = None
    is_paid_partnership: bool = False
    video_url: str | None = None
    thumb_url: str | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    likes_hidden: bool = False
    comments_disabled: bool = False


class CommentData(BaseModel):
    ig_comment_id: str
    text: str
    # Read only to filter bots and spot friend tags, then dropped: never stored.
    author_handle: str | None = None
    posted_at: datetime | None = None
    like_count: int = 0
    reply_count: int = 0


class HashtagPageData(BaseModel):
    tag: str
    post_count: int | None = None
    top: list[ReelData] = Field(default_factory=list)
    recent: list[ReelData] = Field(default_factory=list)


class PublicDataError(Exception):
    """Base class for collection errors."""


class AccountNotFound(PublicDataError):
    """The username doesn't exist (or was deleted)."""


class PrivateAccount(PublicDataError):
    """The account is private. CURO never collects private accounts."""


class TransientError(PublicDataError):
    """A vendor hiccup worth retrying (timeout, rate limit, actor failure)."""


class CollectionFailed(PublicDataError):
    """Every attempt failed (retry, then backup vendor): the snapshot is missed."""


class MediaUnavailable(PublicDataError):
    """The media link expired or the file is gone (e.g. the reel was deleted)."""


class PublicDataProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def get_profile(self, username: str) -> ProfileData: ...

    @abstractmethod
    def get_reels(self, username: str, limit: int = 50) -> list[ReelData]:
        """The account's latest reels, newest first, with current public counts."""

    @abstractmethod
    def get_reels_by_shortcodes(self, username: str, shortcodes: list[str]) -> list[ReelData]:
        """Current counts for specific reels, in one batched run. Reels that are gone
        (deleted or unavailable) are simply absent from the result."""

    @abstractmethod
    def get_comments(
        self, permalink: str, limit: int = 100, since: datetime | None = None
    ) -> list[CommentData]:
        """The newest comments, at most ``limit``; with ``since``, only those posted after it
        (a follow-up read never pays for comments CURO already has)."""

    @abstractmethod
    def get_hashtag_page(self, tag: str, limit: int = 50) -> HashtagPageData: ...

    @abstractmethod
    def download(self, url: str) -> bytes:
        """Fetch a reel's video or thumbnail from the vendor's media link. Links expire, so
        callers copy the file into storage straight away. Raises MediaUnavailable."""
