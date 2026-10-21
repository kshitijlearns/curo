"""Record real vendor and model responses for the contract tests (MVP doc §4 and §12: "Record
real API responses once and replay them in tests, so tests never call Apify or the AI
providers").

Run it only once the keys are in .env; it calls the real services and costs a little.

    python tools/record_contracts.py apify reels --account your.test.account --input '{"username": ["your.test.account"], "resultsLimit": 12}'
    python tools/record_contracts.py apify hashtag --tag ganpatioutfit --input '{"hashtags": ["ganpatioutfit"], "resultsLimit": 30}'
    python tools/record_contracts.py gemini-video path/to/your-reel.mp4
    python tools/record_contracts.py gemini-embed "One kurta, five dupattas" "3 mistakes ruining your aesthetic reel"
    python tools/record_contracts.py claude T3                 # its captured inputs (see below)
    python tools/record_contracts.py claude --all              # every task with captured inputs
    python tools/record_contracts.py check                     # replay every recording

Each recording lands in ``api/tests/contracts/<kind>/<name>.json`` and is replayed by
``api/tests/test_contracts.py`` through the real provider's parser
(``curo.providers.contracts``).

Inputs for Claude: set ``CAPTURE_TASK_INPUTS=.data/task-inputs`` in .env and run the demo
(``./dev.ps1 local --seed`` or ``make seed``) and the Studio once; every AI task saves its first
few inputs there. The recorder sends those inputs to the real model.

Privacy: record only your own test account. Handles of anyone else in a response (commenters,
other creators on a hashtag page) are replaced with placeholders before the file is written,
and @mentions in text are masked, so recordings never carry other people's handles.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "api"))
CONTRACTS = REPO / "api" / "tests" / "contracts"

APIFY = "https://api.apify.com/v2"
GEMINI = "https://generativelanguage.googleapis.com"
APIFY_ACTOR_SETTING = {
    "profile": "apify_profile_actor_id",
    "reels": "apify_reels_actor_id",
    "comments": "apify_comments_actor_id",
    "hashtag": "apify_hashtag_actor_id",
}

# Keys that carry a person's handle or name in vendor items.
HANDLE_KEYS = {
    "ownerusername",
    "owner_username",
    "username",
    "authorusername",
    "author",
    "fullname",
    "full_name",
    "ownerfullname",
    "profilepicurl",
    "profile_pic_url",
    "ownerprofilepicurl",
}
MENTION = re.compile(r"@([A-Za-z0-9._]{1,30})")


# ------------------------------------------------------------------------------ privacy


class Scrubber:
    """Replace every handle except the account being recorded with a stable placeholder."""

    def __init__(self, own: str | None):
        self.own = (own or "").lstrip("@").lower()
        self.seen: dict[str, str] = {}

    def _name(self, value: str) -> str:
        if value.lstrip("@").lower() == self.own:
            return value
        return self.seen.setdefault(value, f"user_{len(self.seen) + 1}")

    def __call__(self, item: Any) -> Any:
        if isinstance(item, list):
            return [self(v) for v in item]
        if isinstance(item, dict):
            out = {}
            for key, value in item.items():
                if key.lower() in HANDLE_KEYS and isinstance(value, str) and value:
                    out[key] = self._name(value) if "pic" not in key.lower() else ""
                elif isinstance(value, str) and key.lower() in ("text", "caption"):
                    out[key] = MENTION.sub(lambda m: "@" + self._name(m.group(1)), value)
                else:
                    out[key] = self(value)
            return out
        return item


# ------------------------------------------------------------------------------ files


def write_recording(
    kind: str,
    name: str | None,
    source: dict[str, Any],
    request: dict[str, Any],
    response: Any,
    root: Path = CONTRACTS,
) -> Path:
    stamp = datetime.now(UTC)
    folder = root / kind
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name or stamp.strftime('%Y%m%d-%H%M%S')}.json"
    record = {
        "kind": kind,
        "recorded_at": stamp.isoformat(timespec="seconds"),
        "source": source,
        "request": request,
        "response": response,
    }
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"recorded {path.relative_to(REPO) if path.is_relative_to(REPO) else path}")
    return path


def _settings():
    from curo.config import get_settings

    return get_settings()


def _need(value: str, name: str) -> str:
    if not value:
        raise SystemExit(f"{name} is empty: add it to .env first (docs/INTEGRATION.md).")
    return value


# ------------------------------------------------------------------------------ Apify


def record_apify(
    method: str,
    actor_input: dict[str, Any],
    tag: str | None,
    name: str | None,
    build: str | None,
    account: str | None,
) -> Path:
    import httpx

    s = _settings()
    token = _need(s.apify_token, "APIFY_TOKEN")
    actor = _need(getattr(s, APIFY_ACTOR_SETTING[method]), APIFY_ACTOR_SETTING[method].upper())
    params = {"timeout": 300, **({"build": build} if build else {})}
    res = httpx.post(
        f"{APIFY}/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items",
        params=params,
        json=actor_input,
        headers={"Authorization": f"Bearer {token}"},
        timeout=330,
    )
    res.raise_for_status()
    items = res.json()
    request = {
        "actor": actor,
        "build": build,
        "input": actor_input,
        **({"tag": tag} if tag else {}),
    }
    return write_recording(
        f"public_data/apify/{method}",
        name,
        {"vendor": "apify", "actor": actor, "build": build},
        request,
        Scrubber(account)(items),
    )


# ------------------------------------------------------------------------------ Gemini


def record_gemini_video(path: Path, mime: str, name: str | None) -> Path:
    import httpx

    from curo import prompts
    from curo.schemas.tasks import T1, T1Output

    s = _settings()
    key = _need(s.gemini_api_key, "GEMINI_API_KEY")
    model = _need(s.gemini_video_model, "GEMINI_VIDEO_MODEL").removeprefix("models/")
    data = path.read_bytes()
    auth = {"x-goog-api-key": key}
    with httpx.Client(timeout=300) as http:
        start = http.post(
            f"{GEMINI}/upload/v1beta/files",
            headers={
                **auth,
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(len(data)),
                "X-Goog-Upload-Header-Content-Type": mime,
            },
            json={"file": {"display_name": path.name}},
        )
        start.raise_for_status()
        uploaded = http.post(
            start.headers["x-goog-upload-url"],
            headers={"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"},
            content=data,
        )
        uploaded.raise_for_status()
        file = uploaded.json()["file"]
        try:
            while file.get("state") == "PROCESSING":
                time.sleep(3)
                file = http.get(f"{GEMINI}/v1beta/{file['name']}", headers=auth).json()
            if file.get("state") != "ACTIVE":
                raise SystemExit(f"Gemini couldn't process the video: {file.get('state')}")
            body = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"file_data": {"mime_type": mime, "file_uri": file["uri"]}},
                            {"text": prompts.load(T1)},
                        ],
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": T1Output.model_json_schema(),
                },
            }
            res = http.post(
                f"{GEMINI}/v1beta/models/{model}:generateContent", headers=auth, json=body
            )
            res.raise_for_status()
            raw = res.json()
        finally:
            http.delete(f"{GEMINI}/v1beta/{file['name']}", headers=auth)
    request = {"file": path.name, "mime_type": mime, "prompt": T1.prompt_file}
    return write_recording("video/gemini", name, {"vendor": "gemini", "model": model}, request, raw)


def record_gemini_embed(texts: list[str], name: str | None) -> Path:
    import httpx

    s = _settings()
    key = _need(s.gemini_api_key, "GEMINI_API_KEY")
    model = _need(s.gemini_embedding_model, "GEMINI_EMBEDDING_MODEL").removeprefix("models/")
    body = {
        "requests": [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": t}]},
                "outputDimensionality": s.embedding_dim,
            }
            for t in texts
        ]
    }
    res = httpx.post(
        f"{GEMINI}/v1beta/models/{model}:batchEmbedContents",
        headers={"x-goog-api-key": key},
        json=body,
        timeout=60,
    )
    res.raise_for_status()
    return write_recording(
        "embedding/gemini",
        name,
        {"vendor": "gemini", "model": model},
        {"texts": texts, "dim": s.embedding_dim},
        res.json(),
    )


# ------------------------------------------------------------------------------ Claude


def _captured(task_id: str) -> list[Path]:
    root = _settings().capture_task_inputs or ".data/task-inputs"
    folder = (Path(root) if Path(root).is_absolute() else REPO / root) / task_id
    return sorted(folder.glob("*.json"))


def record_claude(task_id: str, inputs: list[Path], name: str | None) -> list[Path]:
    """Send captured task inputs to the real model, as the Claude provider will
    (structured output for T2–T15, a tool turn for T14), and record the raw messages."""
    try:
        import anthropic
    except ImportError:
        raise SystemExit('The Anthropic SDK is missing: pip install -e "api[live]"') from None

    from curo import prompts
    from curo.providers.llm import claude
    from curo.schemas.tasks import TASKS

    s = _settings()
    task = TASKS[task_id]
    model = s.claude_model_fast if task.tier == "fast" else s.claude_model_main
    # An empty key lets the SDK find credentials itself (env var, `ant auth login` profile).
    client = anthropic.Anthropic(api_key=s.anthropic_api_key or None)
    out = []
    for i, path in enumerate(inputs, 1):
        data = task.input.model_validate_json(path.read_text(encoding="utf-8"))
        try:
            if task_id == "T14":
                message = client.messages.create(
                    model=model,
                    max_tokens=16000,
                    system=claude.chat_system(data, prompts.load(task)),
                    tools=claude.to_claude_tools(data),
                    messages=claude.to_claude_messages(data),
                )
            else:
                message = client.messages.parse(
                    model=model,
                    max_tokens=16000,
                    system=prompts.load(task),
                    messages=[{"role": "user", "content": data.model_dump_json()}],
                    output_format=task.output,
                )
        except anthropic.RateLimitError as exc:
            print(f"{task_id} {path.name}: rate limited ({exc.message}); try again later")
            break
        except anthropic.APIStatusError as exc:
            print(f"{task_id} {path.name}: the API answered {exc.status_code}: {exc.message}")
            continue
        except anthropic.APIConnectionError:
            print(f"{task_id} {path.name}: couldn't reach the API; check the connection")
            break
        raw = message.to_dict()
        if raw.get("stop_reason") == "refusal":
            print(f"{task_id} {path.name}: the model declined; not recorded")
            continue
        label = f"{name}-{i}" if name else f"{path.stem}-{datetime.now(UTC):%Y%m%d-%H%M%S}"
        out.append(
            write_recording(
                f"llm/claude/{task_id}",
                label,
                {"vendor": "anthropic", "model": model, "request_id": message._request_id},
                {"task": task.tag, "input_file": path.name, "prompt": task.prompt_file},
                raw,
            )
        )
    return out


# ------------------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("apify", help="run an Apify actor and record its dataset items")
    p.add_argument("method", choices=sorted(APIFY_ACTOR_SETTING))
    p.add_argument("--input", required=True, help="the actor's input, as JSON")
    p.add_argument("--tag", help="the hashtag (for the hashtag method)")
    p.add_argument("--build", help="the actor build or version tag to pin")
    p.add_argument("--account", help="your test account's handle: kept; all others replaced")
    p.add_argument("--name")

    p = sub.add_parser("gemini-video", help="watch one video with Gemini (T1)")
    p.add_argument("file", type=Path)
    p.add_argument("--mime", default="video/mp4")
    p.add_argument("--name")

    p = sub.add_parser("gemini-embed", help="embed a few texts with Gemini")
    p.add_argument("texts", nargs="+")
    p.add_argument("--name")

    p = sub.add_parser("claude", help="send captured task inputs to Claude")
    p.add_argument("task", nargs="?", help="T2 … T15 (not T1, which is Gemini)")
    p.add_argument("--input", type=Path, action="append", help="a task input JSON file")
    p.add_argument("--all", action="store_true", help="every task with captured inputs")
    p.add_argument("--name")

    sub.add_parser("check", help="replay every recording through the parsers")

    args = parser.parse_args(argv)
    if args.cmd == "apify":
        record_apify(
            args.method, json.loads(args.input), args.tag, args.name, args.build, args.account
        )
    elif args.cmd == "gemini-video":
        record_gemini_video(args.file, args.mime, args.name)
    elif args.cmd == "gemini-embed":
        record_gemini_embed(args.texts, args.name)
    elif args.cmd == "claude":
        from curo.schemas.tasks import TASKS

        tasks = [t for t in TASKS if t != "T1"] if args.all else [args.task]
        if not tasks or tasks == [None] or any(t not in TASKS or t == "T1" for t in tasks):
            raise SystemExit("Name a task from T2 to T15, or pass --all.")
        for task_id in tasks:
            inputs = args.input or _captured(task_id)[: 1 if args.all else None]
            if not inputs:
                print(f"{task_id}: no inputs (set CAPTURE_TASK_INPUTS and run the demo first)")
                continue
            record_claude(task_id, inputs, args.name)
    else:
        return subprocess.call(
            [sys.executable, "-m", "pytest", "tests/test_contracts.py", "-v"], cwd=REPO / "api"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
