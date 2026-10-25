"""The Follower Persona avatar (v2.2 §2): a soft cluster of dots, the same everywhere.

One algorithm, two copies: this module (the share card and the plan's mood sketch) and
``web/src/lib/avatar.ts`` (the ``PersonaAvatar`` component). Both use the same seeded random
generator (mulberry32) and the same arithmetic, so a persona's avatar looks identical in the
app and on the share card; ``tests/test_persona_avatar.py`` and the web test compare both
against ``web/src/lib/avatar.fixture.json``.

Coordinates are in a 100 × 100 box centred on (50, 50). A mood moves, scales or dims the dots
(no faces): the static shape here is what reduced motion shows; the web adds the motion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

M32 = 0xFFFFFFFF
GOLDEN = math.pi * (3 - math.sqrt(5))  # the golden angle
CLUSTER_R = 31.0
RING_R = 47.0
DOT_R = (2.7, 3.7, 4.7)  # three dot sizes
MIN_DOTS, MAX_DOTS = 18, 40

# Persona colours, in order of share (v2.2 §2.1).
COLORS = ("blue", "lavender", "pink", "ink")
HEX = {
    "blue": "#5B73F2",
    "lavender": "#C3BFF2",
    "pink": "#F2D4E2",
    "ink": "#242424",
    "gray": "#E4E4EC",
}
RING = "#E4E4EC"
LIGHT = {"lavender", "pink", "gray"}  # need a hairline ring on white
MOODS = ("neutral", "love", "like", "unsure", "skip", "thinking", "listening")


def mulberry32(seed: int):
    """The same 32-bit generator as the web copy: floats in [0, 1)."""
    state = [seed & M32]

    def rand() -> float:
        state[0] = (state[0] + 0x6D2B79F5) & M32
        a = state[0]
        t = ((a ^ (a >> 15)) * (1 | a)) & M32
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & M32)) & M32) ^ t
        return ((t ^ (t >> 14)) & M32) / 4294967296

    return rand


@dataclass(frozen=True)
class Dot:
    x: float
    y: float
    r: float
    opacity: float


def dots(seed: int) -> list[Dot]:
    """18–40 dots of three sizes on a jittered sunflower spiral, denser and darker inside."""
    rand = mulberry32(seed)
    n = MIN_DOTS + int(rand() * (MAX_DOTS - MIN_DOTS + 1))
    turn = rand() * 2 * math.pi
    out = []
    for i in range(n):
        t = (i + 0.5) / n
        dist = CLUSTER_R * math.sqrt(t) * (0.92 + 0.16 * rand())
        angle = turn + i * GOLDEN + (rand() - 0.5) * 0.6
        u = rand()
        size = DOT_R[0] if u < 0.45 else DOT_R[1] if u < 0.8 else DOT_R[2]
        opacity = 0.4 + 0.6 * ((1 - t) * 0.6 + rand() * 0.4)
        out.append(
            Dot(
                x=round(50 + dist * math.cos(angle), 2),
                y=round(50 + dist * math.sin(angle), 2),
                r=size,
                opacity=round(opacity, 2),
            )
        )
    return out


@dataclass(frozen=True)
class Placed:
    x: float
    y: float
    r: float
    opacity: float


def place(d: Dot, mood: str) -> Placed:
    """Where a dot sits in a mood (the static shape; the web animates between them)."""
    dx = dy = 0.0
    scale, fade = 1.0, 1.0
    nx = (d.x - 50) / CLUSTER_R
    if mood == "love":  # an upward arc: the cluster flattens and its middle lifts
        dy = (d.y - 50) * -0.3 - 8 * max(0.0, 1 - nx * nx) + 2
    elif mood == "like":  # a slight lift
        dy, scale = -5, 1.04
    elif mood == "unsure":  # spread out
        dx, dy, fade = (d.x - 50) * 0.25, (d.y - 50) * 0.25, 0.85
    elif mood == "skip":  # drift sideways, shrink and dim
        dx, dy, scale, fade = 12, 3, 0.85, 0.45
    elif mood == "thinking":  # pulled into a ring (the web orbits it)
        dist = math.hypot(d.x - 50, d.y - 50) or 1.0
        target = 0.35 * dist + 0.65 * 24
        dx, dy = (d.x - 50) * (target / dist - 1), (d.y - 50) * (target / dist - 1)
    elif mood == "listening":
        scale = 0.92
    x = 50 + (d.x + dx - 50) * scale
    y = 50 + (d.y + dy - 50) * scale
    return Placed(round(x, 2), round(y, 2), round(d.r * scale, 2), round(d.opacity * fade, 2))


def svg_group(seed: int, color: str, mood: str = "neutral", ring: bool | None = None) -> str:
    """The avatar's circles in its 100 × 100 box (wrap it in a translate/scale to place it)."""
    fill = HEX.get(color, HEX["blue"])
    parts = []
    if ring if ring is not None else color in LIGHT:
        parts.append(
            f'<circle cx="50" cy="50" r="{RING_R}" fill="none" stroke="{RING}" stroke-width="1.2"/>'
        )
    light = color in LIGHT
    for d in dots(seed):
        p = place(d, mood)
        # Light dots are faint on white: their opacity range is lifted, as in the web component.
        op = round(0.6 + 0.4 * p.opacity, 2) if light else p.opacity
        parts.append(f'<circle cx="{p.x}" cy="{p.y}" r="{p.r}" fill="{fill}" fill-opacity="{op}"/>')
    return "".join(parts)


def svg(seed: int, color: str, mood: str = "neutral", size: int = 120) -> str:
    """A standalone avatar SVG."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 100 100" role="img">{svg_group(seed, color, mood)}</svg>'
    )


FIXTURE_SEEDS = (1, 42, 123456, 2147483647, 987654321)


def fixture() -> dict:
    """Dots and every mood's pose for a few seeds (web/src/lib/avatar.fixture.json)."""
    out: dict = {"seeds": {}}
    for s in FIXTURE_SEEDS:
        ds = dots(s)
        out["seeds"][str(s)] = {
            "dots": [[d.x, d.y, d.r, d.opacity] for d in ds],
            "moods": {
                m: [[p.x, p.y, p.r, p.opacity] for p in (place(d, m) for d in ds)] for m in MOODS
            },
        }
    return out


def seed_for(creator_id: object, slot: int, salt: str = "") -> int:
    """A stable 31-bit seed for a new persona (kept across months once matched)."""
    import hashlib

    h = hashlib.sha256(f"{creator_id}|{slot}|{salt}".encode()).hexdigest()
    return int(h[:8], 16) & 0x7FFFFFFF
