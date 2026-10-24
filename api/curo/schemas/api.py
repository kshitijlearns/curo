"""Request and response models for the HTTP API (the source of the OpenAPI file)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_USERNAME = re.compile(r"^[a-z0-9._]{1,30}$")

# --------------------------------------------------------------------------- auth


class OtpRequest(BaseModel):
    email: str


class OtpSent(BaseModel):
    sent: bool = True
    # Development only: the code, so the app can show it without an email service.
    dev_code: str | None = None


class OtpVerify(BaseModel):
    email: str
    code: str


class Session(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user_id: UUID
    email: str | None


# --------------------------------------------------------------------------- jobs


class JobOut(BaseModel):
    id: UUID
    type: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class Accepted(BaseModel):
    """202 response for slow work: follow the job (GET /v1/jobs/{id})."""

    job_id: UUID


# --------------------------------------------------------------------------- me & onboarding


class UsernameIn(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = v.strip().lstrip("@").lower()
        if v.startswith("https://") or "instagram.com" in v:
            v = v.rstrip("/").rsplit("/", 1)[-1]
        if not _USERNAME.match(v):
            raise ValueError(
                "Instagram usernames use letters, numbers, dots and underscores (max 30)"
            )
        return v


class OnboardingStarted(Accepted):
    username: str


class OnboardingStatus(BaseModel):
    status: Literal["not_started", "running", "ready", "failed"]
    username: str | None = None
    # v2.1 progress strip: profile → reels → comments → recap (then ready).
    step: str | None = None
    followers: int | None = None
    recap_id: UUID | None = None
    recap_status: Literal["building", "ready", "failed"] | None = None
    job: JobOut | None = None
    reels_found: int = 0
    comments_done: int = 0
    comments_total: int = 0
    # Reels whose video has been understood (DNA extracted); the newest 30 are processed.
    reels_processed: int = 0
    message: str | None = None
    error: str | None = None


class CreatorOut(BaseModel):
    id: UUID
    ig_username: str
    niche: str | None = None
    goal: str | None = None
    timezone: str


class AccountOut(BaseModel):
    username: str
    full_name: str | None = None
    followers: int | None = None
    following: int | None = None
    posts: int | None = None
    status: str
    last_collected_at: datetime | None = None


class DeletionStarted(BaseModel):
    status: Literal["deleting", "deleted"]
    job_id: UUID | None = None


class Me(BaseModel):
    user_id: UUID
    email: str | None
    # v2.1: a first-run session with no email yet ("Save your account" converts it).
    is_anonymous: bool = False
    # CURO's clock (honours FAKE_NOW / time travel): the app measures "updated X ago" against it.
    now: datetime
    creator: CreatorOut | None = None
    account: AccountOut | None = None
    reels: int = 0
    # True once Home can open: reels are in, or onboarding finished (an account may have none).
    onboarded: bool = False
    saved_opportunities: int = 0
    drafts: int = 0
    saved_count: int = 0


# --------------------------------------------------------------------------- reels


class PublicMetrics(BaseModel):
    """The four public metrics. None = not public (hidden likes, no share count,
    comments off) — shown as a dash, never as zero."""

    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None


class MetricChanges(BaseModel):
    """% change vs expected at this age (Phase 4); None = nothing to compare yet."""

    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None


class ReelCard(BaseModel):
    id: UUID
    shortcode: str
    permalink: str
    title: str
    posted_at: datetime
    duration_s: float | None = None
    tone: int = Field(ge=0, le=3, description="Placeholder thumbnail tone")
    metrics: PublicMetrics
    changes: MetricChanges = Field(default_factory=MetricChanges)
    compared_with: Literal["simulation", "usual"] | None = None
    last_snapshot_at: datetime | None = None
    snapshots: int = 0
    seen_late: bool = False
    likes_hidden: bool = False
    comments_disabled: bool = False
    is_paid_partnership: bool = False


class RefreshOut(BaseModel):
    status: Literal["queued", "fresh"]
    job_id: UUID | None = None
    last_snapshot_at: datetime | None = None


# --------------------------------------------------------------------------- insights

PhaseId = Literal["testing", "growing", "peak", "slowing", "longtail"]


class TimelinePoint(BaseModel):
    age_h: float
    velocity: float  # views per hour over the interval ending here
    phase: PhaseId | None


class PhaseOut(BaseModel):
    id: PhaseId
    label: str
    description: str
    usual_range: str | None = Field(None, description="How long this phase usually lasts for you")
    estimated: bool = Field(False, description="Estimated from age: the reel was first seen late")
    views_per_follower: float | None = None
    timeline: list[TimelinePoint] = Field(default_factory=list)


class AudienceCard(BaseModel):
    key: str
    icon: Literal["comments", "shares", "likes", "views"]
    title: str
    text: str
    facts: list[str]  # the evidence behind the sentence
    z: float | None = None


class TopCommentOut(BaseModel):
    text: str
    likes: int
    replies: int
    negative: bool


# --------------------------------------------------------------------------- opportunities

OppTag = Literal["Trend", "Audience", "Your content"]


class OpportunityCard(BaseModel):
    id: UUID
    name: str
    tag: OppTag
    score: float = Field(description="0–10, as computed")
    score_shown: int = Field(description="The whole number shown in the ring")
    card: str
    saved: bool
    topic_key: str


class OpportunityPart(BaseModel):
    key: Literal["F", "D", "T", "O"]
    name: str
    weight: float
    value: float
    share: float = Field(
        description="This part's share of the score formula (weight × value ÷ total)"
    )
    facts: list[str]


class TrendNote(BaseModel):
    name: str
    why_rising: str
    saturation: Literal["low", "medium", "high", "unknown"]


class OpportunityDetail(OpportunityCard):
    description: str
    signals: list[str]
    parts: list[OpportunityPart]
    trending: list[TrendNote] = Field(
        default_factory=list, description="What's trending in your niche (the shared feed)"
    )
    fit: list[dict[str, str]]
    window_ends_on: date | None = None
    saved_score: float | None = None


class SavedOpportunity(BaseModel):
    id: UUID
    name: str
    tag: OppTag
    score_today: float
    score_when_saved: float | None
    window_passed: bool
    saved_at: datetime | None = None


class SavedDraft(BaseModel):
    id: UUID
    title: str
    opportunity: str | None = Field(None, description="The opportunity it came from, if any")
    step: Literal["ideas", "idea", "script", "storyboard", "caption", "final"]
    saved_at: datetime | None = None
    icon_key: str = Field("closeup", description="The first storyboard frame's sketch")


class SavedOut(BaseModel):
    opportunities: list[SavedOpportunity]
    drafts: list[SavedDraft] = Field(default_factory=list)


# --------------------------------------------------------------------------- Studio

Step = Literal["ideas", "idea", "script", "storyboard", "caption", "final"]
Slot = Literal["proven", "adapted", "explore"]


class IdeaParts(BaseModel):
    H: float
    A: float
    T: float
    N: float


class IdeaShares(BaseModel):
    """Whole percents adding up to 100."""

    H: int
    A: int
    T: int
    N: int


class IdeaOut(BaseModel):
    id: UUID
    text: str
    description: str = ""
    why: str = Field("", description="One line: the strongest part's fact")
    slot: Slot | None = None
    score: float | None = None
    parts: IdeaParts | None = None
    shares: IdeaShares | None = Field(
        None, description="Each part's share of the score in whole percents (w·s ÷ Σ w·s)"
    )
    evidence: list[str] = Field(default_factory=list)
    format: str | None = None
    target_behaviour: str | None = None
    source: Literal["generated", "creator"] = "generated"
    selected: bool = False


class IdeaRound(BaseModel):
    round: int
    prompt: str | None = None
    ideas: list[IdeaOut]


class NoteOut(BaseModel):
    type: Literal["hook", "comments", "likes", "shares"]
    title: str
    desc: str
    evidence: str


class BeatOut(BaseModel):
    id: str
    role: str
    text: str
    start_s: float
    end_s: float
    t: str = Field(description="0:00 – 0:04")
    note: NoteOut | None = None


class ScriptOut(BaseModel):
    version: int
    beats: list[BeatOut]
    seconds: float
    words: int
    band: str | None = Field(None, description="e.g. 25–35 seconds, and what it rests on")
    instruction: str | None = None
    reply: str | None = None
    changed_beat_ids: list[str] = Field(default_factory=list)
    source: str


class FrameOutApi(BaseModel):
    id: str
    beat_id: str
    line: str
    t: str
    shot_type: str
    instruction: str
    onscreen_text: str
    transition: str
    icon_key: str
    stale: bool = False


class Feasibility(BaseModel):
    label: Literal["Easy", "Moderate", "Hard"]
    score: int
    detail: str


class StoryboardOut(BaseModel):
    version: int
    script_version: int | None
    frames: list[FrameOutApi]
    feasibility: Feasibility
    instruction: str | None = None
    reply: str | None = None
    up_to_date: bool = Field(True, description="False when script lines changed since")


class CaptionOption(BaseModel):
    text: str
    job: Literal["comments", "likes", "shares"]
    why: str


class HashtagOption(BaseModel):
    tag: str
    kind: Literal["broad", "niche", "local", "series"]
    score: float


class CaptionsOut(BaseModel):
    version: int
    options: list[CaptionOption]
    chosen: int | None
    hashtags: list[str] = Field(max_length=5)
    candidates: list[HashtagOption]
    instruction: str | None = None
    reply: str | None = None


class ProjectOpportunity(BaseModel):
    id: UUID
    name: str
    tag: OppTag


class Project(BaseModel):
    id: UUID
    title: str | None
    step: Step
    status: Literal["active", "saved", "posted", "discarded"]
    saved_at: datetime | None = None
    opportunity: ProjectOpportunity | None = None
    rounds: list[IdeaRound] = Field(default_factory=list)
    idea: IdeaOut | None = Field(None, description="The chosen idea")
    script: ScriptOut | None = None
    storyboard: StoryboardOut | None = None
    captions: CaptionsOut | None = None


class ProjectIn(BaseModel):
    opportunity_id: UUID | None = None
    idea_text: str | None = Field(None, max_length=300, description="An idea the creator validated")


class ProjectStarted(BaseModel):
    project_id: UUID
    job_id: UUID | None = Field(
        None, description="The first round of ideas, when from an opportunity"
    )


class StudioJob(BaseModel):
    project_id: UUID
    job_id: UUID


class IdeasIn(BaseModel):
    prompt: str | None = Field(None, max_length=600, description="The creator's own note")


class ScriptIn(BaseModel):
    direction: str | None = Field(None, max_length=600)
    regenerate: bool = False


class InstructionIn(BaseModel):
    instruction: str = Field(min_length=1, max_length=1000)
    frame_id: str | None = Field(None, description="The storyboard frame on screen")


class OwnScriptIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class CaptionsReviseIn(BaseModel):
    instruction: str | None = Field(None, max_length=1000)
    own_caption: str | None = Field(None, max_length=2200)


class HashtagsIn(BaseModel):
    hashtags: list[str]


class ChosenCaptionIn(BaseModel):
    chosen: int = Field(ge=0)


class SaveIn(BaseModel):
    step: Step | None = None


class ValidateIn(BaseModel):
    text: str = Field(min_length=3, max_length=300)


class Reason(BaseModel):
    text: str
    evidence: str


class TweakOut(BaseModel):
    text: str
    gain: float


class Validation(BaseModel):
    text: str
    score: float
    verdict: Literal["Strong", "Worth trying", "Risky"]
    parts: IdeaParts
    shares: IdeaShares
    reasons: list[Reason]
    tweaks: list[TweakOut]


class ReelInsights(BaseModel):
    reel: ReelCard
    phase: PhaseOut | None = None
    audience: list[AudienceCard] = Field(default_factory=list)
    top_comment: TopCommentOut | None = None
    notes: list[str] = Field(
        default_factory=list, description="Where the data is thin, said plainly"
    )
    processed: bool = Field(False, description="The reel's video has been understood (DNA exists)")


# --------------------------------------------------------------------------- uploads

UploadType = Literal["video/mp4", "video/quicktime"]
SimAudienceId = Literal["followers", "new", "both"]


class UploadSignIn(BaseModel):
    content_type: UploadType = "video/mp4"


class UploadSigned(BaseModel):
    """Send the file with ``method`` to ``url`` (a URL starting with "/" is on this API) and
    ``headers``; then start a simulation with ``path``."""

    path: str
    url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime


class SampleVideo(BaseModel):
    name: str
    title: str
    description: str
    caption: str
    duration_s: float
    width: int
    height: int


class SampleIn(BaseModel):
    name: str


class Uploaded(BaseModel):
    path: str
    duration_s: float
    width: int | None = None
    height: int | None = None
    caption: str | None = Field(None, description="A sample recording's caption")


# --------------------------------------------------------------------------- the Simulator


class SimulationIn(BaseModel):
    upload_path: str
    project_id: UUID | None = Field(None, description="The Studio draft to compare with")
    audience: SimAudienceId = "both"
    caption: str | None = Field(
        None,
        max_length=2200,
        description="The caption it will be posted with; else the linked draft's chosen caption",
    )


class RerunIn(BaseModel):
    upload_path: str
    caption: str | None = Field(None, max_length=2200)


class SimulationStarted(BaseModel):
    simulation_id: UUID
    job_id: UUID


class SimEvidence(BaseModel):
    who: str
    title: str
    stat: str
    tone: int


class SimItem(BaseModel):
    """One thing working or holding the recording back, with the reels behind it."""

    key: str
    feature: str
    value: str
    better: str | None = None
    metric: str
    text: str
    short: str | None = Field(None, description="A short name for it (the chat hint uses it)")
    evidence: list[SimEvidence]
    frame: int | None = Field(None, description="The linked storyboard's frame index")
    frame_label: str | None = None


class SimAudience(BaseModel):
    score: int
    label: str
    summary: str
    working: list[SimItem]
    holding: list[SimItem]
    edit_ids: list[UUID] = Field(description="The best three edits for this audience, in order")


class SimReportRow(BaseModel):
    metric: Literal["views", "like_rate", "comment_rate", "share_rate"]
    label: str
    known: bool
    baseline: float | None = Field(None, description="The creator's 7-day usual (count or rate)")
    low: float | None = None
    mid: float | None = None
    high: float | None = None
    change_pct: int | None = None


class BestTime(BaseModel):
    label: str
    fact: str
    at: datetime


class SimDna(BaseModel):
    content: list[list[str]]
    production: list[list[str]]
    trend: list[list[str]]


class CompareItem(BaseModel):
    kind: str
    text: str


class SimBasis(BaseModel):
    neighbours: int
    own_neighbours: int
    own_reels: int
    history: int


class SimPrevious(BaseModel):
    simulation_id: UUID
    scores: dict[str, int]


class SimVideo(BaseModel):
    duration_s: float
    width: int | None = None
    height: int | None = None


class SkipPoint(BaseModel):
    t: int
    watching: float  # share of agents still watching at this second


class AudiencePrediction(BaseModel):
    metric: Literal["views", "likes", "comments", "shares", "saves"]
    rate: float | None = None
    low: float | None = None
    high: float | None = None
    count: int | None = None
    count_low: int | None = None
    count_high: int | None = None
    simulated: bool = Field(
        False, description="Saves: no public count to calibrate on, always shown as simulated"
    )


class TimedText(BaseModel):
    text: str
    at_s: float | None = None


class AudienceExplain(BaseModel):
    working: list[TimedText] = Field(default_factory=list)
    holding: list[TimedText] = Field(default_factory=list)
    edits: list[TimedText] = Field(default_factory=list)


class AgentReply(BaseModel):
    agent_no: int
    segment: str
    text: str


class AgentComment(BaseModel):
    agent_no: int
    segment: str  # shown as "Agent 12 · Festive planner"; never a handle or an avatar
    text: str
    likes: int = 0
    replies: list[AgentReply] = Field(default_factory=list)


class AudienceSegmentOut(BaseModel):
    key: str
    label: str
    share: float
    description: str


class SimAudienceResult(BaseModel):
    """v2: the AI audience's run (PLAN_V2 §4.5)."""

    persona_version: str
    agents: int
    watched: int
    counts: dict[str, int]
    segments: list[AudienceSegmentOut]
    predictions: list[AudiencePrediction]
    calibration: dict[str, dict[str, Any]]
    engagement: float | None = None
    engagement_score: int | None = Field(
        None, description="0–100: the share of the creator's past reels it beats; null if < 5"
    )
    previous_engagement_score: int | None = None
    past_reels_scored: int
    skip_curve: list[SkipPoint]
    explain: AudienceExplain
    comments: list[AgentComment]
    label: str


class AgentOut(BaseModel):
    agent_no: int
    segment: str
    segment_label: str
    persona_text: str
    reaction: dict[str, Any]
    chat: list[dict[str, str]] = Field(default_factory=list)
    messages_left: int


class AgentChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class AgentChatOut(BaseModel):
    answer: str
    messages_left: int


class SimResult(BaseModel):
    method: str
    video: SimVideo
    caption: str
    linked: bool
    audiences: dict[SimAudienceId, SimAudience]
    report: list[SimReportRow]
    best_time: BestTime | None = None
    accuracy: str
    dna: SimDna
    compare: list[CompareItem]
    notes: list[str]
    basis: SimBasis
    previous: SimPrevious | None = None
    audience: SimAudienceResult | None = None


class SimEdit(BaseModel):
    id: UUID
    title: str
    description: str
    feature_change: dict[str, str]
    effort: Literal["edit_only", "reshoot"]
    gains: dict[SimAudienceId, int]
    frame_index: int | None = None
    frame_label: str | None = None
    applied: bool
    applied_at: datetime | None = None
    applied_job_id: UUID | None = None


class Simulation(BaseModel):
    id: UUID
    status: Literal["queued", "running", "done", "failed"]
    error: str | None = None
    audience: SimAudienceId
    project_id: UUID | None = None
    project_title: str | None = None
    parent_simulation_id: UUID | None = None
    video: SimVideo | None = None
    score: int | None = None
    scores: dict[SimAudienceId, int] | None = None
    engagement_score: int | None = None
    result: SimResult | None = None
    edits: list[SimEdit] = Field(default_factory=list)
    job_id: UUID | None = None
    created_at: datetime
    finished_at: datetime | None = None


class EditApplied(BaseModel):
    edit: SimEdit
    job_id: UUID | None = Field(
        None, description="The Studio write-back, when the simulation is linked to a draft"
    )


# --------------------------------------------------------------------------- Ask Curo

ChatScreen = Literal[
    "studio:validate",
    "studio:ideas",
    "studio:idea",
    "studio:script",
    "studio:storyboard",
    "studio:caption",
    "sim:result",
]


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    screen: ChatScreen
    project_id: UUID | None = None
    simulation_id: UUID | None = None
    frame_id: str | None = Field(None, description="The storyboard frame on screen")


class ChatSource(BaseModel):
    kind: Literal["reel", "pattern", "opportunity", "idea", "project", "simulation", "memory"]
    id: str | None = None
    title: str


class ChatMessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    sources: list[ChatSource] = Field(default_factory=list)
    intent: str | None = None
    created_at: datetime


class MemoryOut(BaseModel):
    id: UUID
    key: str
    value: str
    source: Literal["stated", "learned"]


# --------------------------------------------------------------------------- the learning loop


class ReelMatch(BaseModel):
    """A posted reel that looks like one the creator simulated or drafted."""

    id: UUID
    reel_id: UUID
    reel_title: str
    posted_at: datetime | None = None
    simulation_id: UUID | None = None
    simulation_score: int | None = None
    project_id: UUID | None = None
    project_title: str | None = None
    reasons: list[str] = Field(default_factory=list)
    status: Literal["pending", "confirmed", "rejected"]


# --------------------------------------------------------------------------- Trending for you


class TrendCard(BaseModel):
    """A card from the shared trend feed, ranked for this creator (PLAN_V2 §4.4)."""

    id: UUID
    name: str
    summary: str
    why_rising: str
    why_it_fits: str
    example_angles: list[str]
    window_start: date | None = None
    window_end: date | None = None
    momentum: float | None = None
    saturation: Literal["low", "medium", "high", "unknown"]
    hashtags: list[str] = Field(default_factory=list)
    fit: float = Field(description="0–1: how close it sits to the creator's own content")


# --------------------------------------------------------------------------- v2.1 Creator Recap


class RecapCopy(BaseModel):
    headline: str
    subline: str
    source: str = "template"


class RecapVisual(BaseModel):
    bg: str
    fg: str
    accent: str = "blue"
    milestone: bool = False
    seconds: int = 6


class RecapSlide(BaseModel):
    slide_id: str
    facts: dict[str, Any]
    copy_: RecapCopy = Field(alias="copy")
    visual: RecapVisual

    model_config = {"populate_by_name": True}


class RecapStat(BaseModel):
    slide: str
    label: str
    value: str


class RecapSummary(BaseModel):
    id: UUID
    kind: Literal["first", "monthly"]
    period_start: date
    period_end: date
    period_label: str
    status: Literal["building", "ready", "failed"]
    creator_level: str | None = None
    level_modifier: str | None = None
    archetype: str | None = None
    archetype_runner_up: str | None = None
    stats: list[RecapStat] = Field(default_factory=list)
    viewed_at: datetime | None = None
    is_new: bool = False
    created_at: datetime


class Recap(RecapSummary):
    handle: str | None = None
    slides: list[RecapSlide] = Field(default_factory=list)
    archetype_evidence: dict[str, Any] = Field(default_factory=dict)


class FollowerIdeaOut(BaseModel):
    id: UUID
    title: str
    why: str
    segment: str | None = None
    score: float
    parts: dict[str, float] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
