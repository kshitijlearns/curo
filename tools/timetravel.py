"""Move CURO's clock for every process (API, worker, scheduler) at once.

    python tools/timetravel.py show
    python tools/timetravel.py set 2027-08-23T10:00+05:30 [--frozen]
    python tools/timetravel.py advance 6h        # also: 90m, 2d, 1w
    python tools/timetravel.py freeze | resume
    python tools/timetravel.py reset             # back to FAKE_NOW (or real time)

With Docker running:  make time ARGS="advance 6h"   (or ./dev.ps1 time advance 6h)
The clock lives in Redis, so this needs the same REDIS_URL as the stack.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from curo import clock

_UNITS = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def _redis_reachable() -> bool:
    from curo.redis_client import get_redis

    try:
        get_redis().ping()
        return True
    except Exception:
        return False


def parse_duration(text: str) -> timedelta:
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)([mhdw])", text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"bad duration {text!r}; use e.g. 90m, 6h, 2d, 1w")
    return timedelta(**{_UNITS[m.group(2)]: float(m.group(1))})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Move CURO's clock.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    p_set = sub.add_parser("set")
    p_set.add_argument("when", type=datetime.fromisoformat)
    p_set.add_argument("--frozen", action="store_true")
    p_adv = sub.add_parser("advance")
    p_adv.add_argument("by", type=parse_duration)
    sub.add_parser("freeze")
    sub.add_parser("resume")
    sub.add_parser("reset")
    args = parser.parse_args(argv)

    if args.cmd == "set":
        clock.set_time(args.when, frozen=args.frozen)
    elif args.cmd == "advance":
        clock.advance(args.by)
    elif args.cmd == "freeze":
        clock.set_time(clock.now(), frozen=True)
    elif args.cmd == "resume":
        clock.set_time(clock.now(), frozen=False)
    elif args.cmd == "reset":
        clock.reset()

    if args.cmd != "show" and not _redis_reachable():
        print(
            "warning: Redis not reachable; the change only applied to this process", file=sys.stderr
        )
    info = clock.describe()
    print(f"now:    {info['now']}")
    print(f"source: {info['source']}{' (frozen)' if info['frozen'] else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
