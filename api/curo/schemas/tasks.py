"""AI task catalog (MVP doc §10): one input and one output schema per task.

Every model call returns JSON matching its task's output schema (Claude through tool use,
Gemini through a response schema), and every stored output carries the task's version so
results can be traced and re-run. Mocks return the same schemas. Prompts live in
``api/prompts/<ID>_<name>.v<version>.md``.

T1–T4 understand reels (Phase 3), T5 names opportunities (Phase 5), T6–T8 and T11–T13 are
the Studio (Phase 6); T10 writes explanations; T15 proposes the Simulator's edits (Phase 7);
T14 is Ask Curo (Phase 8), a conversation with tools rather than one structured answer.
v2 adds T16 (trend cards) and T18–T22 (the Simulator's AI audience), v2.1 T23 (recap copy),
v2.2 T25–T29 (Follower Personas). T17 (audience segments) and T24 (follower ideas) were
retired in v2.2: the personas replaced both.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from curo.schemas.taxonomy import ALL_FIELDS, UNKNOWN


def _choice(field: str):
    """A Literal of one taxonomy field's values plus "unknown"."""
    return Literal[(*ALL_FIELDS[field], UNKNOWN)]  # type: ignore[valid-type]


@dataclass(frozen=True)
class TaskSpec:
    id: str
    version: int
    name: str
    # "video" = Gemini; "fast" = Claude Haiku; "main" = Claude Sonnet;
    # "agents" = CLAUDE_MODEL_AGENTS (the Simulator's AI audience)
    tier: Literal["video", "fast", "main", "agents"]
    input: type[BaseModel]
    output: type[BaseModel]

    @property
    def prompt_file(self) -> str:
        return f"{self.id}_{self.name}.v{self.version}.md"

    @property
    def tag(self) -> str:
        return f"{self.id}.v{self.version}"


# ------------------------------------------------------------------ T1 · watch a video (Gemini)


class Word(BaseModel):
    t: float  # seconds from the start
    word: str


class Shot(BaseModel):
    start: float
    end: float


class OnscreenText(BaseModel):
    t: float
    text: str


class SecondDescription(BaseModel):
    t: float
    description: str


AudioType = Literal["original_speech", "voiceover", "trending_audio", "music_only", "mixed"]


class T1Input(BaseModel):
    bucket: str
    path: str  # where the video sits in storage
    duration_s: float | None = None
    mime_type: str = "video/mp4"


class T1Output(BaseModel):
    duration_s: float | None = None
    transcript: list[Word] = Field(default_factory=list)
    shots: list[Shot] = Field(default_factory=list)
    onscreen_text: list[OnscreenText] = Field(default_factory=list)
    seconds: list[SecondDescription] = Field(default_factory=list)
    audio_type: AudioType | None = None
    first_payoff_s: float | None = None

    def transcript_text(self) -> str:
        return " ".join(w.word for w in self.transcript)


# ------------------------------------------------------------------ T2 · extract DNA (Claude Haiku)


class T2Input(BaseModel):
    understanding: T1Output
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    duration_s: float | None = None


class ContentDNA(BaseModel):
    cluster: _choice("cluster") = UNKNOWN
    context: _choice("context") = UNKNOWN
    characters: _choice("characters") = UNKNOWN
    core_tension: _choice("core_tension") = UNKNOWN
    key_entities: list[str] = Field(default_factory=list)


class ProductionDNA(BaseModel):
    format: _choice("format") = UNKNOWN
    hook_type: _choice("hook_type") = UNKNOWN
    hook_text: str = ""
    opening_style: _choice("opening_style") = UNKNOWN
    narrative: _choice("narrative") = UNKNOWN
    ending: _choice("ending") = UNKNOWN
    cta_type: _choice("cta_type") = UNKNOWN
    pov: _choice("pov") = UNKNOWN
    camera: _choice("camera") = UNKNOWN
    cuts_per_10s: float | None = None
    audio: _choice("audio") = UNKNOWN
    visual_style: _choice("visual_style") = UNKNOWN
    setting: _choice("setting") = UNKNOWN


class T2Output(BaseModel):
    content: ContentDNA
    production: ProductionDNA
    # field name → 0..1. Fields below 0.6 are stored as "unknown" (services.dna).
    confidence: dict[str, float] = Field(default_factory=dict)


# ------------------------------------------------------------------ T3 · label comments (Claude Haiku, batch)

Intent = Literal[
    "question",
    "request",
    "thats_me",
    "tags_friend",
    "plans_to_save",
    "disagreement",
    "praise",
    "other",
]
Sentiment = Literal["positive", "neutral", "negative"]


class CommentIn(BaseModel):
    id: str
    text: str


class T3Input(BaseModel):
    comments: list[CommentIn] = Field(max_length=200)


class CommentLabel(BaseModel):
    id: str
    is_bot: bool
    sentiment: Sentiment
    intent: Intent
    # For requests and questions: a short phrase naming what is asked, e.g. "wants budget versions".
    theme: str | None = None


class T3Output(BaseModel):
    labels: list[CommentLabel]


# ------------------------------------------------------------------ T4 · name a group (Claude Haiku)


class T4Input(BaseModel):
    kind: Literal["reels", "comments"]
    samples: list[str] = Field(min_length=1, max_length=12)


class T4Output(BaseModel):
    label: str = Field(min_length=1, max_length=48)


# ------------------------------------------------------------------ T5 · name and explain an opportunity (Claude Sonnet)


class T5Input(BaseModel):
    sources: list[str]  # where it was found: competitor, trend, audience, your_content
    keywords: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    festival: str | None = None
    themes: list[str] = Field(default_factory=list)  # e.g. "wants budget versions"
    follow_up_of: str | None = None  # title of the reel to follow up
    subcluster: str | None = None
    example_titles: list[str] = Field(default_factory=list, max_length=6)
    lead_facts: list[str] = Field(min_length=1)  # the two biggest score contributors' facts
    fit_facts: list[str] = Field(default_factory=list)  # creator-fit facts


class T5Output(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    description: str = Field(min_length=1, max_length=400)
    why_it_fits: str = Field(min_length=1, max_length=240)


# ------------------------------------------------------------------ T10 · write an explanation (Claude Sonnet)


class T10Input(BaseModel):
    kind: str  # what is being explained, e.g. "comments_high" (an audience card)
    title: str  # the card's fixed title, for context
    facts: list[str] = Field(min_length=1, max_length=8)  # computed facts; the only numbers allowed


class T10Output(BaseModel):
    text: str = Field(min_length=1, max_length=240)


# ------------------------------------------------------------------ Studio: shared pieces

Behaviour = Literal["views", "likes", "comments", "shares"]


class VoiceProfile(BaseModel):
    """How the creator talks, measured from their own transcripts (services.voice)."""

    words_per_second: float
    sentence_words: float  # median words per sentence
    language: Literal["en", "hinglish", "hi", "mixed"] = "en"
    phrases: list[str] = Field(default_factory=list)  # lines they keep coming back to
    energy: Literal["calm", "steady", "high"] = "steady"
    reels: int = 0  # how many transcripts it was measured from


# ------------------------------------------------------------------ T6 · generate idea candidates (Claude Sonnet)


class EvidenceItem(BaseModel):
    id: str  # "sub:…", "card:…", "theme:…", "trend:…", "opp:…", "format:…"
    kind: Literal["opportunity", "subcluster", "pattern", "theme", "trend", "format"]
    text: str  # a computed fact, e.g. "“One item, many looks” reels: 1.38× your usual views"
    format: str | None = None  # the usual format of a sub-cluster
    samples: list[str] = Field(default_factory=list, max_length=5)  # comments or titles


class T6Input(BaseModel):
    topic: str | None = None  # the opportunity's name; None for an idea of the creator's own
    festival: str | None = None
    keywords: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=60)
    creator_formats: list[str] = Field(default_factory=list)  # most made first
    # The creator's own note or idea. Its topic, format, tone and limits are fixed rules: every
    # candidate keeps the creator's core thought and differs in angle or format.
    creator_input: str | None = None
    # Topics the creator asked never to be suggested (creator memory). Candidates naming them
    # are also dropped in code.
    avoid: list[str] = Field(default_factory=list)
    # "read": return the creator's idea itself (one candidate, text as written), described.
    mode: Literal["generate", "read"] = "generate"
    count: int = Field(15, ge=1, le=20)


class IdeaCandidate(BaseModel):
    text: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=320)
    angle: str = Field(default="", max_length=80)
    format: _choice("format") = UNKNOWN
    hook_type: _choice("hook_type") = UNKNOWN
    target_behaviour: Behaviour = "views"
    evidence_ids: list[str] = Field(default_factory=list)  # candidates citing none are dropped


class T6Output(BaseModel):
    candidates: list[IdeaCandidate] = Field(min_length=1, max_length=20)


# ------------------------------------------------------------------ T7 · write a script (Claude Sonnet)

BeatRole = Literal["hook", "setup", "item", "ending"]
ScriptAction = Literal[
    "write",
    "regenerate",
    "rewrite_hook",
    "change_tone",
    "shorten",
    "expand",
    "change_ending",
    "edit_line",
]


class BeatPlan(BaseModel):
    id: str
    role: BeatRole
    purpose: str  # e.g. "look 2 of 3", "a choice question to the audience"
    words: int = Field(ge=1)  # this beat's share of the word budget
    text: str | None = None  # current text, for revisions


class T7Input(BaseModel):
    idea: str
    angle: str = ""
    format: str
    topic: str | None = None
    voice: VoiceProfile
    beats: list[BeatPlan] = Field(min_length=1, max_length=12)
    # Transcripts of the creator's strongest reels of this format: their structure and voice.
    examples: list[str] = Field(default_factory=list, max_length=3)
    action: ScriptAction = "write"
    rewrite: list[str] = Field(default_factory=list)  # beat ids to rewrite; others stay as given
    direction: str | None = None  # the creator's own words
    tone: Literal["default", "conversational"] = "default"
    variant: int = 0  # a different take on each regeneration


class ScriptBeat(BaseModel):
    id: str
    text: str = Field(min_length=1, max_length=400)


class T7Output(BaseModel):
    beats: list[ScriptBeat] = Field(min_length=1)


# ------------------------------------------------------------------ T8 · tag script notes (Claude Haiku)

NoteType = Literal["hook", "comments", "likes", "shares"]


class BeatText(BaseModel):
    id: str
    role: BeatRole
    text: str


class CardRef(BaseModel):
    id: str
    feature: str
    value: str
    metric: str
    effect: float


class T8Input(BaseModel):
    beats: list[BeatText] = Field(min_length=1)
    cards: list[CardRef] = Field(default_factory=list)


class NoteLabel(BaseModel):
    beat_id: str
    note_type: NoteType
    pattern_card_id: str


class T8Output(BaseModel):
    notes: list[NoteLabel] = Field(default_factory=list)


# ------------------------------------------------------------------ T11 · build a storyboard (Claude Sonnet)

IconKey = Literal[
    "closeup", "flatlay", "look1", "look2", "look3", "rewind", "mirror", "cta", "triptych"
]
StoryboardAction = Literal[
    "build",
    "change_shot",
    "another_opening",
    "easier",
    "change_transition",
    "pacing",
    "visual_treatment",
]


class FrameBeat(BaseModel):
    id: str
    role: BeatRole
    text: str
    seconds: float


class Toolkit(BaseModel):
    """The camera setups, places and light found in the creator's own Production DNA."""

    cameras: list[str] = Field(default_factory=list)  # most used first
    settings: list[str] = Field(default_factory=list)
    lighting: list[str] = Field(default_factory=list)


class FrameOut(BaseModel):
    beat_id: str
    shot_type: str = Field(max_length=80)  # "Full-length · tripod at chest height"
    camera: _choice("camera") = UNKNOWN
    setting: _choice("setting") = UNKNOWN
    lighting: _choice("visual_style") = UNKNOWN
    instruction: str = Field(max_length=300)
    onscreen_text: str = Field(default="", max_length=60)
    transition: str = Field(default="", max_length=60)
    icon_key: IconKey = "closeup"
    needs_helper: bool = False  # a second person to film it
    outfit_change: bool = False  # props or outfit changed for this frame


class T11Input(BaseModel):
    format: str
    beats: list[FrameBeat] = Field(min_length=1)
    toolkit: Toolkit
    devices: list[str] = Field(default_factory=list)  # proven visual devices, as plain lines
    action: StoryboardAction = "build"
    frames: list[FrameOut] = Field(default_factory=list)  # current frames, for revisions
    targets: list[str] = Field(default_factory=list)  # beat ids whose frames change
    direction: str | None = None
    variant: int = 0


class T11Output(BaseModel):
    frames: list[FrameOut] = Field(min_length=1)


# ------------------------------------------------------------------ T12 · captions and hashtags (Claude Sonnet)

CaptionJob = Literal["comments", "likes", "shares"]


class CaptionStyle(BaseModel):
    """The creator's own caption habits, from their past captions."""

    words: int = 14  # median caption length in words (hashtags left out)
    emoji: int = 1  # median emoji per caption
    language: Literal["en", "hinglish", "hi", "mixed"] = "en"


class TagOption(BaseModel):
    tag: str
    kind: Literal["broad", "niche", "local", "series"]
    score: float


class T12Input(BaseModel):
    idea: str
    topic: str | None = None
    hook: str  # the first line restates it
    beats: list[str] = Field(min_length=1)
    ending: str  # the script's call to action; the caption's must match, not repeat it
    search_phrases: list[str] = Field(default_factory=list, max_length=4)
    style: CaptionStyle = CaptionStyle()
    hashtags: list[TagOption] = Field(default_factory=list)  # scored candidates
    variant: Literal["default", "shorter", "playful", "question", "polish"] = "default"
    own_caption: str | None = None  # "dump your caption idea": kept, polished only if asked
    direction: str | None = None


class CaptionOut(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    job: CaptionJob


class T12Output(BaseModel):
    captions: list[CaptionOut] = Field(min_length=1, max_length=3)
    hashtags: list[str] = Field(default_factory=list, max_length=5)


# ------------------------------------------------------------------ T13 · route a revision (Claude Haiku)

RevisionStep = Literal["ideas", "script", "storyboard", "caption"]


class T13Input(BaseModel):
    step: RevisionStep
    instruction: str = Field(min_length=1, max_length=1000)
    items: list[str] = Field(default_factory=list)  # "b3: Look 2 – a modern twist." / frames
    current: str | None = None  # the item on screen (e.g. the frame being viewed)


class T13Output(BaseModel):
    action: str  # one of the step's actions (services.revisions.ACTIONS)
    targets: list[str] = Field(default_factory=list)  # beat or frame ids
    params: dict[str, str | float] = Field(default_factory=dict)


# ------------------------------------------------------------------ T14 · Ask Curo (Claude Sonnet, tools)

# What the creator wants (services/assistant/intent.py decides before the model is called).
Intent = Literal["explain", "change", "what_if", "remember", "forget", "unclear", "hidden"]


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ChatTurn(BaseModel):
    """One message the model sees: the creator's, its own (text and tool calls), or a tool's
    result (JSON, answering ``tool_call_id``)."""

    role: Literal["user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


class ChatContext(BaseModel):
    screen: str  # "studio:script", "sim:result" …
    intent: Intent
    memory: list[str] = Field(default_factory=list)  # the creator's stated and learned preferences
    project: str | None = None  # the open draft, in a line
    simulation: str | None = None  # the simulation on screen, in a line


class T14Input(BaseModel):
    context: ChatContext
    messages: list[ChatTurn] = Field(min_length=1)
    tools: list[ToolSpec] = Field(default_factory=list)
    # After a reply failed the number check: what to fix in the next attempt.
    retry_note: str | None = None


class ChatChunk(BaseModel):
    """A piece of the model's streamed turn: words, or a request to call a tool."""

    type: Literal["text", "tool_call"]
    text: str = ""
    call: ToolCall | None = None


# ------------------------------------------------------------------ T15 · propose edits (Claude Sonnet)

Effort = Literal["edit_only", "reshoot"]


class Factor(BaseModel):
    """Something holding a draft back, as the creator's patterns show it."""

    feature: str  # a DNA field or derived band, e.g. "payoff_band"
    current: str  # the draft's value, e.g. "2_to_4s"
    better: str  # the value associated with more, e.g. "under_2s"
    metric: str
    fact: str  # the plain fact behind it


class T15Input(BaseModel):
    format: str
    duration_s: float | None = None
    payoff_s: float | None = None
    script: list[str] = Field(default_factory=list)  # the linked Studio draft's lines
    factors: list[Factor] = Field(default_factory=list, max_length=8)


class EditProposal(BaseModel):
    title: str = Field(min_length=3, max_length=60)
    description: str = Field(min_length=3, max_length=240)
    feature_change: dict[str, str] = Field(min_length=1)  # {"payoff_band": "under_2s"}
    effort: Effort


class T15Output(BaseModel):
    edits: list[EditProposal] = Field(default_factory=list, max_length=8)


# ------------------------------------------------------------------ T16 · name a trend card (Claude Sonnet)


class T16Input(BaseModel):
    niche: str  # "Fashion and styling"
    kind: Literal["festival", "hashtag", "format"]
    label: str  # the festival's name or the tag
    hashtags: list[str] = Field(default_factory=list)
    facts: list[str] = Field(min_length=1, max_length=6)  # the only numbers allowed
    sample_captions: list[str] = Field(default_factory=list, max_length=5)


class T16Output(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    summary: str = Field(min_length=1, max_length=280)
    why_rising: str = Field(min_length=1, max_length=280)
    example_angles: list[str] = Field(min_length=2, max_length=3)


# ------------------------------------------------------------------ registry

# ------------------------------------------------------------------ T18–T22 · the AI audience (v2)


class Segment(BaseModel):
    """One of the creator's 4 Follower Personas, as the Simulator's agents are drawn from it
    (v2.2 §8; the personas replaced T17's segments)."""

    key: str = Field(pattern=r"^[a-z0-9_]{2,40}$")
    label: str = Field(max_length=40)  # "Festive Planner"; never a handle or a real name
    share: float = Field(gt=0, le=1)
    description: str = Field(max_length=300)
    interests: list[str] = Field(default_factory=list, max_length=6)
    intent: str | None = None  # the persona's most common comment intent
    # The persona's behaviour, the middle of its agents' range (0–1): patience, liker,
    # commenter, sharer, saver.
    traits: dict[str, float] = Field(default_factory=dict)


class T18Input(BaseModel):
    """Write N personas for one segment."""

    segment: Segment
    niche: str
    count: int = Field(ge=1, le=1000)
    first_agent_no: int = Field(ge=1)


class Persona(BaseModel):
    agent_no: int
    persona_text: str = Field(max_length=400)
    patience: float = Field(ge=0, le=1)  # how long they give a slow start
    sharer: float = Field(ge=0, le=1)
    commenter: float = Field(ge=0, le=1)
    saver: float = Field(ge=0, le=1)
    liker: float = Field(ge=0, le=1)


class T18Output(BaseModel):
    personas: list[Persona]


class TimelinePoint(BaseModel):
    t: float
    what: str


class Timeline(BaseModel):
    """The video, second by second (from T1), as every agent sees it."""

    duration_s: float | None = None
    hook_s: float | None = None  # the first spoken or on-screen line
    payoff_s: float | None = None
    points: list[TimelinePoint] = Field(default_factory=list)
    caption: str = ""
    has_share_prompt: bool = False
    has_question: bool = False
    has_save_prompt: bool = False


class AgentBrief(BaseModel):
    agent_no: int
    segment: str
    segment_label: str
    persona_text: str
    patience: float
    sharer: float
    commenter: float
    saver: float
    liker: float
    interests: list[str] = Field(default_factory=list)
    intent: str | None = None  # the persona's main comment intent
    persona_id: str | None = None


class T19Input(BaseModel):
    """A batch of up to 100 agents meeting the video in a short feed."""

    run_key: str  # simulation id (or a calibration key): seeds the mock
    timeline: Timeline
    agents: list[AgentBrief] = Field(min_length=1, max_length=100)


class Reaction(BaseModel):
    agent_no: int
    watch_until_s: float = Field(ge=0)
    skipped: bool
    liked: bool = False
    commented: bool = False
    comment_text: str | None = Field(default=None, max_length=200)
    shared: bool = False
    saved: bool = False
    reason: str = Field(max_length=200)


class T19Output(BaseModel):
    reactions: list[Reaction]


class ThreadComment(BaseModel):
    agent_no: int
    text: str


class T20Input(BaseModel):
    """The thread round: engaged agents read the top comments and may reply or like them."""

    run_key: str
    timeline: Timeline
    comments: list[ThreadComment] = Field(max_length=20)
    agents: list[AgentBrief] = Field(max_length=100)


class ThreadAction(BaseModel):
    agent_no: int
    reply_to: int  # the agent_no of the comment replied to or liked
    liked: bool = False
    reply_text: str | None = Field(default=None, max_length=200)


class T20Output(BaseModel):
    actions: list[ThreadAction] = Field(default_factory=list)


class T21Input(BaseModel):
    """Explain the run: facts only (skip curve, rates, agents' reasons), with timestamps."""

    facts: list[str] = Field(min_length=1, max_length=40)
    duration_s: float | None = None


class TimedPoint(BaseModel):
    text: str = Field(max_length=220)
    at_s: float | None = None  # where in the video it happens


class T21Output(BaseModel):
    working: list[TimedPoint] = Field(max_length=3)
    holding: list[TimedPoint] = Field(max_length=3)
    edits: list[TimedPoint] = Field(max_length=3)


class AgentChatTurn(BaseModel):
    role: Literal["user", "agent"]
    content: str


class T22Input(BaseModel):
    """Talk to an agent: in character, about this video and its own reaction only."""

    persona: AgentBrief
    reaction: Reaction
    timeline: Timeline
    history: list[AgentChatTurn] = Field(default_factory=list)
    question: str = Field(min_length=1, max_length=500)


class T22Output(BaseModel):
    answer: str = Field(max_length=700)


# ------------------------------------------------------------------ T23 · write recap copy (v2.1)


class RecapSlideIn(BaseModel):
    slide_id: str
    facts: list[str] = Field(min_length=1, max_length=8)  # the numbers it may quote
    data: dict[str, Any] = Field(default_factory=dict)  # the same facts, structured


class T23Input(BaseModel):
    """The playful lines around a recap's facts. Numbers come only from ``facts``."""

    handle: str
    period: str
    comment_language: str | None = None  # e.g. "hinglish": Hinglish is fine then
    slides: list[RecapSlideIn] = Field(min_length=1, max_length=18)


class RecapLine(BaseModel):
    slide_id: str
    headline: str = Field(max_length=60)
    subline: str = Field(max_length=90)


class T23Output(BaseModel):
    slides: list[RecapLine]


# ------------------------------------------------------------------ T25–T29 · Follower Personas (v2.2)

Mood = Literal["neutral", "love", "like", "unsure", "skip", "thinking", "listening"]
PersonaReactionKind = Literal["watch_all", "watch", "scroll_past", "skip"]
SensitiveAttribute = Literal[
    "age",
    "gender",
    "religion",
    "caste",
    "ethnicity",
    "sexuality",
    "health",
    "income",
    "politics",
    "location",
]


class PersonaGroupIn(BaseModel):
    """One comment cluster's facts (code). Numbers may only come from ``facts``."""

    key: str  # "g1"…"g4", in share order
    facts: list[str] = Field(min_length=1, max_length=14)
    data: dict[str, Any] = Field(default_factory=dict)  # the same facts, structured
    # Comments near the group's middle, handles removed: material to paraphrase, never to copy.
    samples: list[str] = Field(default_factory=list, max_length=5)
    keep_name: str | None = None  # a persona matched to last month keeps its name
    keep_short_name: str | None = None


class T25Input(BaseModel):
    """Write the 4 Follower Personas from their groups' facts, in one call."""

    niche: str
    main_language: str | None = None  # e.g. "hinglish": Hinglish lines are fine then
    groups: list[PersonaGroupIn] = Field(min_length=4, max_length=4)


class WrittenPersona(BaseModel):
    key: str
    name: str = Field(min_length=3, max_length=40)  # 2–3 kind words, e.g. "The Festive Planner"
    short_name: str = Field(min_length=2, max_length=24)
    tagline: str = Field(max_length=90)
    comes_for: list[str] = Field(min_length=2, max_length=4)
    loves: list[str] = Field(min_length=2, max_length=4)  # loves[i] describes love fact i
    wants_more: list[str] = Field(min_length=1, max_length=3)
    turn_offs: list[str] = Field(min_length=1, max_length=3)  # turn_offs[i] ↔ turn-off fact i
    engagement_style: str = Field(max_length=160)
    voice: str = Field(max_length=140)
    typical_comment: str = Field(max_length=140)  # paraphrased, never a real comment


class T25Output(BaseModel):
    personas: list[WrittenPersona] = Field(min_length=4, max_length=4)


class ThoughtIn(BaseModel):
    key: str
    name: str
    voice: str
    language: str | None = None
    facts: list[str] = Field(min_length=1, max_length=14)
    mood_hint: Mood = "neutral"  # from code: sentiment and engagement lift
    loves: list[str] = Field(default_factory=list, max_length=4)
    wants_more: list[str] = Field(default_factory=list, max_length=3)
    top_reels: list[str] = Field(default_factory=list, max_length=4)  # titles


class T26Input(BaseModel):
    """What each persona thinks of the creator, in one call."""

    handle: str
    personas: list[ThoughtIn] = Field(min_length=1, max_length=4)


class PersonaThought(BaseModel):
    key: str
    thought: str = Field(min_length=3, max_length=140)  # first person, in the persona's voice
    mood: Mood
    loves: list[str] = Field(min_length=1, max_length=2)
    wants_more: list[str] = Field(default_factory=list, max_length=2)


class T26Output(BaseModel):
    thoughts: list[PersonaThought]


class EvidenceRef(BaseModel):
    id: str
    text: str


class PersonaBrief(BaseModel):
    """A persona as T27 and T28 read it."""

    key: str
    name: str
    voice: str = ""
    facts: list[str] = Field(default_factory=list, max_length=14)
    comes_for: list[str] = Field(default_factory=list)
    loves: list[str] = Field(default_factory=list)
    wants_more: list[str] = Field(default_factory=list)
    turn_offs: list[str] = Field(default_factory=list)
    typical_comment: str = ""
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=8)


class T27Input(BaseModel):
    """Each persona's own take on an idea or draft (or a Simulator result), in one call."""

    target_type: Literal["idea", "script", "storyboard", "caption", "simulation"]
    idea: str
    draft: str | None = None  # the current script, storyboard or caption, or the results
    format: str | None = None
    personas: list[PersonaBrief] = Field(min_length=1, max_length=4)


class Would(BaseModel):
    like: bool = False
    comment: bool = False
    share: bool = False
    save: bool = False  # always shown as "simulated"


class PersonaReaction(BaseModel):
    key: str
    reaction: PersonaReactionKind
    score: int = Field(ge=0, le=100)
    would: Would
    opinion: str = Field(min_length=3, max_length=280)  # first person, 1–3 sentences
    win_them_over: str = Field(max_length=120)
    evidence_ids: list[str] = Field(default_factory=list, max_length=4)


class T27Output(BaseModel):
    reactions: list[PersonaReaction]


class PersonaChatTurn(BaseModel):
    role: Literal["user", "persona"]
    content: str


class T28Input(BaseModel):
    """Talk to a persona: in character, honest about being a summary, no new numbers."""

    persona: PersonaBrief
    context: str | None = None  # the current draft or simulation, when there is one
    history: list[PersonaChatTurn] = Field(default_factory=list, max_length=20)
    question: str = Field(min_length=1, max_length=500)


class T28Output(BaseModel):
    answer: str = Field(min_length=1, max_length=600)


class T29Input(BaseModel):
    """The cheap classifier pass: does any text state or imply a sensitive attribute?"""

    texts: list[str] = Field(min_length=1, max_length=40)


class SensitiveFlag(BaseModel):
    index: int
    attribute: SensitiveAttribute


class T29Output(BaseModel):
    flags: list[SensitiveFlag] = Field(default_factory=list)


T1 = TaskSpec("T1", 1, "watch_video", "video", T1Input, T1Output)
T2 = TaskSpec("T2", 1, "extract_dna", "fast", T2Input, T2Output)
T3 = TaskSpec("T3", 1, "label_comments", "fast", T3Input, T3Output)
T4 = TaskSpec("T4", 1, "name_group", "fast", T4Input, T4Output)
T5 = TaskSpec("T5", 1, "name_opportunity", "main", T5Input, T5Output)
T6 = TaskSpec("T6", 1, "generate_ideas", "main", T6Input, T6Output)
T7 = TaskSpec("T7", 1, "write_script", "main", T7Input, T7Output)
T8 = TaskSpec("T8", 1, "tag_notes", "fast", T8Input, T8Output)
T10 = TaskSpec("T10", 1, "write_explanation", "main", T10Input, T10Output)
T11 = TaskSpec("T11", 1, "build_storyboard", "main", T11Input, T11Output)
T12 = TaskSpec("T12", 1, "write_captions", "main", T12Input, T12Output)
T13 = TaskSpec("T13", 1, "route_revision", "fast", T13Input, T13Output)
T14 = TaskSpec("T14", 1, "ask_curo", "main", T14Input, ChatChunk)
T15 = TaskSpec("T15", 1, "propose_edits", "main", T15Input, T15Output)
T16 = TaskSpec("T16", 1, "name_trend", "main", T16Input, T16Output)
T18 = TaskSpec("T18", 1, "write_personas", "fast", T18Input, T18Output)
T19 = TaskSpec("T19", 1, "agent_reactions", "agents", T19Input, T19Output)
T20 = TaskSpec("T20", 1, "thread_round", "agents", T20Input, T20Output)
T21 = TaskSpec("T21", 1, "explain_simulation", "main", T21Input, T21Output)
T22 = TaskSpec("T22", 1, "agent_chat", "main", T22Input, T22Output)
T23 = TaskSpec("T23", 1, "write_recap_copy", "main", T23Input, T23Output)
T25 = TaskSpec("T25", 1, "write_follower_personas", "main", T25Input, T25Output)
T26 = TaskSpec("T26", 1, "persona_thoughts", "main", T26Input, T26Output)
T27 = TaskSpec("T27", 1, "persona_reactions", "main", T27Input, T27Output)
T28 = TaskSpec("T28", 1, "persona_chat", "main", T28Input, T28Output)
T29 = TaskSpec("T29", 1, "check_sensitive", "fast", T29Input, T29Output)

TASKS: dict[str, TaskSpec] = {
    t.id: t
    for t in (
        T1,
        T2,
        T3,
        T4,
        T5,
        T6,
        T7,
        T8,
        T10,
        T11,
        T12,
        T13,
        T14,
        T15,
        T16,
        T18,
        T19,
        T20,
        T21,
        T22,
        T23,
        T25,
        T26,
        T27,
        T28,
        T29,
    )
}
