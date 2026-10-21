"""Phase 8 done-when: answers cite real records; a planted made-up number is caught — through
POST /v1/chat on the seeded demo, with the real tools and the mock model."""

import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from curo import clock, providers
from curo.db import creator_session, service_connection
from curo.main import create_app
from curo.providers.llm.mock import MockLLMProvider
from curo.providers.public_data.mock import MockPublicDataProvider
from curo.schemas.tasks import ChatChunk
from curo.services import validator
from curo.services.assistant import memory
from curo.services.assistant import tools as T

pytestmark = pytest.mark.db
ANCHOR = MockPublicDataProvider().anchor


def signed_in(email: str) -> TestClient:
    client = TestClient(create_app())
    code = client.post("/v1/auth/otp", json={"email": email}).json()["dev_code"]
    token = client.post("/v1/auth/verify", json={"email": email, "code": code}).json()
    client.headers["Authorization"] = f"Bearer {token['access_token']}"
    return client


@pytest.fixture
def demo(demo_db):
    with clock.frozen_at(ANCHOR):
        yield signed_in("demo@curo.local")


def ask(client: TestClient, message: str, screen: str, **ids) -> tuple[list, dict | None]:
    events: list[tuple[str, dict]] = []
    body = {"message": message, "screen": screen, **{k: str(v) for k, v in ids.items()}}
    with client.stream("POST", "/v1/chat", json=body) as res:
        assert res.status_code == 200, res.read()
        assert res.headers["content-type"].startswith("text/event-stream")
        name = None
        for line in res.iter_lines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                events.append((name, json.loads(line[6:])))
    done = next((d for n, d in events if n == "done"), None)
    return events, done


def meta(events) -> dict:
    return next(d for n, d in events if n == "meta")


def demo_creator() -> dict:
    with service_connection() as conn:
        return conn.execute(
            "select c.* from public.creators c join public.accounts a on a.id = c.account_id "
            "where a.username = 'curo.demo'"
        ).fetchone()


def tool_facts(name: str, args: dict, **ids) -> list[str]:
    """The same tool, called directly as the demo creator: the facts a reply may draw on."""
    creator = demo_creator()
    with creator_session(creator["user_id"]) as conn:
        ctx = T.ToolContext(conn=conn, creator=creator, screen="sim:result", **ids)
        return T.TOOLS[name].run(ctx, args).facts


def linked_simulation(client: TestClient) -> tuple[str, str]:
    opp = client.get("/v1/opportunities").json()[0]
    pid = client.post("/v1/projects", json={"opportunity_id": opp["id"]}).json()["project_id"]
    idea = client.get(f"/v1/projects/{pid}").json()["rounds"][0]["ideas"][0]
    client.post(f"/v1/projects/{pid}/ideas/{idea['id']}/select")
    client.post(f"/v1/projects/{pid}/script", json={})
    client.post(f"/v1/projects/{pid}/storyboard")
    take = client.post("/v1/uploads/sample", json={"name": "take1"}).json()
    started = client.post("/v1/simulations", json={"upload_path": take["path"], "project_id": pid})
    assert started.status_code == 202, started.text
    return pid, started.json()["simulation_id"]


class Planting(MockLLMProvider):
    """The mock model, plus a made-up number in its first ``times`` replies."""

    def __init__(self, times: int):
        self.left = times

    def _chat(self, data):
        chunks = list(super()._chat(data))
        yield from chunks
        if any(c.type == "text" for c in chunks) and self.left > 0:
            self.left -= 1
            yield ChatChunk(type="text", text=" It got 9.7× your usual shares.")


# ------------------------------------------------------------------ the done-when


def test_answers_cite_real_records_and_carry_only_their_numbers(demo):
    events, done = ask(demo, "Which of my reels did best?", "studio:validate")
    assert meta(events)["intent"] == "explain"
    assert [d for n, d in events if n == "tool" and d["status"] == "done"] == [
        {"name": "search_reels", "status": "done"}
    ]
    assert done and done["checked"] == "model"
    reels = [s for s in done["sources"] if s["kind"] == "reel"]
    assert len(reels) == 3
    creator = demo_creator()
    with service_connection() as conn:
        own = {
            str(r["id"])
            for r in conn.execute(
                "select id from public.reels where account_id = %s", (creator["account_id"],)
            ).fetchall()
        }
    assert {s["id"] for s in reels} <= own  # real records, the creator's own
    for s in reels:
        assert s["title"] in done["text"]
    facts = tool_facts("search_reels", {"order": "best", "limit": 3})
    assert validator.new_numbers(done["text"], facts) == set()
    # Saved with the reply, so the conversation keeps its sources.
    with service_connection() as conn:
        row = conn.execute(
            "select sources, checked, intent from public.chat_messages where id = %s",
            (done["message_id"],),
        ).fetchone()
    assert row["checked"] == "model" and len(row["sources"]) == 3 and row["intent"] == "explain"


def test_a_planted_number_is_caught_and_never_shown(demo):
    providers.override("llm", Planting(times=2))
    creator = demo_creator()
    events, done = ask(demo, "What works best for my comments?", "studio:validate")
    names = [n for n, _ in events]
    assert names.count("reset") == 2  # the first reply and the retry were both held back
    assert all("9.7" not in d.get("text", "") for n, d in events if n == "delta")
    assert done["checked"] == "template" and "9.7" not in done["text"]
    assert done["text"].startswith("Here’s what your records show.")
    with service_connection() as conn:
        caught = conn.execute(
            """
            select props from public.events where creator_id = %s and name = 'chat_check_failed'
             order by id desc limit 2
            """,
            (creator["id"],),
        ).fetchall()
    assert len(caught) == 2 and all("9.7" in c["props"]["reason"] for c in caught)


def test_one_retry_is_enough_when_the_model_corrects_itself(demo):
    providers.override("llm", Planting(times=1))
    events, done = ask(demo, "What works best for my comments?", "studio:validate")
    assert [n for n, _ in events].count("reset") == 1
    assert done["checked"] == "model_retry" and "9.7" not in done["text"]
    assert done["text"].startswith("This is what tends to work for you.")


# ------------------------------------------------------------------ the Simulator and Studio


def test_what_if_and_changes_from_the_simulator(demo):
    pid, sid = linked_simulation(demo)
    events, done = ask(demo, "What if I end with a send prompt?", "sim:result", simulation_id=sid)
    assert meta(events)["intent"] == "what_if"
    assert "moves from" in done["text"] and done["checked"] == "model"
    facts = tool_facts(
        "run_simulation",
        {"feature_change": {"cta_type": "share_prompt"}},
        simulation_id=UUID(sid),
    )
    assert validator.new_numbers(done["text"], facts) == set()
    assert done["sources"][0]["kind"] == "simulation"

    # A change the creator's patterns say nothing about doesn't move the estimate, said plainly.
    events, done = ask(demo, "What if I cut faster?", "sim:result", simulation_id=sid)
    assert "stays at" in done["text"] and "don’t link fast cutting" in done["text"]

    events, done = ask(demo, "When should I post it?", "sim:result", simulation_id=sid)
    assert done["text"].startswith("Best time to post")

    events, done = ask(demo, "make the hook punchier", "sim:result", simulation_id=sid)
    assert meta(events)["handoff"] is None  # on the Simulator, the assistant makes the change
    jobs = [d for n, d in events if n == "job"]
    assert len(jobs) == 1 and jobs[0]["step"] == "script"
    assert demo.get(f"/v1/jobs/{jobs[0]['job_id']}").json()["status"] == "succeeded"
    assert demo.get(f"/v1/projects/{pid}").json()["script"]["source"] == "revision"

    history = demo.get(f"/v1/chat?simulation_id={sid}").json()
    assert [m["role"] for m in history] == ["user", "assistant"] * 4
    assert history[0]["content"] == "What if I end with a send prompt?"


def test_studio_changes_are_handed_to_their_step_and_questions_answered(demo):
    pid, _ = linked_simulation(demo)
    events, done = ask(demo, "make the hook punchier", "studio:script", project_id=pid)
    assert meta(events)["handoff"] == "studio" and done is None
    events, done = ask(demo, "Why is the first line there?", "studio:script", project_id=pid)
    assert meta(events)["handoff"] is None
    assert done["text"].startswith("Line 1 of")
    assert done["sources"] == [
        {"kind": "project", "id": pid, "title": demo.get(f"/v1/projects/{pid}").json()["title"]}
    ]


def test_what_isnt_public_and_unclear_messages_get_a_plain_reply(demo):
    events, done = ask(demo, "How many saves will it get?", "studio:validate")
    assert meta(events)["intent"] == "hidden" and not [n for n, _ in events if n == "tool"]
    assert "aren’t public" in done["text"]
    events, done = ask(demo, "ok", "studio:validate")
    assert meta(events)["intent"] == "unclear" and done["text"].startswith("Do you want me")


# ------------------------------------------------------------------ memory


def test_a_stated_preference_is_remembered_applied_and_deletable(demo):
    pid, _ = linked_simulation(demo)
    events, done = ask(demo, "Never suggest film ideas", "studio:ideas", project_id=pid)
    try:
        assert meta(events)["intent"] == "remember"
        assert "I’ll remember" in done["text"] and done["sources"][0]["kind"] == "memory"
        mem = demo.get("/v1/memory").json()
        assert [(m["key"], m["source"]) for m in mem] == [("avoid:film", "stated")]
        # Applied in code: a new round leaves out every idea about filming.
        res = demo.post(f"/v1/projects/{pid}/ideas", json={"prompt": None})
        assert res.status_code == 202
        assert demo.get(f"/v1/jobs/{res.json()['job_id']}").json()["status"] == "succeeded"
        rounds = demo.get(f"/v1/projects/{pid}").json()["rounds"]
        assert any("film" in i["text"].lower() for i in rounds[0]["ideas"])  # before
        assert not any("film" in i["text"].lower() for i in rounds[-1]["ideas"])  # after
    finally:
        for m in demo.get("/v1/memory").json():
            assert demo.delete(f"/v1/memory/{m['id']}").status_code == 204
    assert demo.get("/v1/memory").json() == []


def test_shorter_scripts_are_learned_and_a_deleted_lesson_stays_forgotten(demo):
    creator = demo_creator()
    with service_connection() as conn:
        job_ids = [
            conn.execute(
                """
                insert into public.jobs (creator_id, type, status, payload, result)
                values (%s, 'studio', 'succeeded', '{"action": "script_revise"}',
                        '{"action": "shorten"}') returning id
                """,
                (creator["id"],),
            ).fetchone()["id"]
            for _ in range(3)
        ]
        assert memory.save_learned(conn, creator["id"]) == [memory.LEARNED_SHORTER]
    try:
        mem = demo.get("/v1/memory").json()
        assert [(m["source"], m["value"][:22]) for m in mem] == [
            ("learned", "Starts scripts shorter")
        ]
        pid, _ = linked_simulation(demo)  # writes a script: now planned shorter
        script = demo.get(f"/v1/projects/{pid}").json()["script"]
        assert script["reply"].startswith("Started at the short end")
        with service_connection() as conn:
            plan = conn.execute(
                "select plan from public.script_versions where project_id = %s", (pid,)
            ).fetchone()["plan"]
        assert plan["shorter"] and plan["target_seconds"] < plan["band"]["seconds"]
        assert demo.delete(f"/v1/memory/{mem[0]['id']}").status_code == 204
        with service_connection() as conn:
            assert memory.save_learned(conn, creator["id"]) == []  # not learned again
    finally:
        with service_connection() as conn:
            conn.execute("delete from public.jobs where id = any(%s)", (job_ids,))
            conn.execute(
                "delete from public.creator_memory where creator_id = %s", (creator["id"],)
            )
            conn.execute(
                "update public.creators set memory_dismissed = '{}' where id = %s",
                (creator["id"],),
            )


# ------------------------------------------------------------------ privacy


def test_another_creator_sees_none_of_it(demo):
    _, sid = linked_simulation(demo)
    ask(demo, "Will people share it?", "sim:result", simulation_id=sid)
    other = signed_in("someone.chatting@example.com")
    other.post("/v1/onboarding/username", json={"username": "new.creator"})
    assert other.get(f"/v1/chat?simulation_id={sid}").json() == []
    assert other.get("/v1/memory").json() == []
    _events, done = ask(other, "Will people share it?", "sim:result", simulation_id=sid)
    assert all(s["kind"] != "simulation" for s in done["sources"])  # read as missing
    assert "52 out of 100" not in done["text"]
