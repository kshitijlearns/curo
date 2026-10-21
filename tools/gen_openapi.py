"""Write the API's OpenAPI document for the app's generated client.

    python tools/gen_openapi.py          # → web/src/api/openapi.json
    cd web && npm run gen:api            # → web/src/api/schema.d.ts (typed client)

`make api-types` runs both. The app's types come only from this file, so the app and
the API can't drift (MVP doc §7). (v2: the web app; the Expo app in legacy/app is frozen.)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "api"))

# Document every route, including the local sign-in stub, without reading a developer .env.
os.environ["CURO_ENV_FILE"] = ""
os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("APP_ENV", "development")

from curo.main import create_app  # noqa: E402

OUT = REPO / "web" / "src" / "api" / "openapi.json"


def main() -> None:
    spec = create_app().openapi()
    OUT.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({len(spec['paths'])} paths)")


if __name__ == "__main__":
    main()
