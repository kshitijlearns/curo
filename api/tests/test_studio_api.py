"""Phase 6 done-when: the full Ganpati journey from Home to a saved draft, visible on Saved —
through the real endpoints, jobs and scoring on the seeded demo."""

import itertools

import psycopg
import pytest
from fastapi.testclient import TestClient

from curo import clock
from curo.db import service_connection
from curo.main import create_app
from curo.providers.public_data.mock import MockPublicDataProvider
from curo.services import ideas
from curo.services.validator import new_numbers

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


def done(client: TestClient, res) -> dict:
    """A 202 step: its job ran (inline in tests) and succeeded; returns the project."""
    assert res.status_code == 202, res.text
    body = res.json()
    job = client.get(f"/v1/jobs/{body['job_id']}").json()
    assert job["status"] == "succeeded", job
    return client.get(f"/v1/projects/{body['project_id']}").json()


def start_ganpati(client: TestClient) -> dict:
    ganpati = client.get("/v1/opportunities").json()[0]
    assert ganpati["name"] == "Ganpati dress ideas"
    res = client.post("/v1/projects", json={"opportunity_id": ganpati["id"]})
    assert res.status_code == 201, res.text
    started = res.json()
    job = client.get(f"/v1/jobs/{started['job_id']}").json()
    assert job["status"] == "succeeded", job
    return client.get(f"/v1/projects/{started['project_id']}").json()


def test_the_ganpati_journey_from_home_to_a_saved_draft(demo):
    project = start_ganpati(demo)
    pid = project["id"]
    assert project["opportunity"]["name"] == "Ganpati dress ideas" and project["step"] == "ideas"

    # Step 1: three ideas that do different jobs, each backed by evidence, scored by the formula.
    (round0,) = project["rounds"]
    assert [i["slot"] for i in round0["ideas"]] == ["proven", "adapted", "explore"]
    for idea in round0["ideas"]:
        assert idea["evidence"] and idea["why"]
        assert idea["score"] == pytest.approx(ideas.idea_score(idea["parts"]), abs=1e-3)
        assert sum(idea["shares"].values()) == 100
    first = round0["ideas"][0]
    project = demo.post(f"/v1/projects/{pid}/ideas/{first['id']}/select").json()
    assert project["step"] == "idea" and project["idea"]["id"] == first["id"]
    assert project["title"] == first["text"]

    # Step 2: the script, timed at the creator's speaking speed, notes only where a card backs them.
    project = done(demo, demo.post(f"/v1/projects/{pid}/script", json={}))
    script = project["script"]
    beats = script["beats"]
    assert beats[0]["role"] == "hook" and beats[-1]["role"] == "ending"
    assert all(a["end_s"] <= b["start_s"] + 0.01 for a, b in itertools.pairwise(beats))
    notes = [b["note"] for b in beats if b["note"]]
    assert notes and all(n["type"] in ("hook", "comments", "likes", "shares") for n in notes)
    with service_connection() as conn:
        effects = {
            f"{float(r['effect']):.2f}×"
            for r in conn.execute("select effect from public.pattern_cards").fetchall()
        }
    assert all(any(e in n["evidence"] for e in effects) for n in notes)  # each cites a real card
    assert "will" not in " ".join(n["desc"] for n in notes)
    assert "about" in script["reply"] and "seconds" in script["reply"]

    # A targeted change rewrites only its beat.
    project = done(
        demo,
        demo.post(
            f"/v1/projects/{pid}/script/revise", json={"instruction": "Make the hook stronger"}
        ),
    )
    revised = project["script"]
    assert revised["version"] == 2 and revised["changed_beat_ids"] == [beats[0]["id"]]
    assert [b["text"] for b in revised["beats"][1:]] == [b["text"] for b in beats[1:]]
    assert revised["beats"][0]["text"] != beats[0]["text"]

    # Step 3: one frame per beat, linked by id.
    project = done(demo, demo.post(f"/v1/projects/{pid}/storyboard"))
    board = project["storyboard"]
    assert [f["beat_id"] for f in board["frames"]] == [b["id"] for b in revised["beats"]]
    assert board["feasibility"]["label"] in ("Easy", "Moderate", "Hard") and board["up_to_date"]

    # A script change marks only the frames of changed lines; rebuilding redraws only those.
    project = done(
        demo,
        demo.post(
            f"/v1/projects/{pid}/script/revise",
            json={"instruction": "Change line 3 to a denim jacket over the kurta"},
        ),
    )
    changed = project["script"]["changed_beat_ids"]
    stale = [f["beat_id"] for f in project["storyboard"]["frames"] if f["stale"]]
    assert stale == changed and not project["storyboard"]["up_to_date"]
    project = done(demo, demo.post(f"/v1/projects/{pid}/storyboard"))
    redrawn = project["storyboard"]
    assert redrawn["up_to_date"] and redrawn["version"] == board["version"] + 1
    for old, new in zip(board["frames"], redrawn["frames"], strict=True):
        if old["beat_id"] not in changed:
            assert {k: new[k] for k in ("shot_type", "instruction", "icon_key")} == {k: old[k] for k in ("shot_type", "instruction", "icon_key")}  # fmt: skip

    # Step 4: three captions with three jobs, numbers only from the script; five hashtags at most.
    project = done(demo, demo.post(f"/v1/projects/{pid}/captions"))
    caps = project["captions"]
    assert sorted(o["job"] for o in caps["options"]) == ["comments", "likes", "shares"]
    facts = [
        project["idea"]["text"],
        "Ganpati dress ideas",
        *(b["text"] for b in project["script"]["beats"]),
        "Ganpati outfit",
        "Ganesh Chaturthi",
    ]
    for o in caps["options"]:
        assert new_numbers(o["text"], facts) == set(), o["text"]
    assert 1 <= len(caps["hashtags"]) <= 5
    six = demo.put(
        f"/v1/projects/{pid}/hashtags",
        json={"hashtags": [*caps["hashtags"], "a", "b", "c", "d", "e"][:6]},
    )
    assert six.status_code == 422 and "5" in six.json()["detail"]
    five = demo.put(
        f"/v1/projects/{pid}/hashtags", json={"hashtags": [*caps["hashtags"][:4], "#MumbaiFashion"]}
    )
    assert five.status_code == 200 and five.json()["captions"]["hashtags"][-1] == "mumbaifashion"
    assert (
        demo.put(f"/v1/projects/{pid}/caption", json={"chosen": 2}).json()["captions"]["chosen"]
        == 2
    )

    # Final draft → Saved.
    project = demo.post(f"/v1/projects/{pid}/save", json={"step": "final"}).json()
    assert project["status"] == "saved" and project["step"] == "final"
    drafts = demo.get("/v1/saved").json()["drafts"]
    mine = next(d for d in drafts if d["id"] == pid)
    assert mine["title"] == first["text"] and mine["opportunity"] == "Ganpati dress ideas"
    assert mine["step"] == "final" and mine["icon_key"]
    assert demo.get("/v1/me").json()["drafts"] >= 1
    # Reopening the draft brings everything back under the one project id.
    again = demo.get(f"/v1/projects/{pid}").json()
    assert again["script"]["version"] == 3 and again["storyboard"] and again["captions"]


def test_a_note_of_the_creators_own_starts_a_round_that_keeps_it(demo):
    project = start_ganpati(demo)
    project = done(
        demo, demo.post(f"/v1/projects/{project['id']}/ideas", json={"prompt": "looks on a budget"})
    )
    assert len(project["rounds"]) == 2
    note_round = project["rounds"][1]
    assert note_round["prompt"] == "looks on a budget" and len(note_round["ideas"]) == 3
    assert all("budget" in i["text"].lower() for i in note_round["ideas"])


def test_the_creators_own_script_is_kept_as_written_and_noted(demo):
    project = start_ganpati(demo)
    pid = project["id"]
    demo.post(f"/v1/projects/{pid}/ideas/{project['rounds'][0]['ideas'][0]['id']}/select")
    text = "One outfit, three Ganpati moods.\nLook one: classic.\nLook two: a denim jacket.\nWhich one would you pick? Tell me in the comments."
    project = demo.put(f"/v1/projects/{pid}/script", json={"text": text}).json()
    assert [b["text"] for b in project["script"]["beats"]] == text.splitlines()
    assert project["script"]["source"] == "creator"
    assert project["script"]["beats"][-1]["note"]["type"] == "comments"


def test_steps_need_what_comes_before(demo):
    project = start_ganpati(demo)
    res = demo.post(f"/v1/projects/{project['id']}/storyboard")
    job = demo.get(f"/v1/jobs/{res.json()['job_id']}").json()
    assert job["status"] == "failed" and "script" in job["error"].lower()
    save = demo.post(f"/v1/projects/{project['id']}/save", json={})
    assert save.status_code == 409


def test_validate_scores_a_free_typed_idea(demo):
    res = demo.post("/v1/ideas/validate", json={"text": "Three ways to wear one saree for Ganpati"})
    assert res.status_code == 200, res.text
    v = res.json()
    assert v["verdict"] == ideas.verdict(v["score"])
    assert v["score"] == pytest.approx(ideas.idea_score(v["parts"]), abs=0.01)
    assert len(v["reasons"]) == 2 and all(r["evidence"] for r in v["reasons"])
    assert all(t["gain"] > 0 for t in v["tweaks"])
    # "Develop this idea" makes it the project's idea.
    started = demo.post("/v1/projects", json={"idea_text": v["text"]}).json()
    project = demo.get(f"/v1/projects/{started['project_id']}").json()
    assert started["job_id"] is None and project["step"] == "idea"
    assert project["idea"]["text"] == v["text"] and project["idea"]["source"] == "creator"


def test_a_project_is_only_its_creators(demo):
    project = start_ganpati(demo)
    with clock.frozen_at(ANCHOR):
        other = signed_in("someone@example.com")
        assert other.get(f"/v1/projects/{project['id']}").status_code in (404, 409)


def test_the_database_refuses_a_sixth_hashtag(demo_db):
    with service_connection() as conn:
        project = conn.execute("select id from public.projects limit 1").fetchone()
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "insert into public.captions (project_id, version, options, hashtags) values (%s, 999, '[]', %s)",
                (project["id"], ["a", "b", "c", "d", "e", "f"]),
            )


def test_picking_another_idea_starts_fresh_and_going_back_finds_the_work(demo):
    project = start_ganpati(demo)
    pid = project["id"]
    one, two = project["rounds"][0]["ideas"][:2]
    demo.post(f"/v1/projects/{pid}/ideas/{one['id']}/select")
    first = done(demo, demo.post(f"/v1/projects/{pid}/script", json={}))["script"]
    project = demo.post(f"/v1/projects/{pid}/ideas/{two['id']}/select").json()
    assert project["script"] is None and project["storyboard"] is None
    project = demo.post(f"/v1/projects/{pid}/ideas/{one['id']}/select").json()
    assert project["script"]["version"] == first["version"]


def test_a_pasted_caption_is_kept_as_written(demo):
    project = start_ganpati(demo)
    pid = project["id"]
    demo.post(f"/v1/projects/{pid}/ideas/{project['rounds'][0]['ideas'][0]['id']}/select")
    done(demo, demo.post(f"/v1/projects/{pid}/script", json={}))
    before = done(demo, demo.post(f"/v1/projects/{pid}/captions"))["captions"]
    mine = "my three favourite looks for the festival this year, all from my own wardrobe"
    after = done(demo, demo.post(f"/v1/projects/{pid}/captions/revise", json={"instruction": mine}))
    caps = after["captions"]
    assert [o["text"] for o in caps["options"]] == [mine]
    assert caps["hashtags"] == before["hashtags"]  # the chosen tags stay
