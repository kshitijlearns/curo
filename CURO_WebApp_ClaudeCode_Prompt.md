# CURO v2 — turn the app into a Vercel web app (prompt for Claude Code)

You are working in the existing CURO repository: the folder this prompt sits in. Earlier sessions built CURO as an Expo (React Native) app with a FastAPI backend, an RQ worker and scheduler, Postgres + pgvector and Redis, with every outside service behind a provider interface with a mock. Read `README.md`, `PLAN.md`, `docs/DECISIONS.md` and `docs/INTEGRATION.md` before you change anything.

This session has three goals:

1. **Turn CURO into a web app** that runs in Chrome and deploys to **Vercel**.
2. **Apply the product changes** in section 3. They remove features, redesign the Simulator and add plans and credits.
3. **Publish the repo to GitHub**, ready to import into Vercel later. Do **not** deploy to Vercel in this session.

Keep everything that still applies: the logic services, provider interfaces, mocks, `MOCK_MODE`, prompts, tests, the honesty rules and the no-new-numbers validator. Reuse code; don't rewrite what works.

---

## 1. Rules that still hold

- **Public data only.** No Instagram API, no Instagram login, never ask for Instagram passwords.
- **Missing means unknown, never zero.** Hidden likes, missing share counts and disabled comments are `null`, shown as a dash, and left out of rates and baselines.
- **Every number is relative to the creator's own baseline** at the same reel age.
- **Honesty rules:**
  - Predictions are ranges labelled "estimate based on your history".
  - Script notes say "associated with", never "will".
  - AI text may only contain numbers from its input facts (keep the validator on every AI text a creator reads).
- **One project ID** carries opportunity → idea → script → storyboard → caption → simulation.
- **At most 5 hashtags**, enforced in UI, API and database.
- **Business logic never branches on `MOCK_MODE`.** Only the provider factory reads it.
- **No secrets in the repo, ever.**
- **Log every deviation** from this prompt in `docs/DECISIONS.md`, with the reason.

---

## 2. Target architecture: everything deployable on Vercel

### Before you start
Check Vercel's current documentation for:
- Python functions (FastAPI support)
- function maximum duration on Hobby and Pro
- Cron Jobs (how often they can run on each plan)
- request body size limits

Write what you find at the top of `docs/DEPLOY_VERCEL.md`. Design around those limits. If a limit makes something below impossible, use the fallback named there and log it.

### Layout
```
/web        Next.js (App Router, TypeScript) — the web app. Replaces the Expo app.
/api        FastAPI package `curo` (existing), exposed as Vercel Python functions under /api/*
/db         SQL migrations (existing), run against Supabase
/fixtures   demo dataset (existing)
/tools      existing tools; add a local dev runner
/docs       docs, DECISIONS.md, INTEGRATION.md, DEPLOY_VERCEL.md
/legacy/app the old Expo app, moved here untouched (don't delete it)
vercel.json crons, function settings, rewrites
```

### Frontend: `/web` (Next.js on Vercel)
- Port every screen still in scope (section 3) from the Expo app to responsive web components.
- Keep the design system exactly:
  - six colours only: `#5B73F2`, `#C3BFF2`, `#F2D4E2`, `#FFFFFF`, `#E4E4EC`, `#242424`, no gradients
  - Figtree 300/400/600, set in one theme setting
  - the lavender fixed "Curo" header with the Saved icon, and the white rounded sheet that scrolls under it
  - the springy raised-circle bottom nav (Home · Studio · Simulator)
  - the shared components: Nav, Composer (chat + voice), Sketch
- **Layout:**
  - mobile-first
  - on desktop Chrome, centre the app in a phone-width column (max 480 px) on a `#E4E4EC` background
  - must work at 375 px and at 1440 px wide
- **Voice input:** use the browser's Web Speech API in Chrome. Fall back to typing where it's unavailable.
- **Auth:** Supabase Auth with email OTP, in the browser via `@supabase/supabase-js`. The browser gets only public keys (`NEXT_PUBLIC_*`).
- **API calls:** the app calls `/api/v1/*` only, never Apify or AI providers directly. Generate a typed client from the FastAPI OpenAPI schema (there is already a generator; point it at `/web`).
- **Live job progress:** use Supabase Realtime on the `jobs` table, with polling `GET /api/v1/jobs/{id}` as the fallback (the `JobWatcher` pattern already exists).

### Backend on Vercel
- Expose the FastAPI app through Vercel's Python runtime so `/api/v1/*` routes to it. Keep routes and schemas; drop routes for removed features.
- **Database, auth and storage:** Supabase.
  - Postgres + pgvector, with the existing migrations and Row Level Security
  - Supabase Auth
  - Supabase Storage for videos
  - Keep the `db/local` shim for local development.
- **Uploads:** reel uploads go straight from the browser to Supabase Storage through a signed upload URL (`POST /api/v1/uploads/sign` already exists), never through a Vercel function body.
- **Remove Redis and RQ.** Replace them with a **Postgres-backed job queue** on the existing `jobs` table:
  - claim jobs with `SELECT … FOR UPDATE SKIP LOCKED`
  - keep idempotency keys, retries with backoff, and a `locked_until` lease
- **Worker:** a Vercel function `POST /api/internal/run-jobs`, protected by a `CRON_SECRET` header, that claims and runs jobs until it nears its time limit.
- **Scheduler:** a Vercel Cron entry in `vercel.json` that calls the worker endpoint, plus cron entries for the daily and weekly jobs.
- **Long jobs** (onboarding, `process_reel`, `run_simulation`) must run as **resumable steps**. Each step saves its progress and enqueues the next, so no single step outlives a function's time limit. A 1,000-agent simulation runs in batches, e.g. 100 agents per step.
- **Fallback:** if Vercel's cron frequency or duration limits make this unworkable on the chosen plan, keep the same job code and add `worker/standalone.py`, which runs the same job loop as a long-lived process for a small host. Document both options in `docs/DEPLOY_VERCEL.md`.

### Local development
- `make dev` (and `./dev.ps1 dev` on Windows) starts Postgres + pgvector, the FastAPI app, a local job loop (`worker/standalone.py`) and `next dev`.
- Keep the no-Docker option (embedded Postgres) working.
- `MOCK_MODE=true` stays the default, so the whole app runs on fixtures with no keys.

---

## 3. Product changes

### 3.1 Remove: peer tracking
Remove the whole peer feature:
- peer suggestion and peer search (hashtag-based candidate search)
- adding and confirming peers, and the onboarding peer step
- peer collection jobs, peer snapshots, peer video analysis
- the peers screens and settings
- `routes/peers.py`, `jobs/peers.py`, `services/peers.py`

Write a new migration that drops peer-only tables and policies (`peers`, peer visibility helpers). Keep `accounts` for the creator's own account.

Then fix everything that used peers:
- **Opportunity score:** drop the "Peer evidence" part and re-weight to
  `Score = 10 × (0.35 F + 0.25 D + 0.25 T + 0.15 O)`
  (F creator fit, D audience demand, T timeliness, O openness).
  - Remove the "Competitor" candidate source.
  - On the detail page, replace "What your competitors are doing" with **"What's trending in your niche"**, built from the shared trend feed (3.4).
- **Idea score:** drop P and re-weight to
  `0.40 H + 0.30 A + 0.20 T + 0.10 N`.
  - The "Adapted" slot now adapts a trending angle instead of a peer outlier.
- **Hashtags:** candidates come from the creator's own past hashtags, the trend feed and AI suggestions. Re-weight the scoring accordingly.
- **Simulator neighbours:** the creator's own reels only.
- **Cold start:** with fewer than 5 reels, use cross-creator pattern priors (`pattern_cards` with `account_id` null) built from all CURO creators' own reels, labelled "based on creators like you".

Update every affected unit test. The old worked examples that use peer numbers (Ganpati 0.82, ideas 0.80/0.71/0.60) no longer apply. Write new worked examples for the new formulas, hand-check them, and record them in `docs/DECISIONS.md`.

### 3.2 Remove: Insights page and the previous-content carousel
- Remove the Insights screen (reel phase, "what your audience thinks" cards, top comment) and the Home carousel of past reels, with their arrows.
- Keep the data underneath: reels, snapshots, comments, baselines and pattern cards, because Opportunities, Studio and the Simulator use them.
- Remove `GET /v1/reels/{id}/insights` and the carousel endpoint from the app's API surface.

### 3.3 Data collection: the creator's own profile only, with cost controls
CURO reads the creator's public profile, reels, counts and comments, nothing from other accounts except the shared trend feed. Make these changes in `jobs/collect.py`, `services/schedule.py` and related code:

| Setting | New value |
|---|---|
| Onboarding | Profile + latest 50 reels of metadata. Analyse the newest 30. Comments on the newest 30, up to `COMMENT_LIMIT` (default **100**, configurable) |
| Comment re-reads | Never re-read all comments. Fetch only comments newer than the newest one stored, at most twice per reel: about **24 h** and **7 days** after posting |
| New-reel discovery | Every **12 h** (was 3 h), profile + latest **3** reels |
| Snapshot schedule (own reels) | Every 6 h for the first 48 h, daily to day 7, weekly to day 30, then stop (about 15 snapshots) |
| Inactive users | Pause all collection and processing for a creator who hasn't opened the app in **14 days**. Resume on next login with one catch-up run |

### 3.4 New: "Trending for you"
- **Home now has two sections:** **Opportunity areas** (top 5, as before) and **Trending for you**.
- **Shared trend feed:** a daily job per niche (start with about 10 niches) reads about 5 hashtag pages of about 30 reels each. Combine it with the existing festival calendar.
- Claude turns each niche's feed into 3–6 trend cards. Each card has a name, why it's rising, example angles, a timing window, and how crowded it is.
- **Personalised from shared data:** "Trending for you" filters and ranks the niche's cards by fit with the creator's own content. Trend data is fetched once per niche and shared by all creators, never per creator.
- **New tables:** `trend_cards` (niche, name, summary, momentum, saturation, window, evidence, created_at) and a `niches` list. Re-use `hashtag_pages` as the cache.

### 3.5 Redesigned Simulator: AI followers
The creator uploads their **finished reel** (MP4/MOV, max **90 seconds**). The Simulator runs a crowd of AI followers on it and shows how a feed of real followers might react.

**Pipeline** (each step resumable, see section 2):

1. **Watch once.** Gemini turns the video into a second-by-second timeline: what's on screen, what's said, on-screen text, when the hook and the payoff land. Store it on the simulation.
2. **Personas.**
   - Built **once per creator, refreshed monthly**, not per simulation.
   - Group the creator's commenters by the topics, language and tone of their comments into 4–8 audience segments, sized by share of comments.
   - Generate **1,000 agent personas** across those segments in proportion to segment size.
   - Personas describe a segment-style viewer: interests, what they watch for, how they react.
   - **Never store or reuse commenters' handles. Never build a persona of a real individual.**
   - Store them in `audience_personas` (creator_id, agent_no, segment, persona_text, version).
3. **Agents react.**
   - Each agent reads the timeline, as one reel among a few others in a short feed, and returns JSON:
     `{watch_until_s, skipped (bool), liked, commented, comment_text|null, shared, saved, reason}`
   - Run in batches (e.g. 100 agents per step) with prompt caching of the shared timeline.
   - Model: `CLAUDE_MODEL_AGENTS`. Check the current Claude models page for the Claude Haiku 5.5 model ID and use it if available, else Haiku 4.5. Log the choice.
4. **Thread round.** Agents who engaged see the comment thread and may reply to or like comments (one short pass).
5. **Calibrate and predict.**
   - Agents over-engage compared with real people. Calibrate agent rates against the creator's real past reels: run the agents on a sample of the creator's past reels once per persona refresh, and fit a per-metric correction factor.
   - Then predict: likes, comments, shares and saves as ranges against the creator's usual views; a watch-time / skip curve (share of agents still watching at each second); and an **overall engagement score (0–100)** compared with the creator's own past reels.
   - Label saves as **"simulated"**: saves aren't public, so they can't be checked against real results.
   - Keep the accuracy record: after posting, compare predictions with the real public counts.
6. **Explain.** Up to 3 "what's working", 3 "what's holding it back" and 3 suggested edits, each tied to a timestamp. The no-new-numbers check applies.

**Simulator UI** (web, in the CURO design system):
- **Results:** score ring, predicted ranges, skip curve, best time to post (from the creator's own history), and the explanations.
- **Simulated comments:** a feed that looks like a social app's comment section, using CURO's own colours, fonts and icons. Do **not** copy Instagram's branding, logos or exact layout.
  - Commenters are shown as **"Agent 12 · Festive planner"** (agent number + segment). No profile pictures, no generated usernames.
  - A permanent label reads **"Simulated by CURO's AI audience. Not real comments."**
- **Talk to an agent:** tap any agent to open a one-to-one chat ("why did you skip at 0:04?", "what did you like?"). The agent answers in character from its persona, its recorded reaction and the timeline, using `CLAUDE_MODEL_MAIN`. **Up to 10 agent messages per simulation.**
- **Re-run:** uploading an edited version is a new simulation (uses a credit). Show the new score next to the previous one.

Write new mocks for every new task (timeline, personas, agent reactions, thread round, agent chat) that return schema-valid output from fixtures, so the whole flow runs with `MOCK_MODE=true`.

### 3.6 Plans, credits and usage limits
| Plan | Price | Each month |
|---|---|---|
| **Free** | $0 | Opportunity areas, Trending for you, **2 Studio projects**, **2 simulations** |
| **Pro** | **$30/month** | Everything in Free, **10 Studio projects**, **10 simulations**, Ask Curo (fair use: 100 messages) |
| **Top-ups** | about **$1.50 each** | Extra Studio projects or simulations, bought one by one |

**Credit rules:**
- **1 Studio project credit** = one project from idea to caption, including up to **10 revisions** across its steps.
- **1 simulation credit** = one upload, including up to **10 agent chat messages**.
- Credits **reset monthly and don't carry over**. Top-up credits don't expire.

**Build now** (fully working on mocks):
- tables `plans`, `subscriptions`, `credit_ledger` (append-only: grants, spends, top-ups, with reason and job/project ID)
- server-side enforcement on every endpoint that spends a credit, with a clear "out of credits" response and an upgrade screen
- a plan and credits page in Settings showing what's left this month
- a `usage_ledger` table recording, per creator and per call: provider, model, tokens in/out, Apify results and an estimated cost in USD
- a per-creator monthly cost alert threshold (config)
- an internal, admin-only `/admin/costs` page summarising cost per user and per feature

**Payments: interface only, for now.**
- Add a `PaymentProvider` interface (create checkout, handle webhook, cancel) with a mock that grants Pro or top-ups instantly in development.
- Leave a stub for a real gateway (e.g. Razorpay or Stripe) that raises `NotImplementedError` with a TODO, and list it in `docs/INTEGRATION.md`.

### 3.7 Ask Curo
- Keep Ask Curo (tool-calling assistant on the creator's own data) inside Studio and the Simulator.
- Count its messages against the Pro fair-use cap of 100 a month; free users get 10.
- Re-point its tools away from removed features: no peer or insights tools.

### 3.8 Models and providers
- `CLAUDE_MODEL_MAIN=claude-sonnet-5-5`
- `CLAUDE_MODEL_FAST`: Haiku, for labelling
- `CLAUDE_MODEL_AGENTS`: see 3.5. Confirm every ID on the current models page.
- `GEMINI_VIDEO_MODEL`: make this configurable. Default to the current Gemini Flash model, and note Flash-Lite as the cheaper option.
- `GEMINI_EMBEDDING_MODEL=gemini-embedding-2` at **768** dimensions.
  - Never mix mock and real vectors in one table.
  - Add a `tools/reembed.py` that re-embeds everything and rebuilds sub-clusters when the embedding model changes.
- Provider stubs stay stubs this session (`NotImplementedError` + TODO). Real keys come later.

---

## 4. Environment variables
Rewrite `.env.example` (and `web/.env.example`):
- **Remove:** Redis, Expo and peer variables.
- **Add:**
  - `CRON_SECRET`
  - `CLAUDE_MODEL_AGENTS`
  - `COMMENT_LIMIT`
  - `INACTIVE_PAUSE_DAYS=14`
  - `SIM_AGENTS=1000`
  - `SIM_MAX_SECONDS=90`
  - credit amounts per plan
  - `COST_ALERT_USD`
  - `PAYMENT_PROVIDER=mock`
  - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Every variable needed in Vercel must be listed in `docs/DEPLOY_VERCEL.md` with what it's for and whether it's secret.

---

## 5. Publish to GitHub (do this last, after tests pass)

1. This folder is **not** a git repository yet. Run `git init` and create a proper `.gitignore`. It must cover `.env`, `.env.*` (but not `.env.example`), `.venv/`, `node_modules/`, `.next/`, `.vercel/`, `.data/`, `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, `reference/screens` large binaries if over 5 MB, and any `*.local` files.
2. **Before the first commit, scan for secrets:**
   - Check that no `.env` file and no API key, token or service-role key is staged.
   - Search staged files for `sk-`, `AIza`, `apify_api_`, `service_role` and `eyJ` (JWTs).
   - If anything is found, stop and tell me.
3. **Commit** with a clear message.
4. **Push** to GitHub with the `gh` CLI. Check `gh auth status` first; if it isn't logged in, stop and ask me to run `gh auth login`.
   - **Target:** the existing repository **`kshitijlearns/curo`**. Today it holds only the docs, uploaded through the web. Push this codebase to a new branch **`web-v2`** and open a pull request into `main` titled "CURO v2: web app for Vercel".
   - Don't force-push over `main`.
   - If I don't have push access to that repo, create a new **private** repo `curo-web` under my account instead, and push there.
5. **Do not** connect or deploy to Vercel. Finish with `docs/DEPLOY_VERCEL.md`: the exact steps to import the repo in Vercel, set the root and build settings for `/web` and the Python functions, add the environment variables, run migrations on Supabase, and set up the cron jobs.

---

## 6. Build order: stop after each phase and report

After each phase, give me a short report (what changed, what's mocked, any decisions) and the exact steps to check it in Chrome. Then wait for me to say continue.

0. **Plan.**
   - Read everything listed at the top.
   - Write `PLAN_V2.md` covering the architecture, the removed and added features, the new formulas with worked examples, new tables and migrations, new task schemas, and the job-step design for Vercel.
   - *Check:* I approve the plan.
1. **Web shell.**
   - Create `/web` (Next.js) with the theme, header, sheet, nav and composer.
   - Get Supabase local auth (email OTP) working.
   - Move the Expo app to `/legacy/app`.
   - *Check:* `make dev`, open `http://localhost:3000` in Chrome, sign in, and switch between Home, Studio and Simulator.
2. **Backend on the Vercel shape.**
   - FastAPI behind `/api/v1`.
   - Postgres job queue and the worker endpoint, with Redis/RQ removed.
   - Resumable job steps, `vercel.json` with crons, and a local job loop.
   - *Check:* the full test suite passes. A demo onboarding runs end to end through the new queue.
3. **Removals and collection changes.** Sections 3.1, 3.2 and 3.3, with migrations, re-weighted formulas and updated tests.
   - *Check:* the demo creator onboards with no peer step, and costs per onboarding in `usage_ledger` reflect the new limits.
4. **Home: Opportunities + Trending for you** (3.4).
   - *Check:* the demo shows 5 opportunities and trend cards, and their score parts add up.
5. **Studio on web.** Port all Studio steps. Keep the "Why this idea" shares and the 5-hashtag rule.
   - *Check:* the full journey from an opportunity to a saved draft works in Chrome.
6. **Simulator v2** (3.5), on mocks.
   - *Check:* uploading a sample reel shows the score, ranges, skip curve, simulated comment feed with agent labels, and a working agent chat. A re-upload shows the score change.
7. **Plans, credits, usage and costs** (3.6, 3.7).
   - *Check:* a free user is blocked after 2 simulations with an upgrade screen. The mock payment grants Pro. `/admin/costs` shows per-user cost.
8. **Hardening.**
   - Error and empty states, account deletion, accessibility basics (keyboard and labels), and Lighthouse checks in Chrome.
   - Write `docs/INTEGRATION.md` (updated) and `docs/DEPLOY_VERCEL.md`.
   - *Check:* tests, lint and type-check pass.
9. **Publish to GitHub** (section 5).
   - *Check:* the pull request exists and contains no secrets.

## 7. Working rules
- Prefer simple, readable code. This is an MVP.
- Test every formula against hand-calculated worked examples.
- Record real API responses only later, when keys exist. Tests never call outside services.
- If something genuinely blocks you, ask me one clear question rather than guessing.
- Start with Phase 0: read the files and write `PLAN_V2.md`.
