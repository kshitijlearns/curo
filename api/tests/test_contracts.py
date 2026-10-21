"""Contract tests (MVP doc §4, §12): recorded real responses, replayed through the real
providers' parsers. Recordings come from tools/record_contracts.py once keys exist; until
then the replay test is skipped and the parsers are checked on responses shaped like the
vendors' documented formats."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

from curo.config import REPO_ROOT
from curo.providers import contracts
from curo.providers.embedding.gemini import EmbeddingError, parse_embeddings
from curo.providers.llm import claude
from curo.providers.llm.base import LLMError
from curo.providers.video.base import VideoUnderstandingError
from curo.providers.video.gemini import parse_response
from curo.schemas.tasks import T4, ChatContext, ChatTurn, T14Input, ToolCall, ToolSpec

RECORDINGS = sorted((Path(__file__).parent / "contracts").rglob("*.json"))


@pytest.mark.parametrize(
    "path",
    RECORDINGS
    or [
        pytest.param(
            None,
            marks=pytest.mark.skip(
                reason="no recorded responses yet: run tools/record_contracts.py once keys exist"
            ),
        )
    ],
    ids=lambda p: str(p.relative_to(Path(__file__).parent / "contracts")) if p else "none",
)
def test_a_recorded_response_still_matches_the_contract(path):
    recording = json.loads(path.read_text(encoding="utf-8"))
    assert recording["kind"] in contracts.kinds(), f"unknown kind {recording['kind']}"
    contracts.check(recording)


def test_every_recording_kind_has_a_parser():
    kinds = contracts.kinds()
    assert "public_data/apify/reels" in kinds and "public_data/brightdata/hashtag" in kinds
    assert {"video/gemini", "embedding/gemini", "llm/claude/T3", "llm/claude/T14"} <= set(kinds)
    assert "llm/claude/T1" not in kinds  # T1 is Gemini's


# ------------------------------------------------------------------ Claude (Messages API)


def message(content, stop="end_turn", **extra):
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "content": content,
        "stop_reason": stop,
        "usage": {"input_tokens": 10, "output_tokens": 5},
        **extra,
    }


def test_a_structured_answer_is_read_into_the_tasks_schema():
    raw = message(
        [
            {"type": "thinking", "thinking": ""},
            {"type": "text", "text": '{"label": "Festive styling"}'},
        ]
    )
    assert claude.parse_message(T4, raw).label == "Festive styling"
    recording = {"kind": "llm/claude/T4", "request": {}, "response": raw}
    assert contracts.check(recording).label == "Festive styling"


@pytest.mark.parametrize(
    ("raw", "problem"),
    [
        (message([{"type": "text", "text": '{"label": ""}'}]), "schema"),
        (message([{"type": "text", "text": "Festive styling"}]), "schema"),
        (message([], stop="refusal", stop_details={"category": "cyber"}), "declined"),
        (message([{"type": "text", "text": '{"lab'}], stop="max_tokens"), "cut off"),
    ],
)
def test_an_answer_that_breaks_the_contract_is_an_error_never_a_guess(raw, problem):
    with pytest.raises(LLMError, match=problem):
        claude.parse_message(T4, raw)


def test_an_ask_curo_turn_reads_as_words_then_tool_calls():
    raw = message(
        [
            {"type": "thinking", "thinking": ""},
            {"type": "text", "text": "Let me look at your reels."},
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "search_reels",
                "input": {"query": "kurta"},
            },
        ],
        stop="tool_use",
    )
    chunks = claude.parse_chat_message(raw)
    assert [c.type for c in chunks] == ["text", "tool_call"]
    assert chunks[1].call == ToolCall(id="toolu_1", name="search_reels", args={"query": "kurta"})


def test_ask_curo_turns_are_sent_in_the_messages_apis_shape():
    data = T14Input(
        context=ChatContext(screen="home", intent="explain"),
        messages=[
            ChatTurn(role="user", content="Which reel did best?"),
            ChatTurn(
                role="assistant",
                tool_calls=[
                    ToolCall(id="t1", name="search_reels", args={}),
                    ToolCall(id="t2", name="get_pattern_cards", args={}),
                ],
            ),
            ChatTurn(role="tool", tool_call_id="t1", name="search_reels", content='{"facts": []}'),
            ChatTurn(role="tool", tool_call_id="t2", name="get_pattern_cards", content="{}"),
        ],
        tools=[
            ToolSpec(name="search_reels", description="Find reels", input_schema={"type": "object"})
        ],
        retry_note="Use only numbers from the tools.",
    )
    sent = claude.to_claude_messages(data)
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert [b["type"] for b in sent[1]["content"]] == ["tool_use", "tool_use"]
    # Both results of one turn go back in one message, as the API expects.
    assert [b["tool_use_id"] for b in sent[2]["content"]] == ["t1", "t2"]
    assert claude.to_claude_tools(data)[0]["name"] == "search_reels"
    system = claude.chat_system(data, "PROMPT")
    assert system.startswith("PROMPT") and '"screen":"home"' in system and "held back" in system


# ------------------------------------------------------------------ Gemini


def gemini(text, finish="STOP", **extra):
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}],
        **extra,
    }


def test_a_gemini_video_answer_is_read_into_t1():
    t1 = {
        "duration_s": 32,
        "transcript": [{"t": 0.2, "word": "Teen"}],
        "audio_type": "voiceover",
        "first_payoff_s": 1.8,
    }
    out = parse_response(gemini(json.dumps(t1)))
    assert out.first_payoff_s == 1.8 and out.transcript_text() == "Teen"


@pytest.mark.parametrize(
    "raw",
    [
        gemini("{}", finish="MAX_TOKENS"),
        gemini('{"audio_type": "podcast"}'),
        {"promptFeedback": {"blockReason": "SAFETY"}},
        {"candidates": []},
    ],
)
def test_a_gemini_answer_that_breaks_the_contract_is_an_error(raw):
    with pytest.raises(VideoUnderstandingError):
        parse_response(raw)


def test_gemini_vectors_are_checked_and_normalised():
    raw = {"embeddings": [{"values": [3.0, 4.0] + [0.0] * 766}, {"values": [1.0] * 768}]}
    vectors = parse_embeddings(raw)
    assert vectors[0][:2] == [0.6, 0.8]
    assert all(abs(math.sqrt(sum(x * x for x in v)) - 1) < 1e-9 for v in vectors)
    assert contracts.check(
        {"kind": "embedding/gemini", "request": {"texts": ["a", "b"]}, "response": raw}
    )
    with pytest.raises(EmbeddingError, match="768"):
        parse_embeddings({"embeddings": [{"values": [1.0] * 3072}]})
    with pytest.raises(contracts.ContractBroken, match="one vector per text"):
        contracts.check({"kind": "embedding/gemini", "request": {"texts": ["a"]}, "response": raw})


# ------------------------------------------------------------------ public data


def test_public_data_parsers_wait_for_the_chosen_actors():
    """Their mapping depends on the actors picked when the key arrives (INTEGRATION.md)."""
    with pytest.raises(NotImplementedError):
        contracts.check({"kind": "public_data/apify/reels", "request": {}, "response": [{}]})


def test_a_hidden_count_must_come_back_as_unknown(monkeypatch):
    from curo.providers.public_data import apify
    from curo.providers.public_data.base import ReelData

    def reels(items):
        return [
            ReelData(
                ig_media_id="1",
                shortcode="abc",
                permalink="https://x/abc",
                posted_at="2027-08-20T00:00:00Z",
                likes=0,
                likes_hidden=True,
            )
        ]

    monkeypatch.setattr(apify, "parse_reels", reels)
    with pytest.raises(contracts.ContractBroken, match="hidden likes"):
        contracts.check({"kind": "public_data/apify/reels", "request": {}, "response": [{}]})


# ------------------------------------------------------------------ the recorder


def recorder():
    spec = importlib.util.spec_from_file_location(
        "record_contracts", REPO_ROOT / "tools" / "record_contracts.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_recorder_keeps_only_the_test_accounts_handle():
    scrub = recorder().Scrubber("my.test.account")
    items = [
        {
            "ownerUsername": "my.test.account",
            "caption": "Styled by @someone.else",
            "latestComments": [
                {
                    "ownerUsername": "a.fan",
                    "text": "@best.friend look!",
                    "ownerProfilePicUrl": "https://cdn/x.jpg",
                }
            ],
        },
        {"ownerUsername": "a.fan"},
    ]
    out = scrub(items)
    assert out[0]["ownerUsername"] == "my.test.account"
    assert out[0]["caption"] == "Styled by @user_1"
    comment = out[0]["latestComments"][0]
    assert comment["ownerUsername"] == "user_2" and comment["text"] == "@user_3 look!"
    assert comment["ownerProfilePicUrl"] == ""
    assert out[1]["ownerUsername"] == "user_2"  # the same person keeps the same placeholder
    assert "a.fan" not in json.dumps(out) and "best.friend" not in json.dumps(out)


def test_a_recording_names_its_kind_and_source_and_replays(tmp_path):
    raw = message([{"type": "text", "text": '{"label": "Hauls"}'}])
    path = recorder().write_recording(
        "llm/claude/T4", "sample", {"model": "claude-haiku"}, {"task": "T4.v1"}, raw, root=tmp_path
    )
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path == tmp_path / "llm" / "claude" / "T4" / "sample.json"
    assert saved["kind"] == "llm/claude/T4" and saved["source"] == {"model": "claude-haiku"}
    assert contracts.check(saved).label == "Hauls"


def test_task_inputs_are_captured_for_recording(tmp_path, monkeypatch):
    from curo import providers
    from curo.config import get_settings
    from curo.providers.llm.base import CAPTURE_PER_TASK

    monkeypatch.setenv("CAPTURE_TASK_INPUTS", str(tmp_path))
    get_settings.cache_clear()
    llm = providers.get_llm()
    for _ in range(CAPTURE_PER_TASK + 2):
        llm.run(T4, {"kind": "reels", "samples": ["One kurta, five dupattas"]})
    saved = sorted((tmp_path / "T4").glob("*.json"))
    assert len(saved) == CAPTURE_PER_TASK  # the first few only
    assert json.loads(saved[0].read_text(encoding="utf-8"))["samples"] == [
        "One kurta, five dupattas"
    ]
