"""Mock stand-in for T16 (name a trend card): words built only from the card's own facts."""

from __future__ import annotations

from curo.schemas.tasks import T16Input, T16Output


def _plain_tag(tag: str) -> str:
    return "#" + tag


def t16(data: T16Input) -> T16Output:
    if data.kind == "festival":
        name = f"{data.label} looks"
        summary = (
            f"{data.label} is coming up, and {data.niche.lower()} reels for it are starting to "
            "appear."
        )
        angles = [
            f"What to wear for {data.label} on a budget",
            f"One outfit, styled different ways for {data.label}",
            f"Getting ready for {data.label} with what you already own",
        ]
    elif data.kind == "hashtag":
        tag = _plain_tag(data.hashtags[0] if data.hashtags else data.label.lstrip("#"))
        name = f"{tag} is picking up"
        summary = f"More {data.niche.lower()} creators are posting reels tagged {tag}."
        angles = [f"Your own take on {tag}", f"{tag}, done with a twist only you'd add"]
    else:
        tag = _plain_tag(data.hashtags[0] if data.hashtags else data.label.lstrip("#"))
        name = f"The {tag} format"
        summary = f"Reels in {data.niche.lower()} keep using {tag} alongside the niche’s tags."
        angles = [f"Try {tag} with your usual style", f"{tag}, explained in your words"]
    return T16Output(
        name=name[:60], summary=summary, why_rising=data.facts[0], example_angles=angles[:3]
    )
