"""Re-embed every reel with the configured embedding model (D210).

    python tools/reembed.py            # dry run: how many rows would change
    python tools/reembed.py --apply    # re-embed, then rebuild sub-clusters (their centroids)

Never mix vectors from two models — or mock and real ones — in one table (MVP doc §5): when
GEMINI_EMBEDDING_MODEL (or EMBEDDING_PROVIDER) changes, run this once. It re-reads each reel's
stored understanding (T1) and caption, embeds in batches, records the model on every row, and
queues ``recompute_learning`` for each creator so sub-cluster centroids come from the new
vectors. It refuses to run unless the configured dimension is 768.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "api"))

BATCH = 64


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="write the new vectors")
    args = parser.parse_args()

    from curo import clock, providers
    from curo.config import get_settings
    from curo.db import service_connection
    from curo.jobs.understand import vector_literal
    from curo.queue import enqueue
    from curo.schemas.tasks import T1Output
    from curo.services import dna

    settings = get_settings()
    if settings.embedding_dim != 768:
        raise SystemExit("EMBEDDING_DIM must be 768 (the tables are vector(768)).")
    embedder = providers.get_embedding()
    model = embedder.model
    with service_connection() as conn:
        rows = conn.execute(
            """
            select r.id, r.caption, d.transcript, e.model
              from public.reels r
              join public.reel_dna d on d.reel_id = r.id
              left join public.reel_embeddings e on e.reel_id = r.id
             where d.transcript is not null
             order by r.id
            """
        ).fetchall()
    todo = [r for r in rows if r["model"] != model]
    print(f"{len(rows)} reels with an understanding; {len(todo)} not embedded with {model}")
    if not args.apply or not todo:
        if todo:
            print("dry run: add --apply to re-embed")
        return

    now = clock.now()
    for i in range(0, len(todo), BATCH):
        batch = todo[i : i + BATCH]
        texts = [
            dna.embedding_text(r["caption"] or "", T1Output.model_validate(r["transcript"]))
            for r in batch
        ]
        vectors = embedder.embed(texts)
        with service_connection() as conn:
            for r, v in zip(batch, vectors, strict=True):
                conn.execute(
                    """
                    insert into public.reel_embeddings (reel_id, embedding, model, created_at)
                    values (%s, %s::vector, %s, %s)
                    on conflict (reel_id) do update set embedding = excluded.embedding,
                      model = excluded.model, created_at = excluded.created_at
                    """,
                    (r["id"], vector_literal(v), model, now),
                )
        print(f"  {min(i + BATCH, len(todo))}/{len(todo)}")

    with service_connection() as conn:
        accounts = [
            r["account_id"]
            for r in conn.execute(
                "select account_id from public.creators where account_id is not null"
            ).fetchall()
        ]
    for account_id in accounts:
        enqueue(
            "recompute_learning",
            {"account_id": str(account_id)},
            idempotency_key=f"reembed:{account_id}:{now:%Y%m%dT%H%M}",
        )
    print(f"re-embedded {len(todo)} reels; queued learning for {len(accounts)} creators")


if __name__ == "__main__":
    main()
