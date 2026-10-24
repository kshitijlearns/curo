"""The recap share card (v2.1 §3.7): a 1080×1920 SVG in CURO's colours, drawn on the server.

The web app turns it into a PNG in the browser (canvas) for Share and Download (D217). It
carries the handle, the period, 3–4 headline stats, the creator level and archetype, and a
small CURO mark and URL — never another person's comment or handle.
"""

from __future__ import annotations

from html import escape

from curo.services.recap_config import COLOURS

W, H = 1080, 1920
FONT = "Figtree, 'Segoe UI', Arial, sans-serif"


def _text(x, y, s, size, weight=600, fill=COLOURS["ink"], anchor="start") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}">{escape(str(s))}</text>'
    )


def _wrap(s: str, width: int) -> list[str]:
    words, lines, line = s.split(), [], ""
    for w in words:
        if len(line) + len(w) + 1 > width and line:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        lines.append(line)
    return lines


def svg(
    handle: str,
    period: str,
    stats: list[dict],
    level: str | None,
    modifier: str | None,
    archetype: str | None,
    web_url: str,
) -> str:
    c = COLOURS
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{c["lavender"]}"/>',
        # Palette shapes (no gradients)
        f'<circle cx="960" cy="180" r="150" fill="{c["pink"]}"/>',
        f'<circle cx="1010" cy="1850" r="170" fill="{c["blue"]}"/>',
        f'<rect x="720" y="1800" width="90" height="90" rx="26" fill="{c["white"]}"/>',
        _text(90, 200, "Creator Recap", 52, 600),
        _text(90, 290, f"@{handle}", 76, 600),
        _text(90, 360, period[:1].upper() + period[1:], 44, 400),
    ]
    y = 470
    for s in stats[:4]:
        parts.append(f'<rect x="90" y="{y}" width="900" height="210" rx="48" fill="{c["white"]}"/>')
        parts.append(_text(150, y + 125, s["value"], 96, 600, c["blue"]))
        parts.append(_text(150, y + 178, s["label"], 38, 400))
        y += 240
    y = max(y, 1200) + 40
    parts.append(f'<rect x="90" y="{y}" width="900" height="300" rx="48" fill="{c["ink"]}"/>')
    parts.append(_text(150, y + 80, "You're", 40, 400, c["lavender"]))
    lines = _wrap(" · ".join(x for x in (level, archetype) if x), 26)[:2]
    for i, line in enumerate(lines):
        parts.append(_text(150, y + 150 + i * 70, line, 60, 600, c["white"]))
    if modifier:
        parts.append(_text(150, y + 270, modifier, 36, 400, c["pink"]))
    parts.append(_text(90, 1830, "CURO", 56, 600))
    parts.append(_text(90, 1880, web_url, 32, 400))
    parts.append("</svg>")
    return "".join(parts)
