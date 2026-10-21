"""Unpack CURO_prototype.html into readable files under reference/prototype/.

The prototype is a self-contained "bundler" page, not plain HTML:

* ``<script type="__bundler/manifest">`` is JSON mapping asset IDs to
  ``{mime, compressed, data}``; ``data`` is base64, gzip-compressed when
  ``compressed`` is true.
* ``<script type="__bundler/template">`` is a JSON string holding the page shell.
* ``<script type="__bundler/page_order">`` lists asset IDs that are whole pages
  (each one is itself a nested bundle, shown in an iframe by the root shell).
* ``<script type="__bundler/ext_resources">`` maps resource names
  (e.g. ``./Nav.dc.html``) to asset IDs.

Each page's template contains an ``<x-dc>`` element (markup with ``sc-if`` /
``sc-for`` / ``{{value}}`` bindings) and a ``<script type="text/x-dc">`` holding
mock data and interaction logic. This script writes, per page:

    reference/prototype/pages/<slug>/bundle.html      standalone page (open in a browser)
    reference/prototype/pages/<slug>/template.html    decoded page template
    reference/prototype/pages/<slug>/markup.html      just the <x-dc> markup
    reference/prototype/pages/<slug>/logic.js         the text/x-dc script
    reference/prototype/pages/<slug>/components/      dc-import components (markup + logic)
    reference/prototype/pages/<slug>/assets/          every other asset, by ID

Usage:  python tools/extract_prototype.py [path/to/CURO_prototype.html] [out_dir]
Stdlib only, so it runs anywhere Python 3.10+ is installed.
"""

from __future__ import annotations

import base64
import gzip
import html
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_IN = REPO / "reference" / "CURO_prototype.html"
DEFAULT_OUT = REPO / "reference" / "prototype"

EXT_BY_MIME = {
    "text/html": "html",
    "text/javascript": "js",
    "application/javascript": "js",
    "text/css": "css",
    "application/json": "json",
    "image/svg+xml": "svg",
    "image/png": "png",
    "image/jpeg": "jpg",
    "font/woff2": "woff2",
    "font/woff": "woff",
    "font/ttf": "ttf",
}


def script_block(doc: str, script_type: str) -> str | None:
    """Return the text of the first <script type="..."> block, or None."""
    m = re.search(r'<script type="' + re.escape(script_type) + r'"[^>]*>(.*?)</script>', doc, re.S)
    return m.group(1) if m else None


def decode_asset(entry: dict) -> bytes:
    data = base64.b64decode(entry["data"])
    return gzip.decompress(data) if entry.get("compressed") else data


def slugify(text: str) -> str:
    text = text.lower().replace("—", " ").replace("·", " ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "page"


def split_template(template: str) -> tuple[str, str]:
    """Split a page template into (x-dc markup, text/x-dc logic script)."""
    markup = re.search(r"<x-dc>(.*?)</x-dc>", template, re.S)
    logic = re.search(r'<script type="text/x-dc"[^>]*>(.*?)</script>', template, re.S)
    return (markup.group(1).strip() if markup else "", logic.group(1).strip() if logic else "")


def page_titles(root_template: str) -> dict[str, str]:
    """Map page asset ID -> iframe title from the root shell."""
    titles = {}
    for m in re.finditer(
        r'<iframe src="about:blank#([0-9a-f-]{36})" title="([^"]*)"', root_template
    ):
        titles[m.group(1)] = html.unescape(m.group(2))
    return titles


def unpack_page(doc: str, out: Path) -> dict:
    """Unpack one page bundle (a full bundler HTML document) into ``out``."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "bundle.html").write_text(doc, encoding="utf-8")

    manifest = json.loads(script_block(doc, "__bundler/manifest") or "{}")
    template = json.loads(script_block(doc, "__bundler/template") or '""')
    ext_resources = json.loads(script_block(doc, "__bundler/ext_resources") or "[]")
    names = {r["uuid"]: r["id"] for r in ext_resources}

    (out / "template.html").write_text(template, encoding="utf-8")
    markup, logic = split_template(template)
    (out / "markup.html").write_text(markup, encoding="utf-8")
    (out / "logic.js").write_text(logic, encoding="utf-8")

    assets = []
    for asset_id, entry in manifest.items():
        data = decode_asset(entry)
        name = names.get(asset_id, "")
        component = re.fullmatch(r"\./(\w+)\.dc\.html", name)
        if component:
            # A dc-import component: keep its source plus split markup/logic.
            comp_dir = out / "components"
            comp_dir.mkdir(exist_ok=True)
            text = data.decode("utf-8")
            base = component.group(1)
            (comp_dir / f"{base}.html").write_text(text, encoding="utf-8")
            c_markup, c_logic = split_template(text)
            (comp_dir / f"{base}.markup.html").write_text(c_markup, encoding="utf-8")
            (comp_dir / f"{base}.logic.js").write_text(c_logic, encoding="utf-8")
            path = comp_dir / f"{base}.html"
        else:
            ext = EXT_BY_MIME.get(entry["mime"], "bin")
            path = out / "assets" / f"{asset_id}.{ext}"
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
        assets.append(
            {
                "id": asset_id,
                "mime": entry["mime"],
                "name": name,
                "bytes": len(data),
                "file": str(path.relative_to(out)).replace("\\", "/"),
            }
        )
    assets.sort(key=lambda a: -a["bytes"])
    (out / "assets.json").write_text(json.dumps(assets, indent=2), encoding="utf-8")
    return {"markup_chars": len(markup), "logic_chars": len(logic), "assets": len(assets)}


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IN
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    doc = src.read_text(encoding="utf-8")

    manifest = json.loads(script_block(doc, "__bundler/manifest"))
    root_template = json.loads(script_block(doc, "__bundler/template"))
    page_order = json.loads(script_block(doc, "__bundler/page_order") or "[]")
    titles = page_titles(root_template)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "root_template.html").write_text(root_template, encoding="utf-8")

    # The main screen is the largest HTML page; the others are component previews.
    pages = sorted(page_order, key=lambda pid: -len(manifest[pid]["data"]))
    summary = []
    for i, page_id in enumerate(pages):
        title = titles.get(page_id, page_id)
        slug = "main-screen" if i == 0 else slugify(title.split("·")[-1])
        page_doc = decode_asset(manifest[page_id]).decode("utf-8")
        info = unpack_page(page_doc, out / "pages" / slug)
        summary.append({"id": page_id, "title": title, "slug": slug, **info})
        print(f"  {slug:<22} {title}  ({info['assets']} assets)")

    (out / "index.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Unpacked {len(summary)} pages into {out}")


if __name__ == "__main__":
    main()
