"""The mock PublicDataProvider (on the real fixture dataset) and the failover wrapper."""

from datetime import timedelta

import pytest

from curo.providers.public_data import (
    AccountNotFound,
    CollectionFailed,
    PrivateAccount,
    PublicDataProvider,
    TransientError,
)
from curo.providers.public_data.failover import FailoverProvider
from curo.providers.public_data.mock import MockPublicDataProvider, views_at

ANCHOR = MockPublicDataProvider().anchor  # 12 days before Ganesh Chaturthi 2027


def provider_at(when):
    return MockPublicDataProvider(now=lambda: when)


def test_fixture_tells_the_prototype_story_at_the_anchor():
    p = provider_at(ANCHOR)
    reels = p.get_reels("curo.demo", 50)
    assert len(reels) == 49  # 50 past reels, one deleted before the anchor
    titles = [
        r.caption.split(" 🎥")[0].split(" ✨")[0].split(" 💛")[0].split(" 🛍️")[0] for r in reels[:4]
    ]
    assert titles == [
        "3 mistakes ruining your aesthetic reel",
        "Get ready with me: Navratri edition",
        "One kurta, five dupattas",
        "Thrift haul under ₹2,000",
    ]
    assert reels[0].views == 104_000
    assert reels[0].shares == 281
    profile = p.get_profile("curo.demo")
    assert 45_000 < profile.followers < 52_000


def test_missing_counts_are_none():
    reels = provider_at(ANCHOR).get_reels("curo.demo", 12)

    def find(prefix):
        return next(r for r in reels if r.caption.startswith(prefix))

    hidden = find("GRWM: monsoon office look")
    assert hidden.likes is None and hidden.likes_hidden
    assert find("How I light my reels").shares is None
    comments_off = find("My monsoon skincare routine")
    assert comments_off.comments is None and comments_off.comments_disabled
    assert comments_off.is_paid_partnership


def test_counts_grow_with_time_and_future_reels_appear_later():
    p_now = provider_at(ANCHOR)
    p_later = provider_at(ANCHOR + timedelta(days=2))
    first_now = p_now.get_reels("curo.demo", 1)[0]
    newer = p_later.get_reels("curo.demo", 3)
    assert newer[0].shortcode != first_now.shortcode  # a reel posted after the anchor
    same = next(r for r in newer if r.shortcode == first_now.shortcode)
    assert same.views > first_now.views


def test_reels_by_shortcode_omits_deleted_reels():
    before = provider_at(ANCHOR - timedelta(days=10))
    all_before = before.get_reels("curo.demo", 50)
    deleted = next(r for r in all_before if "10-minute reel editing" in r.caption)
    after = provider_at(ANCHOR)
    assert after.get_reels_by_shortcodes("curo.demo", [deleted.shortcode]) == []


def test_unknown_and_private_accounts():
    p = provider_at(ANCHOR)
    with pytest.raises(AccountNotFound):
        p.get_profile("no.such.creator")
    data = {
        "meta": {"anchor": ANCHOR.isoformat()},
        "accounts": [
            {
                "username": "goes.private",
                "followers": {"base": 100},
                "posts_at_anchor": 1,
                "status_events": [{"at_h": 5, "status": "private"}],
            }
        ],
        "reels": {"goes.private": []},
    }
    assert (
        MockPublicDataProvider(data=data, now=lambda: ANCHOR).get_profile("goes.private").followers
        == 100
    )
    with pytest.raises(PrivateAccount):
        MockPublicDataProvider(data=data, now=lambda: ANCHOR + timedelta(hours=6)).get_profile(
            "goes.private"
        )


def test_comments_carry_handles_only_until_stored():
    p = provider_at(ANCHOR)
    reel = p.get_reels("curo.demo", 1)[0]
    comments = p.get_comments(reel.permalink)
    assert len(comments) > 30
    top = max(comments, key=lambda c: c.like_count)
    assert top.text == "Mistake #2 is literally me every single time. Saving this."
    assert all(c.author_handle for c in comments)  # vendor gives handles; storage drops them


def test_glitch_reports_fewer_views_inside_its_window():
    reel = next(
        r
        for r in provider_at(ANCHOR).get_reels("curo.demo", 12)
        if r.caption.startswith("GRWM: monsoon")
    )
    p_glitch = provider_at(ANCHOR - timedelta(hours=100))
    p_before = provider_at(ANCHOR - timedelta(hours=124))
    during = p_glitch.get_reels_by_shortcodes("curo.demo", [reel.shortcode])[0].views
    before = p_before.get_reels_by_shortcodes("curo.demo", [reel.shortcode])[0].views
    assert during < before  # the data-quality rule must catch this


def test_second_wave_curve():
    curve = {
        "v_total": 100,
        "tau_h": 50,
        "beta": 1.6,
        "wave2": {"start_h": 100, "v": 100, "tau_h": 50, "beta": 2.0},
    }
    assert views_at(100, curve) < views_at(150, curve) - 30


# ---------------------------------------------------------------- failover


class Flaky(PublicDataProvider):
    def __init__(self, name, fails, raise_=TransientError):
        self.name, self.fails, self.calls, self.raise_ = name, fails, 0, raise_

    def get_profile(self, username):
        self.calls += 1
        if self.calls <= self.fails:
            raise self.raise_("boom")
        return {"from": self.name}

    get_reels = get_reels_by_shortcodes = get_comments = get_hashtag_page = download = None


def test_retry_once_then_succeed():
    primary = Flaky("primary", fails=1)
    assert FailoverProvider(primary).get_profile("x") == {"from": "primary"}
    assert primary.calls == 2


def test_backup_vendor_after_two_failures():
    primary, backup = Flaky("primary", fails=5), Flaky("backup", fails=0)
    assert FailoverProvider(primary, backup).get_profile("x") == {"from": "backup"}
    assert primary.calls == 2 and backup.calls == 1


def test_snapshot_missed_when_everything_fails():
    with pytest.raises(CollectionFailed):
        FailoverProvider(Flaky("p", 9), Flaky("b", 9)).get_profile("x")


def test_definitive_answers_are_not_retried():
    primary = Flaky("primary", fails=5, raise_=PrivateAccount)
    with pytest.raises(PrivateAccount):
        FailoverProvider(primary, Flaky("b", 0)).get_profile("x")
    assert primary.calls == 1
