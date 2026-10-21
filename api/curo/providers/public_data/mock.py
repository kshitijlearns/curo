"""Mock PublicDataProvider serving the deterministic fixture dataset (fixtures/data).

It behaves like a live vendor at ``clock.now()``:

* reels posted after "now" don't exist yet; deleted reels disappear at their deletion time;
* counts come from each reel's growth curve at its current age, so successive snapshots
  grow like real ones (and one scripted vendor glitch reports a lower count);
* hidden likes, missing share counts and disabled comments come back as None;
* accounts can turn private or be deleted at a scripted time.

Times in the fixtures are offsets in hours from the dataset's anchor (meta.json), which is
12 days before Ganesh Chaturthi 2027; set FAKE_NOW to the anchor to see the demo.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import Any

from curo import clock
from curo.config import REPO_ROOT

from .base import (
    AccountNotFound,
    CommentData,
    HashtagPageData,
    MediaUnavailable,
    PrivateAccount,
    ProfileData,
    PublicDataProvider,
    ReelData,
)

DEFAULT_DATA_DIR = REPO_ROOT / "fixtures" / "data"
MEDIA_BASE = "https://cdn.example.invalid/"
# Downloaded "videos" are small placeholders that name their fixture reel; the mock video
# provider reads them back from storage and returns that reel's fixture understanding.
MOCK_VIDEO_MAGIC = b"CURO-MOCK-MEDIA\n"


def curve_fraction(age_h: float, tau_h: float, beta: float) -> float:
    """Share of a reel's total views reached by ``age_h`` (Weibull-shaped growth)."""
    if age_h <= 0:
        return 0.0
    return 1.0 - math.exp(-((age_h / tau_h) ** beta))


def views_at(age_h: float, curve: dict[str, Any]) -> float:
    """Views at a given age from a fixture curve, including an optional second wave."""
    views = curve["v_total"] * curve_fraction(age_h, curve["tau_h"], curve["beta"])
    wave = curve.get("wave2")
    if wave and age_h > wave["start_h"]:
        views += wave["v"] * curve_fraction(
            age_h - wave["start_h"], wave["tau_h"], wave.get("beta", 1.0)
        )
    return views


def permalink_for(shortcode: str) -> str:
    return f"https://www.instagram.com/reel/{shortcode}/"


def shortcode_from_permalink(permalink: str) -> str:
    return permalink.rstrip("/").rsplit("/", 1)[-1]


class MockPublicDataProvider(PublicDataProvider):
    name = "mock"

    def __init__(
        self,
        data_dir: Path | str | None = None,
        *,
        data: dict[str, Any] | None = None,
        now: Callable[[], datetime] = clock.now,
    ):
        """Read fixtures from ``data_dir``, or take an in-memory ``data`` dict (tests)."""
        self._dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self._data = data
        self._now = now

    # ------------------------------------------------------------------ loading

    def _read(self, name: str) -> Any:
        if self._data is not None:
            return self._data[name.split("/")[0].removesuffix(".json")]
        return json.loads((self._dir / name).read_text(encoding="utf-8"))

    @cached_property
    def meta(self) -> dict[str, Any]:
        return self._read("meta.json")

    @cached_property
    def anchor(self) -> datetime:
        return clock.to_utc(datetime.fromisoformat(self.meta["anchor"]))

    @cached_property
    def accounts(self) -> dict[str, dict[str, Any]]:
        return {a["username"]: a for a in self._read("accounts.json")}

    @cached_property
    def _reels(self) -> dict[str, list[dict[str, Any]]]:
        if self._data is not None:
            return self._data["reels"]
        return {
            p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((self._dir / "reels").glob("*.json"))
        }

    @cached_property
    def _comments(self) -> dict[str, list[dict[str, Any]]]:
        if self._data is not None:
            return self._data.get("comments", {})
        out: dict[str, list[dict[str, Any]]] = {}
        for p in sorted((self._dir / "comments").glob("*.json")):
            out.update(json.loads(p.read_text(encoding="utf-8")))
        return out

    @cached_property
    def _hashtags(self) -> dict[str, dict[str, Any]]:
        if self._data is not None:
            return self._data.get("hashtags", {})
        return self._read("hashtags.json")

    @cached_property
    def _owner_of(self) -> dict[str, str]:
        return {r["shortcode"]: user for user, reels in self._reels.items() for r in reels}

    # ------------------------------------------------------------------ time helpers

    def _hours(self) -> float:
        return (self._now() - self.anchor).total_seconds() / 3600

    def _at(self, offset_h: float) -> datetime:
        return self.anchor + timedelta(hours=offset_h)

    def _status(self, account: dict[str, Any], h: float) -> str:
        status = "public"
        for event in sorted(account.get("status_events", []), key=lambda e: e["at_h"]):
            if event["at_h"] <= h:
                status = event["status"]
        return status

    def _account(self, username: str) -> dict[str, Any]:
        account = self.accounts.get(username.lower().lstrip("@"))
        if account is None:
            raise AccountNotFound(username)
        status = self._status(account, self._hours())
        if status == "deleted":
            raise AccountNotFound(username)
        if status == "private" or account.get("is_private"):
            raise PrivateAccount(username)
        return account

    def _live_reels(self, username: str) -> list[dict[str, Any]]:
        h = self._hours()
        reels = [
            r
            for r in self._reels.get(username, [])
            if r["posted_h"] <= h and (r.get("deleted_h") is None or r["deleted_h"] > h)
        ]
        return sorted(reels, key=lambda r: r["posted_h"], reverse=True)

    # ------------------------------------------------------------------ mapping

    def _visible_comments(self, shortcode: str) -> list[dict[str, Any]]:
        h = self._hours()
        return [c for c in self._comments.get(shortcode, []) if c["posted_h"] <= h]

    def _reel_data(self, r: dict[str, Any], owner: str) -> ReelData:
        h = self._hours()
        age = h - r["posted_h"]
        views = views_at(age, r["curve"])
        glitch = r.get("glitch")
        if glitch and glitch["from_h"] <= h <= glitch["to_h"]:
            views *= glitch["factor"]  # a vendor glitch: reports fewer views than before
        rates = r["rates"]
        likes = None if r.get("likes_hidden") else round(views * rates["like"])
        comments = None
        if not r.get("comments_disabled"):
            comments = max(
                round(views * rates["comment"]), len(self._visible_comments(r["shortcode"]))
            )
        shares = None if r.get("shares_hidden") else round(views * rates["share"])
        return ReelData(
            ig_media_id=r["ig_media_id"],
            shortcode=r["shortcode"],
            permalink=permalink_for(r["shortcode"]),
            owner_username=owner,
            posted_at=self._at(r["posted_h"]),
            duration_s=r.get("duration_s"),
            caption=r.get("caption", ""),
            hashtags=r.get("hashtags", []),
            mentions=r.get("mentions", []),
            audio_name=r.get("audio_name"),
            is_paid_partnership=bool(r.get("is_paid_partnership")),
            video_url=f"{MEDIA_BASE}{r['shortcode']}.mp4",
            thumb_url=f"{MEDIA_BASE}{r['shortcode']}.jpg",
            views=round(views),
            likes=likes,
            comments=comments,
            shares=shares,
            likes_hidden=bool(r.get("likes_hidden")),
            comments_disabled=bool(r.get("comments_disabled")),
        )

    # ------------------------------------------------------------------ interface

    def get_profile(self, username: str) -> ProfileData:
        a = self._account(username)
        h = self._hours()
        f = a["followers"]
        jumps = f.get("jumps", [])
        followers = (
            f["base"]
            + f.get("per_day", 0) * h / 24
            + sum(j["add"] for j in jumps if j["at_h"] <= h)
            - sum(j["add"] for j in jumps if j["at_h"] <= 0)
        )
        reels = self._reels.get(a["username"], [])
        posts = (
            a["posts_at_anchor"]
            + sum(1 for r in reels if 0 < r["posted_h"] <= h)
            - sum(1 for r in reels if h < r["posted_h"] <= 0)
        )
        return ProfileData(
            username=a["username"],
            full_name=a.get("full_name"),
            bio=a.get("bio"),
            followers=round(followers),
            following=a.get("following"),
            posts=posts,
            category=a.get("category"),
            is_private=False,
        )

    def get_reels(self, username: str, limit: int = 50) -> list[ReelData]:
        a = self._account(username)
        return [self._reel_data(r, a["username"]) for r in self._live_reels(a["username"])[:limit]]

    def get_reels_by_shortcodes(self, username: str, shortcodes: list[str]) -> list[ReelData]:
        a = self._account(username)
        wanted = set(shortcodes)
        return [
            self._reel_data(r, a["username"])
            for r in self._live_reels(a["username"])
            if r["shortcode"] in wanted
        ]

    def get_comments(
        self, permalink: str, limit: int = 100, since: datetime | None = None
    ) -> list[CommentData]:
        shortcode = shortcode_from_permalink(permalink)
        owner = self._owner_of.get(shortcode)
        if owner is None:
            return []
        self._account(owner)  # private / deleted accounts expose nothing
        if not any(r["shortcode"] == shortcode for r in self._live_reels(owner)):
            return []
        comments = sorted(
            self._visible_comments(shortcode), key=lambda c: c["posted_h"], reverse=True
        )
        return [
            CommentData(
                ig_comment_id=c["id"],
                text=c["text"],
                author_handle=c.get("author"),
                posted_at=self._at(c["posted_h"]),
                like_count=c.get("likes", 0),
                reply_count=c.get("replies", 0),
            )
            for c in comments
            if since is None or self._at(c["posted_h"]) > since
        ][:limit]

    def get_hashtag_page(self, tag: str, limit: int = 50) -> HashtagPageData:
        page = self._hashtags.get(tag.lower().lstrip("#"))
        if page is None:
            return HashtagPageData(tag=tag.lower().lstrip("#"))
        h = self._hours()

        def to_reel(s: dict[str, Any]) -> ReelData:
            return ReelData(
                ig_media_id=s["ig_media_id"],
                shortcode=s["shortcode"],
                permalink=permalink_for(s["shortcode"]),
                owner_username=s.get("owner"),
                posted_at=self._at(s["posted_h"]),
                duration_s=s.get("duration_s"),
                caption=s.get("caption", ""),
                hashtags=s.get("hashtags", []),
                views=s.get("views"),
                likes=s.get("likes"),
                comments=s.get("comments"),
            )

        live = [s for s in page["reels"] if s["posted_h"] <= h]
        top = sorted(live, key=lambda s: s.get("views") or 0, reverse=True)[:9]
        recent = sorted(live, key=lambda s: s["posted_h"], reverse=True)[:limit]
        return HashtagPageData(
            tag=page["tag"],
            post_count=page.get("post_count"),
            top=[to_reel(s) for s in top],
            recent=[to_reel(s) for s in recent],
        )

    def download(self, url: str) -> bytes:
        if not url.startswith(MEDIA_BASE):
            raise MediaUnavailable(url)
        shortcode, _, kind = url[len(MEDIA_BASE) :].partition(".")
        owner = self._owner_of.get(shortcode)
        if owner is None or not any(r["shortcode"] == shortcode for r in self._live_reels(owner)):
            raise MediaUnavailable(url)  # unknown, deleted, or not posted yet
        ref = {"shortcode": shortcode, "owner": owner, "kind": kind}
        return MOCK_VIDEO_MAGIC + json.dumps(ref).encode("utf-8")
