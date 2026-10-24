# CURO v2 — plan: a web app on Vercel

Source: `CURO_WebApp_ClaudeCode_Prompt.md`. Built on v1 (README, PLAN.md, DECISIONS D1–D105,
INTEGRATION.md). Everything that still applies is reused: the logic services, provider
interfaces and mocks, `MOCK_MODE`, prompts, the honesty rules and the no-new-numbers
validator. Deviations go to `docs/DECISIONS.md` (v2 entries start at D200).

**Status of v1 when v2 starts.** v1 phases 0–8 are done. v1 phase 9 (hardening) was mid-way:
account deletion (`DELETE /v1/me`), the daily `cleanup` job, `match_posted_reel` with
confirmation, the weekly `accuracy_report` with automatic range widening, a Monitoring
provider (Sentry/PostHog stub) and their tests are built and passing. They carry into v2.
v1's peer-dependent parts change as described in section 4.

---

## 1. What Vercel allows (checked 2026-10-21; details go in docs/DEPLOY_VERCEL.md)

| Limit | Hobby | Pro |
|---|---|---|
| Function max duration (Fluid compute, Python included) | 300 s | 800 s (1,800 s beta) |
| Request / response body | 4.5 MB | 4.5 MB |
| Python bundle size | 500 MB | 500 MB |
| Memory | 2 GB / 1 vCPU | up to 4 GB / 2 vCPU |
| Cron jobs | 100 per project, **once per day at most**, ±59 min | 100, every minute, on the minute |

What follows from this:
- **Uploads never pass through a function.** The browser PUTs straight to Supabase Storage
  through a signed URL (4.5 MB body limit).
- **No step runs longer than about 4 minutes.** Every long job is a chain of resumable steps
  (section 3).
- **On Hobby, a per-minute cron is impossible.** The design does not need one:
  1. **Pumping on poll.** `GET /api/v1/jobs/{id}`, while the job is still queued, runs one
     step of it inline (bounded to 45 s). The app polls while the creator waits, so their
     job moves.
  2. **A kick on enqueue.** The API answers 202 and asks the worker endpoint to start. On
     Pro, the per-minute cron also does this.
  3. **A daily cron** runs the worker for its full 300 s for background work: nightly
     learning, trend feed, cleanup.
  4. **On Hobby, background work only gets the daily run.** Snapshots every 6 h need either
     the Pro plan or the fallback, `worker/standalone.py`: the same job loop as a
     long-lived process on any small host. Both options are documented.
- **Python on Vercel:** FastAPI is detected through `tool.vercel.entrypoint`. Next.js and
  FastAPI deploy as two **services** of one project (`vercel.json` `services`). `/api/*` is
  routed to the backend service, and everything else to Next.js.

**Models (to confirm on the providers' pages when keys arrive):**
- `CLAUDE_MODEL_MAIN=claude-sonnet-5-5`
- `CLAUDE_MODEL_FAST=claude-haiku-5-5`
- `CLAUDE_MODEL_AGENTS=claude-haiku-5-5` (Haiku 5.5 exists, so it's used rather than Haiku 4.5)
- `GEMINI_VIDEO_MODEL=gemini-3.6-flash`; `gemini-3.5-flash-lite` is the cheaper option.
- `GEMINI_EMBEDDING_MODEL=gemini-embedding-2` at 768 dimensions.

---

## 2. Architecture

```
Browser (Chrome) ── Next.js /web (App Router, TS) ── supabase-js (auth, Realtime on jobs)
        │  same origin
        ▼  /api/v1/*                       /api/internal/run-jobs  (CRON_SECRET)
   FastAPI `curo` (Vercel Python service) ─────── job loop (claims jobs, runs steps)
        │                                              ▲ Vercel Cron (daily; every minute on Pro)
        ▼                                              │ worker/standalone.py (fallback, local dev)
   Supabase: Postgres + pgvector + RLS · Auth · Storage (videos) · Realtime (jobs)
```

```
/web        Next.js app (replaces Expo)            /api   FastAPI package `curo`
/legacy/app the Expo app, moved untouched          /db    migrations (+ db/local shim)
/worker     standalone.py (job loop)               /tools dev runner, reembed.py, generators
vercel.json services, routes, crons, functions     /docs  DECISIONS, INTEGRATION, DEPLOY_VERCEL
```

**Frontend (`/web`).**
- Next.js App Router, TypeScript and React Query, with plain CSS modules; one `theme.css`
  holds the six colours and Figtree 300/400/600.
- Ported from the Expo screens: the lavender "Curo" header with the Saved button, the white
  rounded sheet scrolling under it, the raised-circle springy nav (CSS transitions with
  spring-like cubic-bezier curves), the Composer with voice, Sketch (SVG) and the score ring.
- Mobile-first. From 481 px up, the app sits in a 480 px column on `#E4E4EC`. Checked at
  375 px and 1440 px.
- **Voice:** `webkitSpeechRecognition` (en-IN / hi-IN); the mic is hidden where it isn't
  available.
- **API:** a typed client (`openapi-typescript` + `openapi-fetch`) generated into
  `web/src/api/schema.d.ts`, calling only `/api/v1/*`.
- **Job progress:** a `JobWatcher` subscribes with Supabase Realtime to the job's row and
  falls back to polling (polling also pumps the job, as in section 1).
- **Auth:** an `AuthClient` with two implementations.
  - `supabase` (supabase-js email OTP): when `NEXT_PUBLIC_SUPABASE_URL` is set.
  - `local`: v1's dev OTP stub, which issues the same Supabase-format JWTs. This machine has
    no Docker, so no local Supabase.

  The API verifies both kinds of token the same way.

**Backend.**
- FastAPI is served under `/api` (`/api/v1/*`, `/api/internal/*`); routes and schemas stay,
  and removed features' routes go.
- **Redis and RQ go.** The queue is the `jobs` table (section 3).
- **SSE chat:** Ask Curo keeps streaming. Python functions can stream responses; the reply
  ends well under the duration limit.

**Local dev.** `make dev` / `./dev.ps1 dev`:
- Postgres + pgvector: Docker, or embedded pgserver with `./dev.ps1 local`, the no-Docker
  path on this machine.
- the FastAPI app (uvicorn, with `/api` as the prefix)
- `worker/standalone.py`
- `next dev` on :3000, which proxies `/api` to :8000

`MOCK_MODE=true` stays the default.

---

## 3. The Postgres job queue and resumable steps

**`jobs` table additions (migration 0014):**
- `run_after timestamptz` (backoff and scheduling)
- `locked_until timestamptz` and `locked_by text` (the lease)
- `max_attempts int default 3`
- `state jsonb default '{}'` (a step's saved progress)
- `step int default 0`
- `priority smallint` (interactive work first)
- index on `(status, priority, run_after)`

**Claim:**
```sql
update jobs set status='running', locked_until=now()+interval '5 min', locked_by=$worker,
       attempts=attempts+1
 where id = (select id from jobs
              where status='queued' and run_after<=now()
                 or status='running' and locked_until<now()        -- an expired lease
              order by priority, created_at
              for update skip locked limit 1)
returning *;
```

**Handlers.**
- They stay plain functions. A long one returns `Continue(state)`: the row goes back to
  `queued` with its state saved, `step+1` and `attempts` reset. So no step outlives the
  function, and a crash resumes from the last saved step.
- On an error: `run_after = now() + 30 s × 2^attempts`, then `failed` after `max_attempts`.
- `JobFailed` fails at once with the creator-facing reason.
- Idempotency keys stay as they are.

**Steps per long job:**

| Job | Steps |
|---|---|
| `onboard_public` | profile → reel metadata (50) → comments in batches of 5 reels → queue understanding |
| `process_reel` | download+store → T1 timeline → T2 DNA → embed |
| `run_simulation` (v2) | validate → watch (timeline) → ensure personas → agents 100 per step ×10 → thread round → calibrate+predict → explain |
| `build_personas` | segment commenters → generate 1,000 personas in steps of 200 → calibration on past reels |
| `trend_feed` | per niche: hashtag pages → T-trend cards |

**Worker endpoint:** `POST /api/internal/run-jobs` with header
`Authorization: Bearer $CRON_SECRET`. It loops claim → run until about 60 s before its
`maxDuration` (300 s Hobby, 800 s Pro), then returns counts. The scheduler tick (enqueuing
snapshots and nightly work) runs at the start of each invocation.

**`vercel.json` crons:**
- `/api/internal/run-jobs` every minute (Pro), or once daily (Hobby)
- `/api/internal/daily` 02:00 IST: nightly learning, trends, cleanup
- `/api/internal/weekly` Monday: accuracy report, persona refresh check

---

## 4. Product changes

### 4.1 Peer tracking removed
- **Gone:** `routes/peers.py`, `jobs/peers.py`, `services/peers.py`, the onboarding peer
  step, the peer settings, peer collection and snapshots, and peer video analysis.
- **Migration 0015:** drop `peers` and its policies; drop `curo.visible_account_ids()` and
  `curo.suggested_account_ids()`. `accounts_read` becomes "own account only".
- **Opportunity score:** `10 × (0.35 F + 0.25 D + 0.25 T + 0.15 O)`.
  - The "Competitor" source and the P part go.
  - The detail page's "What your competitors are doing" becomes **"What's trending in your
    niche"**, from the trend feed.
- **Idea score:** `0.40 H + 0.30 A + 0.20 T + 0.10 N`. The Adapted slot adapts a trending
  angle (a trend card's example angle) instead of a peer outlier.
- **Hashtags:** candidates come from the creator's own past tags, the trend feed's tags and
  AI suggestions. Score = 0.5 relevance + 0.3 results + 0.2 specificity, where "results" is
  now the creator's own lift with the tag, else the trend feed's momentum. This replaces
  peer results.
- **Simulator neighbours:** the creator's own reels only; v2's Simulator replaces T9, but
  T9 stays for the "what if" tool.
- **Cold start (< 5 reels):** cross-creator priors, `pattern_cards` with `account_id` null,
  built from all CURO creators' own reels and labelled "based on creators like you".

**Worked examples (hand-checked; recorded as D2xx with tests):**

*Ganpati dress ideas, the v1 parts without P.* F 0.66, D 0.80, T 1.00, O 0.55:

| Part | Calculation | Value |
|---|---|---|
| F | 0.35 × 0.66 | 0.2310 |
| D | 0.25 × 0.80 | 0.2000 |
| T | 0.25 × 1.00 | 0.2500 |
| O | 0.15 × 0.55 | 0.0825 |
| Total | 0.7635 × 10 | **7.6 / 10** (shown as 8) |

The shares are F 30%, D 26%, T 33%, O 11%, which add up to 100.

*An idea.* H 0.80, A 0.70, T 0.90, N 0.50:

| Part | Calculation | Value |
|---|---|---|
| H | 0.40 × 0.80 | 0.320 |
| A | 0.30 × 0.70 | 0.210 |
| T | 0.20 × 0.90 | 0.180 |
| N | 0.10 × 0.50 | 0.050 |
| Total | | **0.760** |

The shares are 42 / 28 / 24 / 6. A second idea with H 0.40, A 0.90, T 0.50, N 0.90 scores
0.16 + 0.27 + 0.10 + 0.09 = **0.620**.

### 4.2 Insights page and Home carousel removed
The screen and `GET /v1/reels/{id}/insights` go, and the carousel endpoint `GET /v1/reels`
leaves the app's API. The data stays: reels, snapshots, comments, baselines and pattern cards.

### 4.3 Collection: own profile only, with cost controls

| Setting | v2 |
|---|---|
| Onboarding | profile + 50 reels' metadata; analyse the newest 30; comments on the newest 30, up to `COMMENT_LIMIT=100` |
| Comment re-reads | only newer than the newest stored, at about 24 h and 7 days after posting (two reads per reel, at most) |
| Discovery | every 12 h: profile + latest 3 reels |
| Snapshots | every 6 h until 48 h, daily to day 7, weekly to day 30, then stop |
| Inactive | no app open for `INACTIVE_PAUSE_DAYS=14`: collection and processing pause; the next login queues one catch-up run |

**Snapshot count**, to the 6 h / 1 d / 7 d / 30 d marks:
- 6 h steps to 48 h: 8 snapshots.
- Daily on days 3 to 7: 5.
- Weekly at days 14, 21 and 28 (the 30-day mark is read off them): 3.
- The total is **16**; the prompt's "about 15" allows this. The exact list will be written
  into `schedule.py`'s test.

`creators.last_seen_at` is set on every authenticated request (once an hour at most).
Every vendor call writes to `usage_ledger` (Apify results and estimated USD).

### 4.4 Trending for you
- **Tables:**
  - `niches` (key, label, hashtags[]), seeded with about 10 niches: fashion styling,
    beauty, food, fitness, travel, creator tips, comedy, education, lifestyle, finance.
  - `trend_cards` (id, niche, name, summary, why_rising, example_angles jsonb, window_start,
    window_end, momentum, saturation, evidence jsonb, created_at).
  - `hashtag_pages` is reused as the cache.
- **Daily `trend_feed` job, per niche:**
  - About 5 hashtag pages of about 30 reels: posting momentum from v1's daily counts, and
    saturation as reels in the last 7 days.
  - Plus festivals from the calendar.
  - A new task, **T16 (Sonnet, name trend cards)**, writes 3–6 cards from those facts, and
    the no-new-numbers check applies.
- **Personalising:** cards are ranked by the cosine between the card's text embedding and
  the creator's sub-cluster centroids (fit), times momentum. The top 4 show under
  "Trending for you", each with a "why it fits you" line. The trend feed is fetched once
  per niche, never per creator.
- Opportunities' T part and the Adapted idea slot read the same cards.

### 4.5 Simulator v2: AI followers
**Tasks (each with a schema, prompt and mock):**

| Task | Model | Does |
|---|---|---|
| T1 (kept) | Gemini Flash | the second-by-second timeline, hook and payoff times. Stored on `simulations.timeline` |
| T17 segment audience | Haiku | comment themes + language + tone → 4–8 segments with share and description; never handles |
| T18 write personas | Haiku | segment → N persona texts (interests, what they watch for, how they react); 1,000 in total |
| T19 agent reactions | `CLAUDE_MODEL_AGENTS` | batch of agents + the timeline (cached) in a short feed → `{watch_until_s, skipped, liked, commented, comment_text, shared, saved, reason}` each |
| T20 thread round | `CLAUDE_MODEL_AGENTS` | the engaged agents + top comments → replies and comment likes |
| T21 explain | Sonnet | facts → 3 working / 3 holding / 3 edits with timestamps (validated) |
| T22 agent chat | Sonnet | persona + its reaction + timeline + question → answer in character |

**Mocks.** Deterministic. Each agent's reaction comes from a seeded RNG keyed on
(simulation, agent number), shaped by its segment's interests, the timeline's hook and
payoff times and the presence of a call to action. So a better take (payoff at 1 s, a send
prompt) gets more watching and sharing, and the demo's take1 → take2 shows a score change.

**Calibration (per persona version).**
- Run 200 agents on 5 of the creator's past reels (their stored T1 timelines).
- For each public metric m, the factor is `k_m = exp(mean(ln(real_rate_r / agent_rate_r)))`,
  with a spread s_m from the p10/p90 of those ratios.
- Stored in `persona_calibrations`.

**Predict.**
- Agent rates: likes, comments, shares and saves each as a share of the agents that
  watched; views = agents not skipped.
- `pred_rate_m = agent_rate_m × k_m`, with the range × s_m.
- Counts = the creator's 7-day usual views × rate.
- **Saves:** there's no real calibration, so the like factor is used, and they're labelled
  **"simulated"** everywhere (D2xx: the prompt now asks for saves; v1 never showed them).
- **Skip curve:** the share of agents still watching at each second.
- **Engagement score (0–100):** the percentile of
  `E = like_rate + 3·comment_rate + 4·share_rate` (calibrated) among the creator's past
  reels' real E. Saves are left out because they can't be compared.

*Worked example.* 1,000 agents; 620 not skipped; 240 likes, 22 comments, 30 shares among
them. Calibration k: likes 0.18, comments 0.12, shares 0.20.

| Count | Agent rate | Calibrated rate |
|---|---|---|
| Likes | 240 / 620 = 0.387 | × 0.18 = 0.0697 |
| Comments | 22 / 620 = 0.0355 | × 0.12 = 0.00426 |
| Shares | 30 / 620 = 0.0484 | × 0.20 = 0.00968 |

E = 0.0697 + 0.0128 + 0.0387 = **0.1212**. Against past reels' E values, it beats 34 of 50
reels, so the score is **68**.

**The rest of the Simulator:**
- **Accuracy:** v1's record and `match_posted_reel` stay (likes, comments, shares; never
  saves).
- **Explain:** working, holding and edits each carry a timestamp. The facts come from the
  skip curve (for example "38% of agents stopped watching before 0:04") and the agents'
  reasons.
- **UI:**
  - the score ring, predicted ranges, the skip curve (SVG) and best time to post (kept)
  - the explanations
  - a simulated comment feed in CURO's style, with "Agent 12 · Festive planner", no
    avatars, and the permanent label "Simulated by CURO's AI audience. Not real comments."
  - tap an agent to chat with it (10 messages per simulation)
  - a re-run shows the new score next to the previous one
- **Kept and dropped:** v1's T15 edits and edit write-back to the Studio are replaced by
  T21's edits, which can still be sent to the Studio as a script revision. The audience
  toggle and T9 percentile go; T9 stays for Ask Curo's "what if".

### 4.6 Plans, credits, usage, payments

**Tables:**
- `plans`: free 2 projects and 2 simulations a month, chat 10; pro $30, 10 and 10, chat 100.
- `subscriptions`: creator, plan, status, period start and end.
- `credit_ledger`, append-only: kind = grant | spend | topup | refund, resource =
  project | simulation | chat, amount, reason, ref_id, created_at. The balance = grants and
  top-ups minus spends, with this period's grants expiring at period end and top-ups never
  expiring.
- `usage_ledger`: creator, provider, model, task, tokens in and out, Apify results,
  cost_usd, ref_id.

**Rules:**
- **Spend points:** creating a project (1 project credit), starting a simulation (1), and
  each Ask Curo message.
- **Revisions:** up to 10 per project; the 11th answers "this project has used its 10
  revisions".
- **Agent chat:** up to 10 messages per simulation, counted on the simulation.
- **Out of credits:** `402` with `{code: "out_of_credits", resource, plan}`, and the web
  shows an upgrade screen.

**Payments and costs:**
- **`PaymentProvider`:** `create_checkout(plan|topup)`, `handle_webhook`, `cancel`.
  - The mock grants Pro or a top-up at once, through `/api/v1/billing/checkout`.
  - The Razorpay stub raises `NotImplementedError` with a TODO.
- **`/admin/costs`:** for creators with `is_admin`, set by email in `ADMIN_EMAILS`. Totals
  per creator and per feature this month, and creators over `COST_ALERT_USD` are flagged.

### 4.7 Ask Curo
Kept in Studio and the Simulator.
- **Tools gone:** `search_reels` stays (own reels); `get_reel`'s insight cards go;
  `run_simulation` and `get_simulation` are re-pointed to v2 results; there are no peer tools.
- **Limits:** messages count against 100 (Pro) or 10 (Free) a month, and a 403-style "out of
  credits" reply is streamed.

---

## 5. Migrations (new)
- **0014_job_queue:** the `jobs` columns above, plus `creators.last_seen_at` and
  `creators.paused_at`.
- **0015_drop_peers:** drop the peers table and policies; rewrite `accounts_read` and the
  visibility helpers.
- **0016_trends:** `niches` and `trend_cards`, both readable by authenticated users.
- **0017_simulator_v2:**
  - `audience_segments` (creator_id, version, key, label, share, description)
  - `audience_personas` (creator_id, agent_no, segment, persona_text, version)
  - `persona_calibrations`
  - `simulation_agents` (simulation_id, agent_no, reaction jsonb, thread jsonb)
  - `agent_chats` (simulation_id, agent_no, role, content)
  - `simulations.timeline`
- **0018_billing:** `plans`, `subscriptions`, `credit_ledger`, `usage_ledger`,
  `creators.is_admin`; RLS so a creator reads only their own rows.

---

## 6. Phases (stop and report after each)
0. This plan.
1. Web shell: `/web` with theme, header, sheet, nav and composer; auth (local OTP; supabase-js
   when configured); the Expo app moves to `/legacy/app`.
2. Backend on the Vercel shape: `/api` prefix, the Postgres queue, the worker endpoint,
   resumable steps, `vercel.json`, `worker/standalone.py`; Redis and RQ removed.
3. Removals and collection changes (4.1–4.3).
4. Home: Opportunities + Trending for you (4.4).
5. Studio on web.
6. Simulator v2 (4.5).
7. Plans, credits, usage and costs (4.6, 4.7).
8. Hardening: error and empty states, accessibility, Lighthouse, INTEGRATION and
   DEPLOY_VERCEL.
9. Publish to GitHub (branch `web-v2`, PR into `kshitijlearns/curo`).

## 7. Open question
- **Which Vercel plan will you deploy on?** The design works on both (section 1). On Hobby,
  6-hourly snapshots and 12-hourly discovery only run with the standalone worker on a small
  host; without it, they fall back to the daily cron.

---

# v2.1: onboarding, the monthly Creator Recap and the new Home

Source: `CURO_Onboarding_Recap_Home_Prompt.md` (wins over v2 where they differ). Built in one go
on branch `v2.1-recap` (D212). Decisions D212–D222.

## A. First-run flow
`/` with no session → **`/start`**: the username screen (validated as typed). Continue creates
an **anonymous session** first — Supabase `signInAnonymously()` when configured, otherwise the
local stub `POST /v1/auth/anonymous` (an `auth.users` row with `is_anonymous = true`) — then
`POST /v1/onboarding/username`. Errors: not found, private ("CURO can only read public
profiles…"), and **already a CURO account** (409 `account_taken` → "Sign in instead").
Then three onboarding cards (Home, Idea Studio, Simulator; Sketch-style SVG art, dots, Next,
Skip) with a **live progress strip** from `GET /v1/onboarding/status` (`step`: profile →
reels → comments → recap; polling every 1.5 s — Realtime when Supabase is on). The last card's
button is "See my recap" once `recap_id` is set, "Almost there…" before. A waiting screen with
teasers covers the rest (90 s → "We'll notify you", into Home with a live placeholder; 5 min →
logged error + friendly fallback). After the recap: **Save your account** (email + code;
local `POST /v1/auth/convert`, Supabase `updateUser({email})` + `verifyOtp('email_change')`),
or "Maybe later" (a reminder on Home next time). Anonymous accounts that never convert are
deleted after 30 days by the daily cleanup.

## B. Creator Recap
- **`services/recap.py`** (pure, unit-tested): facts per slide, minimum-data rules, slide choice
  and order (hook → wins → audience → style → reveal; 5–12 slides), creator level + modifier,
  archetype (+ runner-up, evidence), "that's like…" comparisons, Indian number formatting.
  Thresholds, copy and comparisons live in **`services/recap_config.py`**.
- **Periods:** first = last 90 days (or all history); monthly = previous calendar month in the
  creator's time zone, built on the 1st by the scheduler (paused creators: on next login).
- **Table `recaps`** (migration 0017): as specified; unique (creator, kind, period_start); RLS own.
- **Job `build_recap`**: facts → slides → **T23 write recap copy** (one call, JSON per slide:
  headline ≤ 60, subline ≤ 90) → validator per line (retry once, then template) → store.
  `onboard_public` enqueues it (kind `first`) once the newest 10 reels' comments are in.
- **Endpoints:** `GET /v1/recaps/latest`, `GET /v1/recaps`, `GET /v1/recaps/{id}`,
  `POST /v1/recaps/{id}/viewed`, `GET /v1/recaps/{id}/share-image` (1080×1920 SVG, rendered
  server-side; the web converts it to PNG for Share/Download).
- **Cost:** one Claude call per recap, recorded in `usage_ledger` as task `T23` (feature
  `recap`); free on every plan.

## C. New Home — four swipeable sections
1. **Insights: your Creator Recap** — cover card (New badge until viewed) → 3–4 highlight cards
   (open the story at that slide) → "All recaps".
2. **Opportunity areas** (top 5, v2).
3. **Trending for you** — tap → trend detail sheet with "Make this my way" → Studio.
4. **What your followers will love** — `follower_ideas` (migration 0017), candidates from
   comment requests/questions, proven sub-clusters and pattern cards, and Simulator audience
   segments; score `0.45 demand + 0.35 proven + 0.20 novelty`; deduped against opportunities by
   embedding similarity (≥ 0.85, the higher section keeps it); named by **T24** with the number
   check. Rebuilt weekly and after each recap. `GET /v1/follower-ideas`.
Carousels: scroll-snap, the next card peeks, page dots, keyboard/trackpad; "See all" per section;
skeletons; a retry card per section.

## D. Task numbers
The prompt's T16/T17 are already taken (v2: T16 name_trend, T17 segment_audience), so the recap
copy is **T23** and the follower idea is **T24** (D213).

## E. Demo mode
The Vercel deploy plays back fixtures (D211); the recording now covers the first-run flow,
the recap (with its share image), all recaps and follower ideas.
