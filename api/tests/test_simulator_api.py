"""Phase 7 done-when: a sample upload returns a full result; a re-run shows the score change —
through the real endpoints, jobs and estimate on the seeded demo."""

import re

import pytest
from fastapi.testclient import TestClient

from curo import clock
from curo.db import service_connection
from curo.main import create_app
from curo.providers.public_data.mock import MockPublicDataProvider
from curo.services import mp4

pytestmark = pytest.mark.db
ANCHOR = MockPublicDataProvider().anchor
HIDDEN = re.compile(r"\b(saves?|saved by|reach|impressions?|watch time|demographic)", re.I)


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


def ganpati_draft(client: TestClient) -> dict:
    """The Studio journey up to a caption, as a creator would have it before recording."""
    opp = client.get("/v1/opportunities").json()[0]
    pid = client.post("/v1/projects", json={"opportunity_id": opp["id"]}).json()["project_id"]
    idea = client.get(f"/v1/projects/{pid}").json()["rounds"][0]["ideas"][0]
    client.post(f"/v1/projects/{pid}/ideas/{idea['id']}/select")
    for step in ("script", "storyboard", "captions"):
        res = client.post(f"/v1/projects/{pid}/{step}", json={} if step == "script" else None)
        assert res.status_code == 202, res.text
    return client.get(f"/v1/projects/{pid}").json()


def simulate(client: TestClient, path: str, **body) -> dict:
    res = client.post("/v1/simulations", json={"upload_path": path, **body})
    assert res.status_code == 202, res.text
    started = res.json()
    job = client.get(f"/v1/jobs/{started['job_id']}").json()
    assert job["status"] == "succeeded", job
    return client.get(f"/v1/simulations/{started['simulation_id']}").json()


def all_text(sim: dict) -> str:
    r = sim["result"]
    parts = [r["accuracy"], *r["notes"], *(c["text"] for c in r["compare"])]
    for a in r["audiences"].values():
        parts += [a["label"], a["summary"]]
        for item in a["working"] + a["holding"]:
            parts += [item["text"], *(e["stat"] for e in item["evidence"])]
    parts += [e["title"] + " " + e["description"] for e in sim["edits"]]
    parts += [v for rows in r["dna"].values() for _, v in rows]
    return " ".join(parts)


def test_a_sample_upload_returns_a_full_result_and_a_rerun_shows_the_change(demo):
    draft = ganpati_draft(demo)
    samples = demo.get("/v1/uploads/samples").json()
    assert [s["name"] for s in samples] == ["take1", "take2"]
    take1 = demo.post("/v1/uploads/sample", json={"name": "take1"}).json()
    assert take1["duration_s"] == 41 and take1["path"].startswith("uploads/")

    sim = simulate(demo, take1["path"], project_id=draft["id"], audience="both")
    assert sim["status"] == "done" and sim["project_title"] == draft["title"]
    result = sim["result"]
    # A score for each audience (the toggle switches between them), each with its reasons.
    assert set(sim["scores"]) == {"followers", "new", "both"}
    assert sim["score"] == sim["scores"]["both"]
    for audience in result["audiences"].values():
        assert 0 <= audience["score"] <= 100 and audience["label"] and audience["summary"]
        assert audience["working"] and audience["holding"]
        # v2: evidence is the creator's own reels; a "creators like you" prior may have none.
        assert any(item["evidence"] for item in audience["working"] + audience["holding"])
    holding = {h["feature"] for h in result["audiences"]["both"]["holding"]}
    assert {"cta_type", "payoff_band"} <= holding
    hook = next(h for h in result["audiences"]["both"]["holding"] if h["feature"] == "payoff_band")
    assert hook["frame"] == 0 and hook["frame_label"] == "Frame 1 · Hook"
    # The report: the four public counts against the 7-day usual, as ranges.
    assert [r["metric"] for r in result["report"]] == [
        "views",
        "like_rate",
        "comment_rate",
        "share_rate",
    ]
    for row in result["report"]:
        assert row["known"] and row["low"] <= row["mid"] <= row["high"]
    assert result["best_time"] and result["accuracy"]
    assert [k for k, _ in result["dna"]["trend"]][-1] == "Originality"
    assert result["linked"] and result["compare"]
    # Edits, re-scored: each helps the audience it is shown for.
    edits = {e["id"]: e for e in sim["edits"]}
    shown = result["audiences"]["both"]["edit_ids"]
    assert 1 <= len(shown) <= 3
    assert all(edits[i]["gains"]["both"] > 0 for i in shown)
    # Honest: nothing hidden is mentioned, and the stored estimate is in counts.
    assert not HIDDEN.search(all_text(sim)), HIDDEN.search(all_text(sim))
    with service_connection() as conn:
        row = conn.execute(
            "select predicted, method_version from public.simulations where id = %s", (sim["id"],)
        ).fetchone()
    assert row["method_version"] == "t9-v0"
    assert set(row["predicted"]) == {"views", "likes", "comments", "shares"}

    # Apply the edits: they are written back to the Studio draft.
    for edit_id in shown:
        applied = demo.post(f"/v1/simulations/{sim['id']}/edits/{edit_id}/apply").json()
        assert applied["edit"]["applied"] and applied["job_id"]
        assert demo.get(f"/v1/jobs/{applied['job_id']}").json()["status"] == "succeeded"
        again = demo.post(f"/v1/simulations/{sim['id']}/edits/{edit_id}/apply").json()
        assert again["job_id"] == applied["job_id"]  # applying twice changes nothing more
    after = demo.get(f"/v1/projects/{draft['id']}").json()
    assert after["script"]["source"] == "simulator_edit"
    assert [b["text"] for b in after["script"]["beats"]] != [
        b["text"] for b in draft["script"]["beats"]
    ]

    # Re-run: the same video is refused; the re-recorded take scores higher than the first.
    same = demo.post(f"/v1/simulations/{sim['id']}/rerun", json={"upload_path": take1["path"]})
    assert same.status_code == 422
    take2 = demo.post("/v1/uploads/sample", json={"name": "take2"}).json()
    res = demo.post(f"/v1/simulations/{sim['id']}/rerun", json={"upload_path": take2["path"]})
    assert res.status_code == 202, res.text
    rerun = demo.get(f"/v1/simulations/{res.json()['simulation_id']}").json()
    assert rerun["status"] == "done" and rerun["parent_simulation_id"] == sim["id"]
    assert rerun["result"]["previous"]["scores"] == sim["scores"]
    assert rerun["scores"]["both"] > sim["scores"]["both"]
    assert rerun["project_id"] == draft["id"] and rerun["audience"] == "both"
    # v2: the AI audience scores the better take higher, shown next to the previous score.
    crowd = rerun["result"]["audience"]
    assert crowd["previous_engagement_score"] == sim["engagement_score"]
    assert rerun["engagement_score"] > sim["engagement_score"]


def test_the_ai_audience_predicts_explains_and_can_be_talked_to(demo):
    take1 = demo.post("/v1/uploads/sample", json={"name": "take1"}).json()
    sim = simulate(demo, take1["path"])
    crowd = sim["result"]["audience"]
    assert crowd["agents"] == 1000 and 0 < crowd["watched"] < 1000
    assert crowd["label"] == "Simulated by CURO's AI audience. Not real comments."
    assert 4 <= len(crowd["segments"]) <= 8
    assert sum(s["share"] for s in crowd["segments"]) == pytest.approx(1.0, abs=0.01)
    # The engagement score is a percentile among the creator's past reels.
    assert crowd["past_reels_scored"] >= 5
    assert sim["engagement_score"] is not None and 0 <= sim["engagement_score"] <= 100
    # Predicted ranges: calibrated on past reels; saves always labelled simulated.
    preds = {p["metric"]: p for p in crowd["predictions"]}
    assert set(preds) == {"views", "likes", "comments", "shares", "saves"}
    assert preds["saves"]["simulated"] and not preds["likes"]["simulated"]
    for m in ("views", "likes", "comments", "shares"):
        p = preds[m]
        assert p["count"] is not None and p["count_low"] <= p["count"] <= p["count_high"]
    # The skip curve only falls.
    watching = [x["watching"] for x in crowd["skip_curve"]]
    assert watching[0] == 1.0 and watching == sorted(watching, reverse=True)
    # 3 working / 3 holding / 3 edits at most, each with a moment where it applies.
    ex = crowd["explain"]
    assert ex["holding"] and ex["edits"]
    assert all(len(ex[k]) <= 3 for k in ("working", "holding", "edits"))
    # Simulated comments: "Agent 12 · Festive planner", never a handle, never a number.
    assert crowd["comments"]
    for c in crowd["comments"]:
        assert c["segment"] and "@" not in c["text"] and not re.search(r"\d", c["text"])
    # Talk to an agent: in character, 10 messages per simulation.
    first = crowd["comments"][0]["agent_no"]
    agent = demo.get(f"/v1/simulations/{sim['id']}/agents/{first}").json()
    assert agent["reaction"]["commented"] and agent["messages_left"] == 10
    out = demo.post(
        f"/v1/simulations/{sim['id']}/agents/{first}/chat", json={"message": "Why did you stop?"}
    )
    assert out.status_code == 200 and out.json()["messages_left"] == 9
    assert out.json()["answer"]
    for _ in range(9):
        demo.post(f"/v1/simulations/{sim['id']}/agents/{first}/chat", json={"message": "And?"})
    over = demo.post(f"/v1/simulations/{sim['id']}/agents/{first}/chat", json={"message": "?"})
    assert over.status_code == 402 and over.json()["detail"]["code"] == "agent_chat_limit"


def test_an_unlinked_simulation_marks_edits_without_a_draft(demo):
    take1 = demo.post("/v1/uploads/sample", json={"name": "take1"}).json()
    sim = simulate(demo, take1["path"], caption=take1["caption"], audience="new")
    assert sim["score"] == sim["scores"]["new"] and not sim["result"]["linked"]
    assert sim["result"]["compare"] == []
    holding = sim["result"]["audiences"]["new"]["holding"][0]
    assert holding["frame"] is None and holding["frame_label"]  # the moment, not a frame
    edit = sim["edits"][0]
    applied = demo.post(f"/v1/simulations/{sim['id']}/edits/{edit['id']}/apply").json()
    assert applied["edit"]["applied"] and applied["job_id"] is None


def test_uploads_are_checked_before_simulating(demo):
    signed = demo.post("/v1/uploads/sign", json={"content_type": "video/mp4"}).json()
    assert signed["url"].startswith("/v1/uploads/local/") and signed["method"] == "PUT"
    too_long = mp4.build(95, 1080, 1920)
    assert demo.put(signed["url"], content=too_long, headers=signed["headers"]).status_code == 204
    res = demo.post("/v1/simulations", json={"upload_path": signed["path"]})
    assert res.status_code == 422 and "95 seconds long" in res.json()["detail"]

    other = demo.post("/v1/uploads/sign", json={"content_type": "video/quicktime"}).json()
    assert other["path"].endswith(".mov")
    demo.put(other["url"], content=b"not a video at all", headers=other["headers"])
    res = demo.post("/v1/simulations", json={"upload_path": other["path"]})
    assert res.status_code == 422 and "MP4 or MOV" in res.json()["detail"]

    assert demo.put(signed["url"] + "x", content=b"x").status_code == 403
    missing = demo.post("/v1/simulations", json={"upload_path": signed["path"] + ".gone"})
    assert missing.status_code == 422
    elsewhere = demo.post("/v1/simulations", json={"upload_path": "uploads/someone-else/a.mp4"})
    assert elsewhere.status_code == 422 and "isn’t yours" in elsewhere.json()["detail"]
    assert demo.post("/v1/uploads/sample", json={"name": "nope"}).status_code == 404


def test_another_creator_cannot_see_or_change_a_simulation(demo):
    take1 = demo.post("/v1/uploads/sample", json={"name": "take1"}).json()
    sim = simulate(demo, take1["path"], caption=take1["caption"])
    other = signed_in("someone.else@example.com")
    other.post("/v1/onboarding/username", json={"username": "new.creator"})
    assert other.get(f"/v1/simulations/{sim['id']}").status_code == 404
    edit = sim["edits"][0]["id"]
    assert other.post(f"/v1/simulations/{sim['id']}/edits/{edit}/apply").status_code == 404
    assert (
        other.post(
            f"/v1/simulations/{sim['id']}/rerun", json={"upload_path": take1["path"]}
        ).status_code
        == 404
    )
    assert other.post("/v1/simulations", json={"upload_path": take1["path"]}).status_code == 422
