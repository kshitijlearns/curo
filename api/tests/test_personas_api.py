"""Follower Personas (v2.2) through the real endpoints, jobs and mocks: the build on the demo
and fixture creators, identity across rebuilds, starters, Studio reactions (cache, re-runs,
revisions, A in the idea score), persona chat, the Simulator's per-persona results, the safety
fallbacks, and the end-to-end journey."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from curo import clock, providers
from curo.db import service_connection
from curo.jobs import personas as persona_jobs
from curo.main import create_app
from curo.providers.public_data.mock import MockPublicDataProvider
from curo.schemas.tasks import T25, T27
from curo.services import ideas, persona_safety
from curo.services import personas as P
from curo.services.validator import new_numbers

pytestmark = pytest.mark.db
ANCHOR = MockPublicDataProvider().anchor


def signed_in(email: str) -> TestClient:
    client = TestClient(create_app())
    code = client.post("/v1/auth/otp", json={"email": email}).json()["dev_code"]
    token = client.post("/v1/auth/verify", json={"email": email, "code": code}).json()
    client.headers["Authorization"] = f"Bearer {token['access_token']}"
    return client


def anonymous(client: TestClient) -> dict[str, str]:
    session = client.post("/v1/auth/anonymous").json()
    return {"Authorization": f"Bearer {session['access_token']}"}


@pytest.fixture
def demo(demo_db):
    with clock.frozen_at(ANCHOR):
        yield signed_in("demo@curo.local")


def creator_id(client: TestClient):
    return client.get("/v1/me").json()["creator"]["id"]


def texts_of(card: dict, detail: dict) -> list[str]:
    return [
        card["name"],
        card["tagline"],
        card["thought"]["thought"],
        *detail["comes_for"],
        *(t["text"] for t in detail["loves"]),
        *detail["wants_more"],
        *(t["text"] for t in detail["turn_offs"]),
        detail["engagement_style"],
        detail["typical_comment"],
    ]


# ------------------------------------------------------------------ the build


def test_the_demo_creator_gets_four_sensible_personas(demo):
    out = demo.get("/v1/personas").json()
    assert out["status"] == "ready" and out["label"] == P.LABEL
    cards = out["personas"]
    assert len(cards) == 4 and [c["slot"] for c in cards] == [1, 2, 3, 4]
    assert sum(c["share_pct"] for c in cards) == 100
    assert [c["share"] for c in cards] == sorted((c["share"] for c in cards), reverse=True)
    assert [c["color"] for c in cards] == ["blue", "lavender", "pink", "ink"]
    assert len({c["name"] for c in cards}) == 4 and len({c["avatar_seed"] for c in cards}) == 4
    assert out["summary"].endswith("of your follower groups are loving your recent reels.") or (
        out["summary"].startswith(("All", "None"))
    )
    for c in cards:
        assert not c["is_starter"] and c["confidence"] in ("medium", "high")
        assert len(c["thought"]["thought"]) <= 140
        assert c["evidence_line"].startswith(f"From {c['n_comments']} comments across ")
        detail = demo.get(f"/v1/personas/{c['id']}").json()
        assert len(detail["comes_for"]) >= 2 and len(detail["loves"]) >= 2
        assert detail["typical_comment"] and "@" not in detail["typical_comment"]
        assert not any(persona_safety.keyword_flags(t) for t in texts_of(c, detail)), c["name"]
        for t in texts_of(c, detail):
            assert not new_numbers(t, detail["facts"]), t
        assert len(detail["history"]) >= 1


def test_persona_facts_match_hand_counts_on_the_demo(demo):
    cid = creator_id(demo)
    with service_connection() as conn:
        usable = conn.execute(
            """
            select count(*) as n from public.comments c
              join public.reels r on r.id = c.reel_id
              join public.creators k on k.account_id = r.account_id
             where k.id = %s and not r.is_deleted and not c.is_creator
               and not coalesce(c.is_bot, false) and length(trim(c.text)) > 0
            """,
            (cid,),
        ).fetchone()["n"]
        rows = persona_jobs.active(conn, cid)
        build = persona_jobs.latest_build(conn, cid)
    assert build["n_comments"] == usable
    # Every usable comment sits in exactly one persona.
    assert sum(r["n_comments"] for r in rows) == usable
    assert sum(float(r["share"]) for r in rows) == pytest.approx(1.0, abs=0.001)
    assert usable > P.HIGH_CONFIDENCE  # so: high confidence unless a group is thin
    for r in rows:
        ev = r["profile"]["evidence"]
        assert f"{ev['share_pct']}% of your comments come from this group." in ev["facts"]
        assert f"{r['n_comments']} comments across {r['n_reels']} reels." in ev["facts"]
        with service_connection() as conn:
            for fav in ev["favourite_reels"]:
                on_reel = conn.execute(
                    "select count(*) as n from public.comments where reel_id = %s and not is_creator",
                    (fav["id"],),
                ).fetchone()["n"]
                assert 0 < fav["comments"] <= on_reel


def test_a_rebuild_on_the_same_data_keeps_every_identity(demo):
    cid = creator_id(demo)
    before = {c["id"]: c for c in demo.get("/v1/personas").json()["personas"]}
    persona_jobs.build_now(cid, "manual")
    after = {c["id"]: c for c in demo.get("/v1/personas").json()["personas"]}
    assert set(after) == set(before)
    for pid, c in after.items():
        assert (c["name"], c["color"], c["avatar_seed"]) == (
            before[pid]["name"],
            before[pid]["color"],
            before[pid]["avatar_seed"],
        )


def test_starter_personas_below_the_data_threshold(db):
    with clock.frozen_at(ANCHOR):
        client = TestClient(create_app())
        h = anonymous(client)
        client.post("/v1/onboarding/username", json={"username": "kavyawears"}, headers=h)
        cid = client.get("/v1/me", headers=h).json()["creator"]["id"]
        # Thin it out: keep only a handful of comments.
        with service_connection() as conn:
            conn.execute(
                """
                delete from public.comments where id in (
                  select c.id from public.comments c join public.reels r on r.id = c.reel_id
                    join public.creators k on k.account_id = r.account_id where k.id = %s
                   order by c.ig_comment_id offset 20)
                """,
                (cid,),
            )
        persona_jobs.build_now(cid, "manual")
        out = client.get("/v1/personas", headers=h).json()
        assert out["early_guess"] and out["summary"] is None
        cards = out["personas"]
        assert len(cards) == 4 and all(c["is_starter"] and c["confidence"] == "low" for c in cards)
        assert sum(c["share_pct"] for c in cards) == 100
        assert all(c["evidence_line"].startswith("An early guess") for c in cards)


@pytest.mark.parametrize("handle", ["stylewithrhea", "kavyawears", "mumbaiwardrobe"])
def test_each_fixture_creator_gets_four_distinct_personas(db, handle):
    with clock.frozen_at(ANCHOR):
        client = TestClient(create_app())
        h = anonymous(client)
        assert (
            client.post("/v1/onboarding/username", json={"username": handle}, headers=h).status_code
            == 202
        )
        cid = client.get("/v1/me", headers=h).json()["creator"]["id"]
        persona_jobs.build_now(cid, "refine")  # the full build, after labels
        cards = client.get("/v1/personas", headers=h).json()["personas"]
        assert len(cards) == 4 and len({c["name"] for c in cards}) == 4
        assert sum(c["share_pct"] for c in cards) == 100
        assert min(c["share"] for c in cards) >= P.MIN_SHARE - 0.001


def test_identity_holds_when_the_data_barely_changes(db):
    with clock.frozen_at(ANCHOR):
        client = TestClient(create_app())
        h = anonymous(client)
        client.post("/v1/onboarding/username", json={"username": "stylewithrhea"}, headers=h)
        cid = client.get("/v1/me", headers=h).json()["creator"]["id"]
        persona_jobs.build_now(cid, "refine")
        before = {c["id"]: c for c in client.get("/v1/personas", headers=h).json()["personas"]}
        # A month later, a few comments more (copies of existing ones on the same reels).
        with clock.frozen_at(ANCHOR + timedelta(days=31)), service_connection() as conn:
            conn.execute(
                """
                insert into public.comments
                  (reel_id, ig_comment_id, text, posted_at, is_creator, intent, sentiment,
                   language, labelled_at, is_bot)
                select c.reel_id, c.ig_comment_id || '_again', c.text, c.posted_at, false,
                       c.intent, c.sentiment, c.language, c.labelled_at, false
                  from public.comments c join public.reels r on r.id = c.reel_id
                  join public.creators k on k.account_id = r.account_id
                 where k.id = %s and not c.is_creator order by c.ig_comment_id limit 12
                """,
                (cid,),
            )
        persona_jobs.build_now(cid, "monthly")
        after = {c["id"]: c for c in client.get("/v1/personas", headers=h).json()["personas"]}
        assert set(after) == set(before)
        assert {(c["name"], c["color"], c["avatar_seed"]) for c in after.values()} == {
            (c["name"], c["color"], c["avatar_seed"]) for c in before.values()
        }


# ------------------------------------------------------------------ safety fallbacks


def test_planted_sensitive_and_number_outputs_fall_back_to_templates(db, monkeypatch):
    llm = providers.get_llm()
    real = llm.run

    def planted(task, data):
        out = real(task, data)
        if task is T25:
            ps = list(out.personas)
            ps[0] = ps[0].model_copy(update={"tagline": "Mostly college students and moms."})
            ps[1] = ps[1].model_copy(update={"typical_comment": "Love this, 87% of us agree!"})
            out = out.model_copy(update={"personas": ps})
        return out

    monkeypatch.setattr(llm, "run", planted)
    with clock.frozen_at(ANCHOR):
        client = TestClient(create_app())
        h = anonymous(client)
        client.post("/v1/onboarding/username", json={"username": "mumbaiwardrobe"}, headers=h)
        cid = client.get("/v1/me", headers=h).json()["creator"]["id"]
        persona_jobs.build_now(cid, "refine")
        with service_connection() as conn:
            rows = persona_jobs.active(conn, cid)
    first, second = rows[0], rows[1]
    assert first["profile"]["source"] == "template" and "students" not in first["tagline"]
    assert second["profile"]["source"] == "template"
    assert "87" not in second["profile"]["typical_comment"]


# ------------------------------------------------------------------ Studio


def _t27_calls(monkeypatch) -> list[int]:
    llm = providers.get_llm()
    real = llm.run
    calls: list[int] = []

    def counting(task, data):
        if task is T27:
            calls.append(1)
        return real(task, data)

    monkeypatch.setattr(llm, "run", counting)
    return calls


def start_project(client: TestClient) -> dict:
    opp = client.get("/v1/opportunities").json()[0]
    started = client.post("/v1/projects", json={"opportunity_id": opp["id"]}).json()
    assert client.get(f"/v1/jobs/{started['job_id']}").json()["status"] == "succeeded"
    return client.get(f"/v1/projects/{started['project_id']}").json()


def test_shown_ideas_get_four_reactions_and_a_is_their_weighted_score(demo):
    project = start_project(demo)
    pid = project["id"]
    cards = {c["id"]: c for c in demo.get("/v1/personas").json()["personas"]}
    for idea in project["rounds"][-1]["ideas"]:
        r = demo.post(
            f"/v1/projects/{pid}/persona-reactions",
            json={"target_type": "idea", "target_id": idea["id"]},
        ).json()
        assert r["status"] == "ready" and len(r["reactions"]) == 4
        assert {x["persona_id"] for x in r["reactions"]} == set(cards)
        # Hand check: A = Σ share × score / Σ share, each persona's score being
        # 0.5 × the model's + 0.5 × the code fit (0–100 → 0–1). The API shows scores rounded.
        total = sum(cards[x["persona_id"]]["share"] for x in r["reactions"])
        a = (
            sum(
                cards[x["persona_id"]]["share"]
                * (0.5 * x["score_model"] + 0.5 * x["score_code"])
                / 100
                for x in r["reactions"]
            )
            / total
        )
        assert idea["parts"]["A"] == pytest.approx(a, abs=0.0015)
        assert idea["score"] == pytest.approx(ideas.idea_score(idea["parts"]), abs=1e-3)
        for x in r["reactions"]:
            assert x["score"] == round(0.5 * (x["score_model"] or 0) + 0.5 * x["score_code"]) or (
                abs(x["score"] - (0.5 * x["score_model"] + 0.5 * x["score_code"])) <= 0.5
            )
            assert x["reaction"] == P.reaction_for(x["score"]) or abs(x["score"] - 55) < 1
            assert x["would"].keys() >= {"like", "comment", "share", "save"}
            assert not persona_safety.keyword_flags(x["opinion"])
        assert r["summary"].endswith(("isn’t sure.", "would skip it.", "are in."))


def test_reactions_are_cached_rerun_on_content_change_and_never_count_as_revisions(
    demo, monkeypatch
):
    project = start_project(demo)
    pid = project["id"]
    idea = project["rounds"][-1]["ideas"][0]
    demo.post(f"/v1/projects/{pid}/ideas/{idea['id']}/select")
    res = demo.post(f"/v1/projects/{pid}/script", json={})
    assert demo.get(f"/v1/jobs/{res.json()['job_id']}").json()["status"] == "succeeded"
    calls = _t27_calls(monkeypatch)

    def revisions():
        with service_connection() as conn:
            return conn.execute(
                "select revisions from public.projects where id = %s", (pid,)
            ).fetchone()["revisions"]

    used = revisions()
    first = demo.post(f"/v1/projects/{pid}/persona-reactions", json={}).json()
    assert first["target_type"] == "script" and len(first["reactions"]) == 4
    assert len(calls) == 1
    # Re-opening (POST again, or GET) never calls the model and never counts.
    again = demo.post(f"/v1/projects/{pid}/persona-reactions", json={}).json()
    cached = demo.get(f"/v1/projects/{pid}/persona-reactions").json()
    assert again["reactions"] == first["reactions"] == cached["reactions"]
    assert len(calls) == 1 and revisions() == used
    # A content change (a revision) is a new version: one revision, one re-run.
    res = demo.post(
        f"/v1/projects/{pid}/script/revise", json={"instruction": "Make the hook shorter"}
    )
    assert demo.get(f"/v1/jobs/{res.json()['job_id']}").json()["status"] == "succeeded"
    assert revisions() == used + 1
    third = demo.post(f"/v1/projects/{pid}/persona-reactions", json={}).json()
    assert third["target_version"] == first["target_version"] + 1 and len(calls) == 2
    assert revisions() == used + 1
    # The earlier version's reactions are still readable by version.
    old = demo.get(f"/v1/projects/{pid}/persona-reactions?version={first['target_version']}").json()
    assert old["reactions"] == first["reactions"]


def test_validate_gives_a_verdict_plus_four_persona_opinions(demo):
    v = demo.post("/v1/ideas/validate", json={"text": "3 budget festive looks for Ganpati"}).json()
    p = v["personas"]
    assert p and len(p["reactions"]) == 4 and p["summary"]
    assert v["parts"]["A"] == pytest.approx(p["audience"], abs=0.002)
    assert len({x["opinion"] for x in p["reactions"]}) >= 2  # their own takes, not one
    again = demo.post(
        "/v1/ideas/validate", json={"text": "3 budget festive looks for Ganpati"}
    ).json()
    assert again["personas"]["reactions"] == p["reactions"]  # cached


def test_another_creator_cannot_read_a_persona(demo, demo_db):
    pid = demo.get("/v1/personas").json()["personas"][0]["id"]
    other = signed_in("someone-else@example.com")
    assert other.get(f"/v1/personas/{pid}").status_code in (404, 409)


# ------------------------------------------------------------------ persona chat


def _sse(text: str) -> list[tuple[str, dict]]:
    import json

    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n") if ": " in line)
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_persona_chat_stays_in_character_counts_as_ask_curo_and_is_honest(demo):
    p = demo.get("/v1/personas").json()["personas"][0]
    before = demo.get("/v1/billing").json()["credits"]["chat"]["left"]
    res = demo.post(f"/v1/personas/{p['id']}/chat", json={"message": "What do you want next?"})
    events = _sse(res.text)
    assert events[-1][0] == "done" and events[-1][1]["text"]
    assert demo.get("/v1/billing").json()["credits"]["chat"]["left"] == before - 1
    honest = _sse(
        demo.post(
            f"/v1/personas/{p['id']}/chat", json={"message": "How many of you are there exactly?"}
        ).text
    )
    assert honest[-1][1]["text"].startswith("I’m a summary of your comments")
    history = demo.get(f"/v1/personas/{p['id']}/chat").json()
    assert [m["role"] for m in history[-4:]] == ["user", "persona", "user", "persona"]


# ------------------------------------------------------------------ the Simulator


def test_simulator_agents_come_from_the_personas_with_per_group_results(demo):
    take1 = demo.post("/v1/uploads/sample", json={"name": "take1"}).json()
    res = demo.post("/v1/simulations", json={"upload_path": take1["path"]})
    started = res.json()
    assert demo.get(f"/v1/jobs/{started['job_id']}").json()["status"] == "succeeded"
    sim = demo.get(f"/v1/simulations/{started['simulation_id']}").json()
    crowd = sim["result"]["audience"]
    cards = {c["id"]: c for c in demo.get("/v1/personas").json()["personas"]}
    groups = crowd["personas"]
    assert len(groups) == 4 and {g["persona_id"] for g in groups} == set(cards)
    assert sum(g["agents"] for g in groups) == crowd["agents"]
    for g in groups:
        # Agents in proportion to the persona's share (largest remainder).
        assert abs(g["agents"] - cards[g["persona_id"]]["share"] * crowd["agents"]) <= 1
        assert 0 <= g["watched_to_end"] <= 1 and g["saves_simulated"]
        assert g["takeaway"] and g["opinion"] and g["opinion"]["opinion"]
    labels = {c["short_name"] for c in cards.values()}
    assert all(c["segment"] in labels and c["color"] for c in crowd["comments"])
    with service_connection() as conn:
        n = conn.execute(
            """
            select count(*) as n from public.audience_personas
             where version = %s and persona_id is null
            """,
            (crowd["persona_version"],),
        ).fetchone()["n"]
        segments = conn.execute(
            "select distinct segment from public.persona_calibrations where version = %s",
            (crowd["persona_version"],),
        ).fetchall()
    assert n == 0
    assert "" in {s["segment"] for s in segments} and len(segments) >= 2


# ------------------------------------------------------------------ end to end


def test_end_to_end_onboarding_recap_home_studio_simulator(db):
    with clock.frozen_at(ANCHOR):
        client = TestClient(create_app())
        h = anonymous(client)
        client.headers.update(h)
        assert (
            client.post("/v1/onboarding/username", json={"username": "curo.demo"}).status_code
            == 202
        )
        # The recap carries "Meet your followers".
        recap = client.get("/v1/recaps/latest").json()
        ids = [s["slide_id"] for s in recap["slides"]]
        assert ids.index("followers_intro") == ids.index("creator_type") + 1
        assert ids[ids.index("followers_intro") + 1 : ids.index("followers_summary")] == [
            "persona_1",
            "persona_2",
            "persona_3",
            "persona_4",
        ]
        # Home: the persona cards come first.
        home = client.get("/v1/home").json()["sections"]
        assert home[0]["id"] == "personas"
        cards = client.get("/v1/personas").json()["personas"]
        assert len(cards) == 4
        # Studio: an idea with 4 reactions; tap a persona; apply its change as a revision.
        # "Make this" on the top persona's request: a project seeded with it.
        seed = (cards[0]["thought"]["wants_more"] or ["A festive look"])[0]
        started = client.post("/v1/projects", json={"idea_text": seed}).json()
        assert started["job_id"] is None  # the creator's own idea: no ideas to write
        pid = started["project_id"]
        idea = client.get(f"/v1/projects/{pid}").json()["idea"]
        r = client.post(
            f"/v1/projects/{pid}/persona-reactions",
            json={"target_type": "idea", "target_id": idea["id"]},
        ).json()
        assert len(r["reactions"]) == 4
        tapped = r["reactions"][1]
        assert tapped["opinion"] and tapped["reaction_label"]
        res = client.post(f"/v1/projects/{pid}/script", json={})
        assert client.get(f"/v1/jobs/{res.json()['job_id']}").json()["status"] == "succeeded"
        applied = client.post(
            f"/v1/projects/{pid}/script/revise",
            json={"instruction": tapped["win_them_over"] or "Show the result first"},
        )
        assert client.get(f"/v1/jobs/{applied.json()['job_id']}").json()["status"] == "succeeded"
        after = client.post(f"/v1/projects/{pid}/persona-reactions", json={}).json()
        assert after["target_type"] == "script" and len(after["reactions"]) == 4
        # Simulator: per-persona results, compared with Studio.
        take = client.post("/v1/uploads/sample", json={"name": "take1"}).json()
        sim = client.post(
            "/v1/simulations", json={"upload_path": take["path"], "project_id": pid}
        ).json()
        assert client.get(f"/v1/jobs/{sim['job_id']}").json()["status"] == "succeeded"
        result = client.get(f"/v1/simulations/{sim['simulation_id']}").json()["result"]
        crowd = result["audience"]
        assert len(crowd["personas"]) == 4
        assert crowd["studio_compare"] and crowd["studio_compare"][0].startswith("In Studio, ")
