"""Wait until the API answers /health, then print a one-screen summary.

    python tools/wait_for_api.py [http://localhost:8000] [--timeout 180]

Stdlib only, so it runs before the project's virtualenv exists.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", nargs="?", default="http://localhost:8000")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()

    deadline = time.monotonic() + args.timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{args.base}/health", timeout=5) as resp:
                body = json.load(resp)
            break
        except urllib.error.HTTPError as exc:  # 503: up, but a dependency isn't ready yet
            last_error = f"HTTP {exc.code}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2)
    else:
        print(f"API not healthy after {args.timeout:.0f}s ({last_error}).", file=sys.stderr)
        print("Check:  docker compose logs api", file=sys.stderr)
        return 1

    print(f"\nCURO API {body['version']} is {body['status']}  ({args.base}/health)")
    for name, check in body["checks"].items():
        mark = "ok " if check["ok"] else "-- "
        print(f"  {mark} {name:<10} {check['detail']}")
    print(f"  mock mode: {body['mock_mode']}   clock: {body['clock'].get('now')}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
