"""Creator memory (logic doc §14): stable preferences, stated ("never suggest dance trends") or
learned from repeated behaviour (always shortens scripts, so drafts start shorter). The
creator sees and deletes them in Settings; a deleted learned preference isn't learned again.

What CURO does with them is enforced in code, not left to a model: an "avoid" preference
filters the Studio's idea candidates, and the shorter-scripts preference sets the length a new
script is planned at. Every memory also goes to Ask Curo as context.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from curo import clock

# "never suggest dance trends", "don't show me haul ideas", "no more GRWMs", "avoid politics"
AVOID = re.compile(
    r"\b(?:never|don'?t|do not|stop)(?: ever)?\s+(?:suggest|show|give|recommend)(?:ing)?"
    r"(?:\s+me)?\s+(?P<a>.+)"
    r"|\bno more\s+(?P<b>.+)"
    r"|\bavoid(?:ing)?\s+(?P<c>.+)"
    r"|\bi (?:hate|don'?t like|don'?t do|never do|won'?t do)\s+(?P<d>.+)",
    re.I,
)
SHORTER = re.compile(
    r"\b(shorter|short|brief|tight|quick)\s+(scripts?|reels?|videos?)\b"
    r"|\bkeep (it|them|scripts?|reels?) (short|tight|brief)\b",
    re.I,
)
LEAD = re.compile(
    r"^\s*(?:please\s+)?(?:remember|note|keep in mind)(?:\s+that)?[:,]?\s*|^\s*from now on[:,]?\s*",
    re.I,
)
# Words that say what kind of thing, not what it's about ("dance trends" avoids "dance").
GENERIC = {
    "trend", "trends", "trending", "reel", "reels", "idea", "ideas", "video", "videos",
    "content", "post", "posts", "anything", "stuff", "any", "more", "please", "the", "a", "an",
    "me", "my", "of", "with", "for", "about", "to", "and", "or", "kind", "type", "types", "like",
    "that", "this", "those", "these", "again", "ever", "format", "formats",
}  # fmt: skip

LEARNED_SHORTER = "learned:shorter_scripts"
SHORTER_MIN = 3  # shortened at least 3 times…
SHORTER_SHARE = 0.5  # …in at least half of the latest script changes
RECENT_CHANGES = 6


@dataclass(frozen=True)
class Memory:
    id: UUID
    key: str
    value: str
    source: str  # "stated" | "learned"


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z'’-]+", text.lower()) if w not in GENERIC]


def note_from(message: str) -> str:
    """The preference as it will be shown: the creator's words without "remember that"."""
    text = LEAD.sub("", message.strip()).strip().rstrip(".!")
    return (text[:1].upper() + text[1:])[:200] if text else ""


def avoided(value: str) -> list[str]:
    """What an "avoid" preference names, as words to keep out of ideas ([] if it isn't one)."""
    m = AVOID.search(value)
    if not m:
        return []
    what = next(g for g in m.groups() if g)
    what = re.split(r"[.,;!?]| because | since ", what, maxsplit=1)[0]
    return _words(what)[:4]


def key_for(value: str) -> str:
    words = avoided(value)
    if words:
        return "avoid:" + "-".join(words)
    if SHORTER.search(value):
        return "prefer:shorter_scripts"
    return "note:" + "-".join(_words(value)[:6] or ["note"])


# ------------------------------------------------------------------ reading and writing


def load(conn, creator_id: UUID) -> list[Memory]:
    rows = conn.execute(
        """
        select id, key, value, source from public.creator_memory
         where creator_id = %s order by created_at, key
        """,
        (creator_id,),
    ).fetchall()
    return [Memory(r["id"], r["key"], r["value"], r["source"]) for r in rows]


def save_stated(conn, creator_id: UUID, message: str) -> Memory | None:
    value = note_from(message)
    if not value:
        return None
    row = conn.execute(
        """
        insert into public.creator_memory (creator_id, key, value, source, created_at)
        values (%s, %s, %s, 'stated', %s)
        on conflict (creator_id, key) do update set value = excluded.value, source = 'stated'
        returning id, key, value, source
        """,
        (creator_id, key_for(value), value, clock.now()),
    ).fetchone()
    return Memory(row["id"], row["key"], row["value"], row["source"])


def forget(conn, creator_id: UUID, query: str) -> list[Memory]:
    """Delete the memories the request names (by shared words); with none named, the newest."""
    memories = load(conn, creator_id)
    words = set(_words(re.sub(r"^\s*(please\s+)?forget(\s+(that|about))?", "", query, flags=re.I)))
    words -= {"forget", "memory", "remember", "remembered", "delete", "note", "preference"}
    hits = [m for m in memories if words & set(_words(m.value))] if words else memories[-1:]
    for m in hits:
        delete(conn, creator_id, m.id)
    return hits


def delete(conn, creator_id: UUID, memory_id: UUID) -> Memory | None:
    row = conn.execute(
        """
        delete from public.creator_memory where id = %s and creator_id = %s
        returning id, key, value, source
        """,
        (memory_id, creator_id),
    ).fetchone()
    if row is None:
        return None
    if row["source"] == "learned":  # deleted by the creator: don't learn it again
        conn.execute(
            """
            update public.creators set memory_dismissed = array_append(memory_dismissed, %s)
             where id = %s and not (%s = any(memory_dismissed))
            """,
            (row["key"], creator_id, row["key"]),
        )
    return Memory(row["id"], row["key"], row["value"], row["source"])


# ------------------------------------------------------------------ what CURO does with them


def avoided_words(memories: Iterable[Memory]) -> set[str]:
    out: set[str] = set()
    for m in memories:
        if m.key.startswith("avoid:"):
            out.update(avoided(m.value) or m.key.removeprefix("avoid:").split("-"))
    return out


def mentions(text: str, words: set[str]) -> str | None:
    """The avoided word a text uses (singular or plural), if any."""
    found = set(re.findall(r"[a-z][a-z'’-]+", text.lower()))
    for w in sorted(words):
        stem = w.rstrip("s")
        if found & {w, stem, stem + "s", stem + "es", stem + "ing"}:
            return w
    return None


def prefers_shorter(memories: Iterable[Memory]) -> bool:
    return any(m.key in (LEARNED_SHORTER, "prefer:shorter_scripts") for m in memories)


# ------------------------------------------------------------------ learned from behaviour


def learned(actions: list[str]) -> list[tuple[str, str]]:
    """Preferences shown by repeated behaviour. ``actions`` are the creator's latest script
    changes, newest first ("shorten", "rewrite_hook", …)."""
    recent = actions[:RECENT_CHANGES]
    n = sum(1 for a in recent if a == "shorten")
    if n >= SHORTER_MIN and n / len(recent) >= SHORTER_SHARE:
        return [
            (
                LEARNED_SHORTER,
                f"Starts scripts shorter: you shortened {n} of your last {len(recent)} script "
                "changes.",
            )
        ]
    return []


def save_learned(conn, creator_id: UUID) -> list[str]:
    """Learn from the creator's latest script changes; keep what they deleted forgotten."""
    actions = [
        r["action"]
        for r in conn.execute(
            """
            select result->>'action' as action from public.jobs
             where creator_id = %s and type = 'studio' and status = 'succeeded'
               and payload->>'action' = 'script_revise' and result ? 'action'
             order by created_at desc limit %s
            """,
            (creator_id, RECENT_CHANGES),
        ).fetchall()
    ]
    dismissed = conn.execute(
        "select memory_dismissed from public.creators where id = %s", (creator_id,)
    ).fetchone()
    skip = set(dismissed["memory_dismissed"] if dismissed else [])
    saved = []
    for key, value in learned(actions):
        if key in skip:
            continue
        conn.execute(
            """
            insert into public.creator_memory (creator_id, key, value, source, created_at)
            values (%s, %s, %s, 'learned', %s)
            on conflict (creator_id, key) do update set value = excluded.value
             where public.creator_memory.source = 'learned'
            """,
            (creator_id, key, value, clock.now()),
        )
        saved.append(key)
    return saved
