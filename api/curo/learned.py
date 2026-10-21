"""Print what CURO has learned about an account (a developer view of Phase 3's output).

    python -m curo.learned [username]        # default: curo.demo

DNA coverage and examples, baselines, sub-clusters, pattern cards and comment themes, read
straight from the database.
"""

from __future__ import annotations

import sys

from curo.db import service_connection
from curo.schemas.taxonomy import UNKNOWN, label_for
from curo.services.metrics import AGE_BUCKETS
from curo.services.text import reel_title

METRIC_NAMES = {
    "views": "views",
    "like_rate": "likes per view",
    "comment_rate": "comments per view",
    "share_rate": "shares per view",
}
SHOWN_FIELDS = (
    "cluster",
    "context",
    "format",
    "hook_type",
    "ending",
    "cta_type",
    "camera",
    "setting",
)


def card_line(c: dict) -> str:
    """The logic doc's wording: "Choice-question endings → comments 1.6× (14 reels, confidence high)"."""
    what = f"{label_for(c['value'])} ({c['feature'].replace('_', ' ')})"
    metric = METRIC_NAMES.get(c["metric"], c["metric"])
    if c["scope"] == "yours":
        basis = f"{c['n']} reels, confidence {c['confidence']}"
    else:
        basis = f"based on creators like you, confidence {c['confidence']}"
    return f"{what} → {metric} {c['effect']:.2f}× ({basis})"


def main(argv: list[str]) -> int:
    username = (argv[0] if argv else "curo.demo").lstrip("@").lower()
    with service_connection() as conn:
        account = conn.execute(
            "select * from public.accounts where username = %s", (username,)
        ).fetchone()
        if account is None:
            print(f"@{username} isn't in the database. Onboard it or run the seed first.")
            return 1
        aid = account["id"]
        reels = conn.execute(
            """
            select r.id, r.caption, r.posted_at, d.content, d.production, d.confidence, d.model_version
              from public.reels r left join public.reel_dna d on d.reel_id = r.id
             where r.account_id = %s and not r.is_deleted order by r.posted_at desc
            """,
            (aid,),
        ).fetchall()
        baselines = conn.execute(
            "select * from public.baselines where account_id = %s", (aid,)
        ).fetchall()
        groups = conn.execute(
            "select * from public.subclusters where account_id = %s order by cardinality(reel_ids) desc",
            (aid,),
        ).fetchall()
        cards = conn.execute(
            """
            select * from public.pattern_cards where account_id = %s
             order by scope desc, abs(ln(effect)) desc
            """,
            (aid,),
        ).fetchall()
        themes = conn.execute(
            "select * from public.comment_themes where account_id = %s order by share desc", (aid,)
        ).fetchall()
        labelled = conn.execute(
            """
            select count(*) filter (where c.labelled_at is not null) as labelled,
                   count(*) filter (where c.is_bot) as bots, count(*) as total
              from public.comments c join public.reels r on r.id = c.reel_id where r.account_id = %s
            """,
            (aid,),
        ).fetchone()

    with_dna = [r for r in reels if r["content"] is not None]
    fields = [
        (name, (r["content"] | r["production"]).get(name))
        for r in with_dna
        for name in SHOWN_FIELDS
    ]
    unknown = sum(1 for _n, v in fields if v == UNKNOWN)
    print(f"@{username}: {len(reels)} reels, {len(with_dna)} with DNA")
    if with_dna:
        print(f"  model: {with_dna[0]['model_version']}")
        print(f"  unknown (confidence below 0.6): {unknown} of {len(fields)} shown fields")
    print(
        f"  comments: {labelled['labelled']} of {labelled['total']} labelled, {labelled['bots']} likely bots"
    )

    print("\nDNA, newest three")
    for r in with_dna[:3]:
        dna = r["content"] | r["production"]
        print(f"  {reel_title(r['caption'])}")
        print(
            "    "
            + ", ".join(f"{n}={dna.get(n)} ({r['confidence'].get(n, 0):.2f})" for n in SHOWN_FIELDS)
        )

    print("\nBaselines: median views (n reels) by age")
    by = {(b["metric"], b["age_bucket"]): b for b in baselines}
    for metric in ("views", "like_rate", "comment_rate", "share_rate", "views_share_7d"):
        cells = []
        for bucket in AGE_BUCKETS:
            b = by.get((metric, bucket))
            if b is None or b["median"] is None:
                cells.append(f"{bucket}: –")
            elif metric == "views":
                cells.append(f"{bucket}: {b['median']:,.0f} ({b['n']})")
            else:
                cells.append(f"{bucket}: {b['median']:.4f} ({b['n']})")
        print(f"  {metric:15} " + "  ".join(cells))

    print("\nSub-clusters")
    for g in groups:
        lifts = ", ".join(
            f"{METRIC_NAMES[m]} {v['lift']:.2f}×" for m, v in (g["lifts"] or {}).items()
        )
        print(f"  {g['label']} · {len(g['reel_ids'])} reels · {lifts}")

    print("\nPattern cards")
    for c in cards:
        print(f"  [{c['scope']}] {card_line(c)}")
    if not cards:
        print("  none yet")

    print("\nComment themes (share of comments on the last 30 reels)")
    for t in themes:
        print(f"  {t['label']} · {t['kind']} · {t['share'] * 100:.1f}% ({t['n']} comments)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
