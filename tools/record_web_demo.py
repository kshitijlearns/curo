"""Record the web app's demo: the demo creator's journey, answered by the local API.

    ./dev.ps1 local --seed          # in one terminal
    python tools/record_web_demo.py # writes web/public/demo/fixtures.json

The web app plays these back when it is deployed without a backend (demo mode, D211):
every screen shows real CURO output — Home (with the Follower Personas), an opportunity, the
Studio steps with the personas' reactions, the Simulator with its AI audience and an agent
chat, persona chats, Saved and Settings — from the synthetic @curo.demo dataset. Nothing here
is a real person's data.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[1] / "web" / "public" / "demo" / "fixtures.json"
EMAIL = "demo@curo.local"
TOKEN = ""


def call(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"{API}/v1{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=300) as res:
        raw = res.read()
        if res.headers.get_content_type() == "image/svg+xml":
            return raw.decode("utf-8")
        return json.loads(raw) if raw else None


def wait(job_id: str) -> None:
    for _ in range(600):
        job = call("GET", f"/jobs/{job_id}")
        if job["status"] in ("succeeded", "failed"):
            if job["status"] == "failed":
                raise SystemExit(f"job failed: {job['error']}")
            return
        time.sleep(0.5)
    raise SystemExit("job timed out")


def persona_chat(persona_id: str, message: str) -> str:
    """The persona's whole answer from its event stream."""
    req = urllib.request.Request(
        f"{API}/v1/personas/{persona_id}/chat",
        data=json.dumps({"message": message}).encode(),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=300) as res:
        raw = res.read().decode("utf-8")
    for block in raw.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if lines.get("event") == "done":
            return json.loads(lines["data"])["text"]
    return ""


def main() -> None:
    global TOKEN
    code = call("POST", "/auth/otp", {"email": EMAIL})["dev_code"]
    TOKEN = call("POST", "/auth/verify", {"email": EMAIL, "code": code})["access_token"]

    fx: dict = {"get": {}}
    get = fx["get"]

    def keep(path: str):
        get[path] = call("GET", path)
        return get[path]

    keep("/me")
    keep("/home")
    # v2.2: the Follower Personas, each one's detail sheet.
    personas = keep("/personas")["personas"]
    for p in personas:
        keep(f"/personas/{p['id']}")
    opps = keep("/opportunities")
    for o in opps:
        keep(f"/opportunities/{o['id']}")
    keep("/trends")
    keep("/memory")
    keep("/uploads/samples")
    fx["billing_free"] = call("GET", "/billing")
    # Enough credits for the recording; the demo shows the Free plan above.
    call("POST", "/billing/checkout", {"item": "pro"})

    fx["validate"] = call(
        "POST", "/ideas/validate", {"text": "Three ways to drape one dupatta for Ganpati"}
    )

    # Studio: a project from the top opportunity, every step.
    started = call("POST", "/projects", {"opportunity_id": opps[0]["id"]})
    wait(started["job_id"])
    pid = started["project_id"]
    fx["project_started"] = started
    stages = fx["project_stages"] = {}
    stages["ideas"] = call("GET", f"/projects/{pid}")
    reactions = fx["persona_reactions"] = {}
    for i, one in enumerate(stages["ideas"]["rounds"][-1]["ideas"]):
        r = call(
            "POST",
            f"/projects/{pid}/persona-reactions",
            {"target_type": "idea", "target_id": one["id"]},
        )
        reactions[f"idea:{one['id']}"] = r
        if i == 0:
            reactions["ideas"] = r
    idea = stages["ideas"]["rounds"][-1]["ideas"][0]
    call("POST", f"/projects/{pid}/ideas/{idea['id']}/select", {})
    wait(
        call("POST", f"/projects/{pid}/script", {"direction": None, "regenerate": False})["job_id"]
    )
    stages["script"] = call("GET", f"/projects/{pid}")
    reactions["script"] = call(
        "POST", f"/projects/{pid}/persona-reactions", {"target_type": "script"}
    )
    wait(call("POST", f"/projects/{pid}/storyboard", {})["job_id"])
    stages["storyboard"] = call("GET", f"/projects/{pid}")
    reactions["storyboard"] = call(
        "POST", f"/projects/{pid}/persona-reactions", {"target_type": "storyboard"}
    )
    wait(call("POST", f"/projects/{pid}/captions", {})["job_id"])
    call("PUT", f"/projects/{pid}/caption", {"chosen": 2})
    stages["caption"] = call("GET", f"/projects/{pid}")
    reactions["caption"] = call(
        "POST", f"/projects/{pid}/persona-reactions", {"target_type": "caption"}
    )

    # Simulator: the first take, then the re-recorded take as a re-run.
    sims = fx["simulations"] = {}
    take1 = call("POST", "/uploads/sample", {"name": "take1"})
    s1 = call(
        "POST",
        "/simulations",
        {"upload_path": take1["path"], "caption": take1["caption"], "project_id": pid,
         "audience": "both"},
    )  # fmt: skip
    wait(s1["job_id"])
    sims["take1"] = call("GET", f"/simulations/{s1['simulation_id']}")
    take2 = call("POST", "/uploads/sample", {"name": "take2"})
    s2 = call(
        "POST",
        f"/simulations/{s1['simulation_id']}/rerun",
        {"upload_path": take2["path"], "caption": take2["caption"]},
    )
    wait(s2["job_id"])
    sims["take2"] = call("GET", f"/simulations/{s2['simulation_id']}")

    agents = fx["agents"] = {}
    replies = fx["agent_replies"] = {}
    questions = [
        "Why did you stop watching?",
        "What would make you share this?",
        "What should I change?",
    ]
    for key, sim in sims.items():
        comments = (sim["result"].get("audience") or {}).get("comments") or []
        for c in comments[:12]:
            no = c["agent_no"]
            agents[f"{sim['id']}:{no}"] = call("GET", f"/simulations/{sim['id']}/agents/{no}")
        if comments and key == "take1":
            no = comments[0]["agent_no"]
            for q in questions:
                out = call("POST", f"/simulations/{sim['id']}/agents/{no}/chat", {"message": q})
                replies[q] = out["answer"]

    # Persona chat: a recorded answer per kind of question, per persona.
    chats = fx["persona_chat"] = {}
    asks = {
        "next": "What do you want next?",
        "why": "Why do you scroll past?",
        "share": "What would make you share a reel?",
        "honest": "How many of you are there exactly?",
    }
    for p in personas:
        chats[p["id"]] = {k: persona_chat(p["id"], q) for k, q in asks.items()}

    keep("/saved")
    # v2.1: the Creator Recap (first + any monthly) and its share card.
    fx["recaps"] = call("GET", "/recaps")
    fx["recap"] = {}
    fx["share_image"] = {}
    for r in fx["recaps"]:
        fx["recap"][r["id"]] = call("GET", f"/recaps/{r['id']}")
        fx["share_image"][r["id"]] = call("GET", f"/recaps/{r['id']}/share-image")
    first = next((r for r in fx["recaps"] if r["kind"] == "first"), None)
    fx["first_recap_id"] = first["id"] if first else None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fx, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
