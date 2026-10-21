"""Phase 8: Ask Curo's routing, memory and number check, without a database."""

import uuid

import pytest

from curo.providers.llm import mock_chat
from curo.schemas.tasks import ChatContext, ChatTurn, T14Input, ToolSpec
from curo.services.assistant import intent, memory
from curo.services.assistant.loop import _sentences, _State
from curo.services.assistant.tools import fmt_count, fmt_rate


@pytest.mark.parametrize(
    ("message", "screen", "expected"),
    [
        ("Why is the first line there?", "studio:script", "explain"),
        ("Which of my reels did best?", "sim:result", "explain"),
        ("make the hook punchier", "studio:script", "change"),
        ("shorter", "studio:script", "change"),
        ("Can you make the ending a save prompt?", "studio:script", "change"),
        ("Could you use a tripod for the opening shot?", "studio:storyboard", "change"),
        ("What if I end with a send prompt?", "sim:result", "what_if"),
        ("would it do better if I cut it to 30 seconds", "sim:result", "what_if"),
        ("Never suggest dance trends", "studio:ideas", "remember"),
        ("Remember that I film on weekends", "sim:result", "remember"),
        ("I always shoot on a tripod", "studio:script", "remember"),
        ("I never get comments, why?", "sim:result", "explain"),  # a question, not a preference
        ("forget the dance thing", "studio:ideas", "forget"),
        ("How many saves will it get?", "sim:result", "hidden"),
        ("what's my reach going to be", "sim:result", "hidden"),
        ("ok", "sim:result", "unclear"),
        ("hmm?", "studio:script", "unclear"),
        ("Pune monsoon outfits under 2000", "studio:validate", "change"),
    ],
)
def test_the_classifier_decides_what_the_creator_wants(message, screen, expected):
    assert intent.classify(message, screen) == expected


def test_a_change_on_a_studio_screen_goes_to_that_step():
    assert intent.handoff("change", "studio:script")
    assert intent.handoff("change", "studio:validate")
    assert not intent.handoff("change", "sim:result")  # the assistant's rewrite tool there
    assert not intent.handoff("explain", "studio:script")


def test_stated_preferences_become_rules_curo_can_apply():
    assert memory.note_from("remember that I never do dance trends.") == "I never do dance trends"
    assert memory.avoided("Never suggest dance trends") == ["dance"]
    assert memory.avoided("don't show me haul ideas please") == ["haul"]
    assert memory.avoided("I film on weekends") == []
    assert memory.key_for("Never suggest dance trends") == "avoid:dance"
    assert memory.key_for("Keep scripts short") == "prefer:shorter_scripts"
    assert memory.key_for("I film on weekends").startswith("note:")
    assert memory.mentions("A dancing transition for Ganpati", {"dance"}) is None
    assert memory.mentions("Two dance looks", {"dance"}) == "dance"
    assert memory.mentions("Hauls under 2000", {"haul"}) == "haul"
    rows = [
        memory.Memory(uuid.uuid4(), "avoid:dance", "Never suggest dance trends", "stated"),
        memory.Memory(uuid.uuid4(), memory.LEARNED_SHORTER, "Starts scripts shorter", "learned"),
    ]
    assert memory.avoided_words(rows) == {"dance"}
    assert memory.prefers_shorter(rows)


def test_shorter_scripts_are_learned_only_from_repeated_shortening():
    assert memory.learned(["shorten", "rewrite_hook", "shorten", "shorten"]) == [
        (
            memory.LEARNED_SHORTER,
            "Starts scripts shorter: you shortened 3 of your last 4 script changes.",
        )
    ]
    assert memory.learned(["shorten", "shorten"]) == []  # twice isn't a habit
    assert memory.learned(["shorten", "x", "x", "shorten", "x", "shorten"])  # half: a habit
    assert memory.learned(["shorten", "x", "x", "shorten", "x", "x", "shorten"]) == []  # 2 of 6


def _state(facts: list[str]) -> _State:
    return _State(
        request=None,  # type: ignore[arg-type]
        creator={},
        intent="explain",
        context=ChatContext(screen="sim:result", intent="explain"),
        messages=[],
        tools=[],
        permitted=set(),
        allowed_text=["Will people share it?"],
        facts=facts,
    )


def test_every_sentence_is_checked_against_the_tool_facts():
    state = _state(["Shares per view: 0.87% estimated, +20% against your usual 0.73%."])
    assert state.check("Shares are estimated at 0.87%, +20% against your usual.") is None
    planted = state.check("It got 9.7× your usual shares.")
    assert planted and "9.7" in planted
    assert state.check("It should get more saves than usual.")  # not public
    assert state.check("Your caption “Save this for later” fits.") is None  # quoted, not a claim
    assert state.check("A save prompt could help.") is None


def test_the_reply_streams_in_whole_sentences():
    done, rest = _sentences("It got 1.66× your usual comments. Your next", final=False)
    assert done == ["It got 1.66× your usual comments."] and rest == "Your next"
    assert _sentences("Last one.", final=True) == (["Last one."], "")


def test_counts_and_rates_are_written_as_the_app_shows_them():
    assert [fmt_count(x) for x in (504, 1189, 62150.2, 128_000, 1_250_000)] == [
        "504",
        "1.2K",
        "62K",
        "128K",
        "1.2M",
    ]
    assert fmt_count(None) == "unknown"
    assert (fmt_rate(0.053), fmt_rate(0.0073)) == ("5.3%", "0.73%")


def _ask(message: str, screen: str, intent_: str, tools: list[str], results=None):
    msgs = [ChatTurn(role="user", content=message)]
    for name, content in results or []:
        msgs.append(ChatTurn(role="tool", name=name, content=content, tool_call_id="c"))
    data = T14Input(
        context=ChatContext(screen=screen, intent=intent_),
        messages=msgs,
        tools=[ToolSpec(name=t, description="", input_schema={}) for t in tools],
    )
    return list(mock_chat.t14(data))


def test_the_mock_model_calls_tools_first_then_answers_from_them():
    chunks = _ask("What if I end with a send prompt?", "sim:result", "what_if", ["run_simulation"])
    assert [c.call.name for c in chunks] == ["run_simulation"]
    assert chunks[0].call.args == {"feature_change": {"cta_type": "share_prompt"}}
    answered = _ask(
        "What if I end with a send prompt?",
        "sim:result",
        "what_if",
        ["run_simulation"],
        [("run_simulation", '{"facts": ["It moves from 48 to 54 out of 100."], "data": {}}')],
    )
    text = "".join(c.text for c in answered)
    assert all(c.type == "text" for c in answered) and "48 to 54" in text
    asked = _ask("What if it was better?", "sim:result", "what_if", ["run_simulation"])
    assert "Which change should I test" in "".join(c.text for c in asked)
