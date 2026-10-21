"""Mock stand-in for T14 (Ask Curo): picks tools from the intent, the screen and the words of
the question, then answers only from what the tools returned. Like the real model it sees
only its input (the conversation, the tool specs and results), and it streams its reply.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

from curo.schemas.tasks import ChatChunk, T14Input, ToolCall

METRIC_WORDS = {
    "shares": r"\bshar|\bsend",
    "comments": r"\bcomment",
    "likes": r"\blike",
    "views": r"\bview|\bwatch(?:ed|es)?\b(?! time)",
}
STORYBOARD = re.compile(
    r"\b(shot|frame|camera|angle|tripod|lighting|light|transition|film)\b", re.I
)
# Plain words → the DNA change a what-if tests (the real model fills these from the tool spec).
WHAT_IF_CHANGES = (
    (
        r"final look first|open(?:ing)? (?:on|with) the (?:final|finished) look|payoff (?:earlier|first|sooner)|show the result first",
        {"payoff_band": "under_2s", "opening_style": "final_look_first"},
    ),
    (r"send|share prompt|ask (?:people|them|viewers) to share", {"cta_type": "share_prompt"}),
    (r"comment prompt|ask (?:people|them|viewers) to comment", {"cta_type": "comment_prompt"}),
    (r"choice question|ask (?:which|them to pick)|which one", {"ending": "choice_question"}),
    (r"under 20|very short", {"duration_band": "under_20s"}),
    (r"shorter|trim|cut it down|under 40|30 seconds", {"duration_band": "20_to_40s"}),
    (
        r"on-?screen text|text on screen|labels?|captions on (?:the )?screen",
        {"onscreen_text": "yes"},
    ),
    (r"faster|quicker cuts|cut faster|on the beat", {"pace": "fast"}),
)


def _what_if_change(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for pattern, change in WHAT_IF_CHANGES:
        if re.search(pattern, text, re.I):
            out.update(change)
    return out


def _metric(text: str) -> str | None:
    return next((m for m, p in METRIC_WORDS.items() if re.search(p, text, re.I)), None)


def _call(name: str, args: dict, n: int) -> ChatChunk:
    return ChatChunk(type="tool_call", call=ToolCall(id=f"call_{n}_{name}", name=name, args=args))


def _plan(data: T14Input, message: str) -> list[tuple[str, dict]]:
    ctx, names = data.context, {t.name for t in data.tools}
    text = message.lower()

    def can(name: str) -> bool:
        return name in names

    if ctx.intent == "remember" and can("remember"):
        return [("remember", {"note": message})]
    if ctx.intent == "forget" and can("forget"):
        return [("forget", {"query": message})]
    if ctx.intent == "what_if":
        change = _what_if_change(message)
        if change and can("run_simulation"):
            return [("run_simulation", {"feature_change": change})]
        if not can("run_simulation") and can("score_idea"):
            idea = re.sub(
                r"^\s*what if (?:i|we)?\s*(?:did|made|posted|tried)?\s*", "", message, flags=re.I
            )
            return [("score_idea", {"text": idea.strip(" ?") or message})]
        return []
    if ctx.intent == "change":
        if STORYBOARD.search(message) and can("update_frame"):
            return [("update_frame", {"instruction": message})]
        if can("rewrite_script"):
            return [("rewrite_script", {"instruction": message})]
        return []
    # explain
    order = (
        "lowest"
        if re.search(r"\b(worst|lowest|weakest|flopped)\b", text)
        else "recent"
        if re.search(r"\b(latest|recent|last)\b", text)
        else "best"
    )
    if re.search(r"\b(reels?|videos?|posts?)\b", text) and re.search(
        r"\b(best|top|strongest|worst|lowest|weakest|latest|recent|last|which|flopped)\b", text
    ):
        return [("search_reels", {"order": order, "limit": 3})]
    if can("get_simulation") or can("compare_to_draft"):
        if re.search(r"\b(draft|script|compare|storyboard)\b", text) and can("compare_to_draft"):
            return [("compare_to_draft", {})]
        if re.search(r"\b(time|when|day|post it)\b", text):
            return [("get_simulation", {"section": "time"})]
        if re.search(r"\b(edits?|change|fix|improve|better)\b", text):
            return [("get_simulation", {"section": "edits"})]
        if re.search(r"\b(followers?|new audiences?|audiences?|strangers?)\b", text):
            return [("get_simulation", {"section": "audiences"})]
        metric = _metric(text)
        return [("get_simulation", {"section": metric or "summary"})]
    if re.search(
        r"\b(patterns?|works?|working|tips?|should i|helps?|hurts?|holds?)\b", text
    ) and can("get_pattern_cards"):
        args: dict = {}
        metric = _metric(text)
        if metric:
            args["metric"] = metric
        if re.search(r"\b(hurts?|hold\w* (?:me|it) back|avoid|worst)\b", text):
            args["direction"] = "hurts"
        elif re.search(r"\b(works?|working|best|helps?|boosts?)\b", text):
            args["direction"] = "works"
        return [("get_pattern_cards", args)]
    if ctx.screen == "studio:validate" and can("score_idea"):  # an idea to score
        idea = re.sub(
            r"^\s*(?:is|would|will|does)\s+(?:this|it)\s+(?:a\s+)?(?:good\s+)?(?:idea)?[:,]?\s*",
            "",
            message,
            flags=re.I,
        )
        return [("score_idea", {"text": idea.strip(" ?") or message})]
    if re.search(
        r"\b(opportunit\w*|trend\w*|topic|festival|ganpati|navratri|score)\b", text
    ) and can("get_opportunity"):
        return [("get_opportunity", {})]
    if can("get_draft"):
        line = re.search(r"\bline (\d+)\b", text)
        if line:
            return [("get_draft", {"line": int(line.group(1))})]
        if re.search(r"\b(first line|hook|opening|open with)\b", text):
            return [("get_draft", {"line": 1})]
        if re.search(r"\b(last line|ending|end with|call to action|cta)\b", text):
            return [("get_draft", {"line": "last"})]
        return [("get_draft", {})]
    if can("get_pattern_cards"):
        return [("get_pattern_cards", {})]
    return []


LEADS = {
    "search_reels": "Here’s what your reels show.",
    "get_pattern_cards": "This is what tends to work for you.",
    "run_simulation": "Re-scored on the same similar reels:",
    "compare_to_draft": "Compared with your Studio draft:",
}


def _reply(data: T14Input, results: list[tuple[str, dict]]) -> str:
    if not results:
        if data.context.intent == "what_if":
            return (
                "Which change should I test: the opening, the ending, the length, the pace or "
                "on-screen text?"
            )
        return "I couldn’t find anything in your records for that. Try asking about a reel, a pattern or this draft."
    name, first = results[0]
    if "error" in first and not first.get("facts"):
        return first["error"]
    data_ = first.get("data") or {}
    if name == "remember":
        avoid = data_.get("avoids") or []
        tail = f" New ideas will leave out anything about {', '.join(avoid)}." if avoid else ""
        return f"Got it. I’ll remember: “{data_.get('remembered')}”.{tail} You can see or delete it in Settings."
    if name == "forget":
        gone = data_.get("forgotten") or []
        if not gone:
            return "There was nothing like that to forget."
        return "Done. I’ve forgotten: " + "; ".join(f"“{g}”" for g in gone) + "."
    if name in ("rewrite_script", "update_frame"):
        what = "script" if name == "rewrite_script" else "storyboard frame"
        return f"On it: Curo is changing the {what} now. The new version will appear in your Studio draft."
    facts: list[str] = []
    for _, r in results:
        facts.extend(r.get("facts") or [])
    lead = LEADS.get(name)
    body = " ".join(facts[:4])
    return f"{lead} {body}" if lead else body


def t14(data: T14Input) -> Iterator[ChatChunk]:
    last_user = max(i for i, m in enumerate(data.messages) if m.role == "user")
    message = data.messages[last_user].content
    after = data.messages[last_user + 1 :]
    tool_turns = [m for m in after if m.role == "tool"]
    if not tool_turns:
        plan = _plan(data, message)
        if plan:
            for n, (name, args) in enumerate(plan):
                yield _call(name, args, n)
            return
    results = []
    for m in tool_turns:
        try:
            results.append((m.name or "", json.loads(m.content)))
        except json.JSONDecodeError:
            results.append((m.name or "", {"error": m.content}))
    text = _reply(data, results)
    words = text.split(" ")
    for i in range(0, len(words), 3):  # streamed a few words at a time, like the real model
        yield ChatChunk(
            type="text", text=" ".join(words[i : i + 3]) + (" " if i + 3 < len(words) else "")
        )
