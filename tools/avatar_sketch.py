"""Draw docs/personas/avatar-moods.svg (every avatar mood in the four persona colours) and
rewrite web/src/lib/avatar.fixture.json (what both copies of the algorithm are tested against).

    python tools/avatar_sketch.py

The shapes are the static (reduced-motion) poses from api/curo/services/persona_avatar.py,
the same code the share card uses; the web component animates between them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from curo.services import persona_avatar as A  # noqa: E402

SEEDS = (20271, 41203, 7719, 93311)  # one example seed per colour
CELL, PAD, TOP, LEFT = 110, 14, 64, 120
MOTION = {
    "neutral": "calm round cluster",
    "love": "lifts into an arc, pulses once",
    "like": "slight upward drift",
    "unsure": "spreads out, slow sway",
    "skip": "drifts sideways, dims",
    "thinking": "pulls into a ring, orbits",
    "listening": "gentle breathing",
}


def main() -> None:
    width = LEFT + len(A.MOODS) * CELL + PAD
    height = TOP + len(A.COLORS) * CELL + 40
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Figtree, Arial, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>',
        '<text x="14" y="26" font-size="16" font-weight="700" fill="#242424">'
        "Follower Persona avatars: moods × colours (static poses)</text>",
    ]
    for j, mood in enumerate(A.MOODS):
        x = LEFT + j * CELL + CELL / 2
        out.append(
            f'<text x="{x}" y="{TOP - 18}" font-size="13" font-weight="700" '
            f'text-anchor="middle" fill="#242424">{mood}</text>'
        )
        out.append(
            f'<text x="{x}" y="{TOP - 4}" font-size="9" text-anchor="middle" '
            f'fill="#242424" fill-opacity="0.7">{MOTION[mood]}</text>'
        )
    for i, (color, seed) in enumerate(zip(A.COLORS, SEEDS, strict=True)):
        y = TOP + i * CELL
        out.append(
            f'<text x="14" y="{y + CELL / 2 + 4}" font-size="12" fill="#242424">'
            f"{i + 1}. {color}</text>"
        )
        for j, mood in enumerate(A.MOODS):
            x = LEFT + j * CELL + 5
            out.append(
                f'<g transform="translate({x} {y + 5}) scale(1)">'
                f"{A.svg_group(seed, color, mood)}</g>"
            )
    out.append(
        f'<text x="14" y="{height - 14}" font-size="10" fill="#242424" fill-opacity="0.7">'
        "Colours follow share order: blue, lavender, pink, ink. Light colours get a hairline "
        "#E4E4EC ring on white. No faces: only the dots move.</text>"
    )
    out.append("</svg>")
    path = ROOT / "docs" / "personas" / "avatar-moods.svg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")
    print(path)
    # The fixture both copies of the algorithm are tested against.
    fixture = ROOT / "web" / "src" / "lib" / "avatar.fixture.json"
    fixture.write_text(json.dumps(A.fixture(), separators=(",", ":")), encoding="utf-8")
    print(fixture)


if __name__ == "__main__":
    main()
