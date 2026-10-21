"""Entry point:  python -m curo_worker {worker|scheduler}"""

from __future__ import annotations

import argparse
import logging


def main() -> None:
    parser = argparse.ArgumentParser(prog="curo_worker")
    parser.add_argument("process", choices=["worker", "scheduler"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if args.process == "worker":
        from curo_worker.worker import run_worker

        run_worker()
    else:
        from curo_worker.scheduler import run_scheduler

        run_scheduler()


if __name__ == "__main__":
    main()
