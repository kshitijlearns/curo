# CURO — build plan

This is the working plan for building CURO from the three source files. It covers screens, modules, schema, provider interfaces, AI task schemas and the phase plan. Deviations and open questions live in [docs/DECISIONS.md](docs/DECISIONS.md); integration steps for real API keys will live in [docs/INTEGRATION.md](docs/INTEGRATION.md).

Sources and precedence (from the prompt):

| Source | Wins on |
| --- | --- |
| `docs/CURO_MVP_Build_Plan.md` (MVP doc) | Scope and architecture |
| `docs/CURO_Backend_Logic.md` (logic doc) | Behaviour and formulas |
| `reference/CURO_prototype.html` (prototype) | Look, copy, interactions, animation |

---

## 1. Ground rules this plan enforces

1. Public data only. No Instagram API or login. Saves, reach, impressions, watch time, skip rate, follower split, demographics and online times are never stored, shown or estimated.
2. Missing means unknown: hidden likes, missing shares and disabled comments are `NULL`, shown as "–", and excluded from rates and baselines.
3. Every number is relative to the creator's own baseline at the same reel age.
4. Honesty: ranges labelled "estimate based on your history"; notes say "associated with", never "will"; percentages are labelled as shares of a scoring formula.
5. No-new-numbers validator on every AI text a creator reads (T5, T10, T12, T14), with regenerate-once then template fallback.
6. One project ID carries opportunity → idea → script → storyboard → caption → simulation.
7. At most 5 hashtags, enforced in UI, API (422) and DB (`CHECK`).
8. No features beyond the three files. Infrastructure needed to run locally (auth stub, job polling, local uploads) is logged in DECISIONS.md.
9. Business logic never branches on `MOCK_MODE`; only the provider factory reads it.

---

## 2. Local architecture

```
 Phone (Expo Go / dev build)
   │  HTTPS JSON + SSE (Bearer JWT)
   ▼
 api  (FastAPI, uvicorn)  ──enqueue──►  redis  ──►  worker (RQ)  +  scheduler
   │                                                  │
   └──────────────► postgres + pgvector ◄─────────────┘
                     (RLS, Supabase-compatible auth shim)
 Providers (behind interfaces, mocks now):
   PublicDataProvider · VideoUnderstandingProvider · EmbeddingProvider
   LLMProvider · StorageProvider (local disk) · Monitoring (no-op)
```

- **Database:** Postgres 16 + pgvector in Docker. A local-only shim (`db/local/`) creates what Supabase provides (`auth` schema, `auth.uid()`, roles `anon` / `authenticated` / `service_role`, `extensions` schema), so the same migrations run unchanged on Supabase later.
- **Auth:** a local auth stub behind an `AuthProvider` interface issues Supabase-format JWTs (HS256, `SUPABASE_JWT_SECRET`, `aud=authenticated`). The API verifies tokens exactly as it will with Supabase.
- **RLS is real:** each API request runs in a transaction with `SET LOCAL ROLE authenticated` and `request.jwt.claims` set, so Postgres policies decide what a creator can read. The worker uses the service role.
- **Job progress:** the MVP uses Supabase Realtime on `jobs`. Locally the app polls `GET /v1/jobs/{id}` behind a `JobWatcher` interface; a Realtime watcher replaces it later.
- **Queue:** Redis + RQ. Jobs are idempotent plain functions in `api/curo/jobs/`, so tests run them inline.
- **Clock:** `curo.clock.now()` everywhere. `FAKE_NOW` sets a time-travel anchor; `tools/timetravel.py` sets or advances it for every process (stored in Redis).

`make dev` (or `./dev.ps1` on Windows) starts db, redis, api, worker and scheduler with Docker Compose, runs migrations and starts Expo. Without Docker, `./dev.ps1 local` runs the same backend in one process (embedded Postgres, the worker as a thread; DECISIONS D115).

---

## 3. Repository layout

```
/app          Expo SDK 57 React Native (TypeScript), Expo Router
  src/app          thin route files (Expo Router): / = main shell, /setup, later login/onboarding/settings
  src/theme        colors (six only), typography (one font setting), motion curves
  src/components   Nav, Composer, ReelThumb, Sketch, Header, Toast, ScoreRing, Metric, motion primitives…
  src/screens      shell/ (header + sheet + dock), home/, studio/, sim/, Saved, later Settings/Onboarding/Login
  src/state        the shell's store (navigation, Studio project, Simulator); actions call the API from Phase 2
  src/mock         Phase 1 data ported from the prototype (removed screen by screen as the API lands)
  src/api          generated OpenAPI types + typed client + JobWatcher
/api          FastAPI package `curo`
  curo/routes      one module per endpoint group (section 7 of the MVP doc)
  curo/services    all product logic (pure functions where possible, unit-tested)
  curo/providers   interfaces, mocks, real stubs (raise NotImplementedError + TODO)
  curo/schemas     Pydantic: API models + task schemas T1–T15
  curo/jobs        the 12 job functions (shared with the worker)
  curo/db          connection pool, RLS session, migration runner
  prompts/         versioned prompt files for every Claude/Gemini task
  tests/
/worker       RQ worker + scheduler entrypoints (imports `curo`)
/db           migrations/*.sql, local/ (Supabase shim), seed loader
/fixtures     generate.py + generated demo dataset (deterministic)
/tools        extract_prototype.py, screenshot_prototype.py, timetravel.py, record_contracts.py
/reference    unpacked prototype + screenshots (read-only)
/docs         copies of both docs, DECISIONS.md, INTEGRATION.md
```

---

## 4. Screens

All screens share the prototype shell: lavender fixed header (brand "Curo" + Saved button, or back/title/subtitle variant), white 32 px rounded sheet that scrolls under it, dock with the Composer (when active) and the springy raised-circle Nav (Home · Studio · Simulator).

| Screen | Prototype source | Logic | Endpoints |
| --- | --- | --- | --- |
| Login | — (new, shell style) | Supabase-style email OTP (local stub) | auth stub |
| Onboarding | — (new, shell style) | Logic §3 onboarding, peers confirm, cold-start questions | `POST /v1/onboarding/username`, `GET /v1/onboarding/status`, `GET /v1/peers/suggestions`, `POST /v1/peers` |
| Home | HOME block | Logic §6 carousel + arrows; §8 top-5 opportunities | `GET /v1/me`, `GET /v1/reels?limit=10`, `POST /v1/reels/refresh`, `GET /v1/opportunities` |
| Insights | INSIGHTS block | Logic §7 phase, audience cards, top comment | `GET /v1/reels/{id}/insights` |
| Opportunity pages (swipeable) | OPPORTUNITY DETAIL CAROUSEL | Logic §8 detail assembly | `GET /v1/opportunities/{id}`, save/unsave, dismiss |
| Saved | SAVED block | Logic §14 Saved (score then vs today, "window passed") | `GET /v1/saved` |
| Studio — validate chat (empty) | studioEmpty | Logic §9 validate | `POST /v1/ideas/validate` |
| Studio 1 — Ideas | Stage 1 | Logic §9 contest, slots, "Why this idea" shares | `POST /v1/projects`, `POST …/ideas`, `POST …/ideas/{id}/select` |
| Studio 2 — Script | Stage 2 (before / generated) | Logic §10 | `POST …/script`, `…/script/revise`, `PUT …/script` |
| Studio 3 — Visuals | Storyboard stage | Logic §11 | `POST …/storyboard`, `…/storyboard/revise` |
| Studio 4 — Caption | Caption stage | Logic §12 | `POST …/captions`, `…/captions/revise`, `PUT …/hashtags` |
| Studio 5 — Final draft | Final stage | Logic §12 final | `POST …/save`, `GET /v1/projects/{id}` |
| Simulator — upload | simIntro | Logic §13 inputs, audience toggle, compare switch | `POST /v1/uploads/sign`, `POST /v1/simulations` |
| Simulator — running | simLoading | job progress | `GET /v1/simulations/{id}` |
| Simulator — result | simResult | T9, reasons, edits, best time, DNA, accuracy | `GET /v1/simulations/{id}`, `…/edits/{id}/apply`, `…/rerun` |
| Ask Curo | composer + Simulator chat | Logic §14 | `POST /v1/chat` (SSE) |
| Settings | — (new, shell style) | creator memory, peers, delete account | `GET/DELETE /v1/me`, peers endpoints, memory endpoints |

Shared components (exact port of prototype): **Nav** (52 px raised circle lifts 30 px, white ring, spring `cubic-bezier(.2,.8,.3,1.25)` 380 ms), **Composer** (hint line, pill input, mic with pulse + waveform bars while listening, send button), **ReelThumb** (4 tones, beam/plant illustration, title, duration pill), **Sketch** (9 kinds: closeup, flatlay, look1, look2, look3, rewind, mirror, cta, triptych).

Theme: six colours only — `#5B73F2` blue, `#C3BFF2` lavender, `#F2D4E2` pink, `#FFFFFF` white, `#E4E4EC` gray, `#242424` ink (muted text = ink at 72% opacity, as in the prototype). No gradients. Font: Figtree 300/400/600, set once in `theme/typography.ts`.

Prototype elements removed by the docs (see DECISIONS.md): saves/reposts metrics, the persona section in the Simulator (MVP: out), commenter handles in the top comment.

---

## 5. Backend modules and what tests them

| Module (`api/curo/services/…`) | Logic doc | Unit tests against |
| --- | --- | --- |
| `metrics.py` — rates, null rules, age buckets, value at age t | §4 | null handling, interpolation |
| `baselines.py` — median of last 20 reels per metric × age bucket, p25/p75/n, growth curve g(t); paid partnerships excluded, deleted reels kept | §4, §5 step 7 | hand-computed medians |
| `arrows.py` — expected(t) from simulation × g(t) or baseline; ±5% flat band; comparison label | §6 | **↗32%** (95K × 0.72 = 68.4K; 90K → +32%) |
| `phases.py` — velocity, 5 phase rules with precedence, phase range p25–p75, views ÷ followers, freshness | §7 | rule table cases |
| `audience_cards.py` — lift z-scores, card selection (≥0.75, strongest positive, z ≤ −1 rule, comment cards) | §7 | selection cases |
| `top_comment.py` — like then reply ranking, skip own/bot/emoji-only, negative label | §7 | ranking cases |
| `embeddings` + `subclusters.py` — HDBSCAN over cosine distance, groups only (never one reel), lifts per group | §4, §5 | clustering of fixture text |
| `comments.py` — bot filter, labels, themes, language mix, places | §5 step 4 | Hinglish/Hindi/English cases |
| `pattern_cards.py` — with/without lift, shrinkage k=10, "yours" if n ≥ 8 and test passes | §5 | **shrinkage n=10 → 50%, n=40 → 80%** |
| `opportunities/` — candidates (4 sources), merge, filters, F/D/P/T/O scoring, explanation assembly | §8 | **Ganpati parts → 0.82 → 8/10** |
| `ideas.py` — evidence pack, 15 candidates, H/A/P/T/N, slots, diversity rule, shares, validate verdicts | §9 | **0.80 / 0.71 / 0.60; 0.27 vs 0.34** |
| `script.py` — duration band, beat structure, word budget, notes filtered by pattern cards, targeted revisions | §10 | word budget 2.6 w/s × 32 s ≈ 83; untouched beats identical |
| `storyboard.py` — beat timing, toolkit shots, feasibility (4 costs), "easier", frame-level revisions | §11 | timing + feasibility cases |
| `captions.py` + `hashtags.py` — 3 caption jobs; 0.5/0.3/0.2 scoring; broad/niche/niche/community/series mix; 5 max | §12 | mix + limit |
| `simulator.py` — T9 neighbours, lifts, estimate (±30% cap), ranges (p10–p90, widened), percentile score, reasons, edit re-scoring, audience toggle, draft comparison | §13, MVP §10 | weighted cases |
| `best_time.py` — views lift by day × hour, avoid peer hours, next 48 h | §13 | slot choice |
| `accuracy.py` — range-contains-actual record, automatic widening | §13, §15 | record text |
| `validator.py` — no-new-numbers | MVP §10 | planted number caught |
| `data_quality.py` — the 7 rules | MVP §4 | each rule |
| `deletion.py` — account deletion | MVP §7, logic §17 | rows gone, RLS intact |
| `assistant/` — intent routing, tools, loop, SSE, project + creator memory | §14 | tool citations, planted number |

Real logic is never mocked. Only the model/vendor calls are.

---

## 6. Database (27 tables, `db/migrations/`)

Supabase-compatible SQL. Every table has RLS enabled. Helper functions (security definer): `curo.current_creator_id()` and `curo.visible_account_ids()` (the creator's own account + confirmed/suggested peers).

**Accounts and data**

| Table | Columns (key) | RLS |
| --- | --- | --- |
| `creators` | id, user_id → auth.users, ig_username, account_id*, niche, goal, formats*, languages*, voice_profile jsonb, accuracy jsonb*, created_at | own row |
| `accounts` | id, username (unique, lower), bio, followers, following, posts, category, is_private, status*, last_collected_at | visible accounts |
| `account_snapshots` | account_id, taken_at, followers, following, posts | visible accounts |
| `peers` | creator_id, account_id, source (suggested/creator), confirmed | own |
| `reels` | id, account_id, ig_media_id, shortcode, permalink, posted_at, duration_s, caption, hashtags[], mentions[]*, audio_name, is_paid_partnership, video_path, thumb_path, first_seen_at, is_deleted*, likes_hidden*, comments_disabled* | visible accounts |
| `metric_snapshots` | reel_id, taken_at, age_hours, views, likes NULL, comments NULL, shares NULL, flagged, flag_reason*; index (reel_id, taken_at) | via reel |
| `comments` | id, reel_id, text (mentions masked), posted_at, like_count, reply_count, is_creator*, language*, sentiment, intent, theme_id, is_bot, tags_friend — **no handles** | via reel |

**Learned data**

| Table | Columns | RLS |
| --- | --- | --- |
| `reel_dna` | reel_id, content, production, transcript (T1), confidence, model_version | via reel |
| `reel_embeddings` | reel_id, embedding vector(768), model; HNSW cosine index | via reel |
| `baselines` | account_id, metric, age_bucket, median, p25, p75, n | visible accounts |
| `subclusters` | id, account_id, label, centroid vector(768), reel_ids[], lifts | visible accounts |
| `comment_themes` | id, account_id, label, kind*, share, sample_comment_ids[] | visible accounts |
| `pattern_cards` | id, account_id (NULL = cross-creator prior), feature, value, metric, effect, n, confidence, scope | visible accounts or NULL |
| `hashtag_pages` | tag, fetched_at, top_reel_ids[], recent_reel_ids[], reel_count_7d, reels jsonb* | all authenticated |
| `festival_calendar` | id, name, starts_on, ends_on, regions[], niches[], keywords[] | all authenticated |

**Product data**

| Table | Columns | RLS |
| --- | --- | --- |
| `opportunities` | id, creator_id, name, tag, score, parts, evidence, status (active/saved/dismissed/expired), window_ends_on, topic_key*, saved_score*, description*, why_it_fits* | own |
| `projects` | id, creator_id, opportunity_id, step, status, posted_reel_id, title* | own |
| `ideas` | id, project_id, text, slot, score, parts, evidence_ids, source, selected, round*, prompt* | via project |
| `script_versions` | id, project_id, version, beats (id, text, timing, note), instruction, changed_beat_ids* | via project |
| `storyboard_versions` | id, project_id, version, frames (beat_id link), feasibility, stale_frame_ids* | via project |
| `captions` | id, project_id, version, options, chosen, hashtags — `CHECK (cardinality(hashtags) <= 5)` | via project |
| `simulations` | id, creator_id, project_id, video_path, audience, status, score, predicted, result, method_version, posted_reel_id*, actual*, in_range* | own |
| `simulation_edits` | id, simulation_id, description, feature_change, delta, effort, applied | via simulation |

**System**

| Table | Columns | RLS |
| --- | --- | --- |
| `chat_messages` | id, creator_id, context, role, content, tool_calls | own |
| `creator_memory` | creator_id, key, value, source | own (select + delete) |
| `jobs` | id, creator_id*, type, status, progress, payload, result*, error, idempotency_key* | own (read) |
| `events` | creator_id, name, props, created_at | own (insert) |

`*` = column added beyond the MVP doc's key columns; each is listed with its reason in DECISIONS.md.

---

## 7. Provider interfaces (`api/curo/providers/`)

| Interface | Methods | Mock now | Real later (stub file) |
| --- | --- | --- | --- |
| `PublicDataProvider` | `get_profile(username)`, `get_reels(username, limit)`, `get_reels_by_shortcodes(username, shortcodes)` (batched snapshot), `get_comments(permalink, limit)`, `get_hashtag_page(tag, limit)`, `download(url)` | Reads `/fixtures`; counts come from each reel's growth curve at `clock.now()`, so repeated snapshots grow realistically; applies hidden likes / missing shares / comments off; refuses private accounts | `apify.py`, `brightdata.py` (+ failover wrapper: retry once → backup vendor → mark missed) |
| `VideoUnderstandingProvider` (T1) | `understand(video_ref) -> T1Output` | Fixture T1 per reel; uploads: plausible output from file name + real duration (MP4/MOV `mvhd` parser) | `gemini.py` |
| `EmbeddingProvider` | `embed(texts) -> list[vector]`, `model`, `dim=768` | Deterministic feature-hashing embedding (word + char n-grams + small domain concept lexicon), L2-normalised, model `mock-hash-768-v1` — stable across calls, so vectors never drift | `gemini.py` |
| `LLMProvider` | `run(task, input) -> output` (T2–T8, T10–T13, T15), `chat(request) -> stream of events` (T14 with tools) | Deterministic template generators per task, schema-valid, built only from the evidence passed in | `claude.py` (tool-use structured output, prompt caching, batch for T3/T2-peers) |
| `StorageProvider` | `put`, `get`, `delete`, `signed_upload(path)`, `signed_url(path)` | Local filesystem + HMAC-signed upload/download URLs served by the API | `supabase.py` |
| `Monitoring` | `capture_exception`, `capture_event` | No-op | `sentry_posthog.py` |
| `AuthProvider` | `verify(token)`; local stub issues OTP + JWT | Local stub | Supabase Auth (app uses supabase-js) |

Selection: `MOCK_MODE=true` picks all mocks. Per-provider overrides: `PUBLIC_DATA_PROVIDER`, `VIDEO_PROVIDER`, `EMBEDDING_PROVIDER`, `LLM_PROVIDER`, `STORAGE_PROVIDER`, `MONITORING_PROVIDER`, `AUTH_PROVIDER`. Mocks and real implementations satisfy the same Pydantic schemas; contract tests check both.

---

## 8. AI task schemas (`api/curo/schemas/tasks.py`, prompts in `api/prompts/`)

Each task has `TASK_ID`, `VERSION`, Pydantic `Input` and `Output`. Version is stored with every output.

| ID | Input | Output |
| --- | --- | --- |
| T1 | video ref, duration | `transcript[{t, word}]`, `shots[{start, end}]`, `onscreen_text[{t, text}]`, `seconds[{t, description}]`, `audio_type`, `first_payoff_s` |
| T2 | T1 output, caption, hashtags | `content{cluster, context, characters, core_tension}`, `production{format, hook_type, hook_text, opening_style, narrative, ending, cta_type, pov, camera, cuts_per_10s, audio, visual_style, setting}`, `confidence{field: 0–1}` — below 0.6 stored as `unknown` |
| T3 | ≤200 comments `{id, text}` | `[{id, is_bot, sentiment, intent, theme}]` |
| T4 | sample texts of one group | `{label}` |
| T5 | merged evidence + score parts (facts) | `{name, description, why_it_fits}` |
| T6 | evidence pack, optional creator input/constraints | 15 × `{text, angle, format, target_behaviour, evidence_ids}` |
| T7 | idea, voice profile, beat structure, word budget | `beats[{id, text, est_seconds}]` |
| T8 | beats + pattern cards | `[{beat_id, note_type, pattern_card_id}]` |
| T9 | (code) draft DNA + embedding, neighbours, pattern cards | `score, ranges per metric, reasons, edit deltas` |
| T10 | computed facts only | short plain sentences |
| T11 | beats, creator camera setups, peer devices | `frames[{beat_id, start, end, shot_type, instruction, onscreen_text, transition, icon_key}]` |
| T12 | project, caption patterns, scored hashtag candidates | `captions[3]{text, job}`, `hashtags[5]` |
| T13 | instruction + current state | `{action, targets, params}` |
| T14 | conversation, screen context, tools | streamed reply + tool calls |
| T15 | draft DNA, negative factors | `[{description, feature_change, effort}]` |

Fixed DNA taxonomy (`api/curo/schemas/taxonomy.py`): 14 hook types, 9 narrative shapes, and closed lists for format, opening, ending, CTA, POV, camera, audio, visual style, setting, context.

---

## 9. Jobs and scheduler (`api/curo/jobs/`, `worker/`)

All 12 jobs from the MVP doc, each idempotent (idempotency key + upserts): `onboard_public`, `snapshot_account`, `process_reel`, `label_comments`, `recompute_learning`, `collect_peers`, `collect_hashtags`, `build_opportunities`, `match_posted_reel`, `run_simulation`, `cleanup`, `accuracy_report`.

Scheduler (one loop, every minute of clock time): finds accounts with due reels per the schedule (creator: 3 h to 48 h, 12 h to day 7, daily to day 30, weekly to day 90; peers: daily to day 14 + latest-5 check) and enqueues **one** `snapshot_account` per account; plus nightly/weekly/daily jobs.

---

## 10. Fixture dataset (`fixtures/`)

Deterministic generator (`fixtures/generate.py`, fixed seed) anchored to **12 days before Ganesh Chaturthi 2027** (`FAKE_NOW`).

- **Demo creator** `@curo.demo` — fashion/styling, Mumbai, ~48K followers, 50 reels across 5 sub-clusters: festive styling, reel-making tips, GRWM, hauls, one-item-many-looks. Includes the prototype reels ("3 mistakes ruining your aesthetic reel", "Get ready with me: Navratri edition", "One kurta, five dupattas", "Thrift haul under ₹2,000") and last year's Ganpati reel.
- **10 peers** with the prototype handles (@theoutfitdiaries, @stylewithrhea, @mumbaiwardrobe, @thedrapestory, @kavyawears, @styledbysana, + 4), 30 reels each. Several recent Ganpati outfit reels reach Outlier Index ≥ 2, so "Ganpati dress ideas" emerges from the scoring.
- Growth curves per reel (snapshots are read from the curve at clock time); hidden likes, missing shares, one reel with comments off, a few seen only late.
- Comments in English, Hindi and Hinglish: "that's me", questions, requests ("part 2", "where is it from", "budget version"), friend tags, negatives, spam/bots.
- Fixture T1 outputs per reel; two tiny sample MP4s for the Simulator.
- Hashtag pages for festival tags; festival calendar JSON for the next two years.
- **Seed by replay:** `make seed` sets the clock back 14 days, onboards the demo handle through the real `onboard_public` path, then steps the clock forward running the real scheduler, so recent reels get genuine snapshot histories and older reels stay "seen late". Two of the prototype reels are simulated before they are posted, through the real Simulator, so their arrows compare "vs your simulation".

Targets that must emerge from real logic (not hard-coded): Ganpati ≈ 8/10; three ideas come out Proven / Adapted / Explore.

---

## 11. Phase plan

Each phase ends with a report (built, mocked, decisions) and exact check steps for your machine and phone.

| # | Phase | Done when |
| --- | --- | --- |
| 0 | **Setup** — monorepo, Docker services, migration runner, `make dev` / `dev.ps1`, lint/format, test runners, CI, `.env.example`, prototype unpacked + screenshots | `make dev` brings up db, redis, api (`/health` OK), worker, and the Expo app opens on your phone |
| 1 | **UI port** — every screen on local mock data; header, sheet, nav spring, composer + voice, four metrics | Side-by-side with `/reference/screens/` |
| 2 | **Data layer + collection (mocked)** — full schema + RLS, `PublicDataProvider`, onboarding, batched scheduler, data-quality rules, follower snapshots, fixture load via real path | Demo handle fills Home from the DB; hidden-likes reel shows "–" |
| 3 | **Understanding pipeline** — T1–T4, embeddings, baselines, sub-clusters, pattern cards with shrinkage, comment labels + themes | Every processed reel (newest 30 + every new one, D40) has DNA with confidence; sensible pattern cards |
| 4 | **Home + Insights on real logic** | Three reels match hand-calculated values (calculations in the report) |
| 5 | **Peers + opportunities** | "Ganpati dress ideas" appears with parts that add up; swipe works |
| 6 | **Studio** | Full Ganpati journey from Home to a saved draft, visible on Saved |
| 7 | **Simulator v0** | Sample upload returns a full result; re-run shows the score change |
| 8 | **Ask Curo + memory** | Answers cite real records; a planted number is caught |
| 9 | **Hardening + integration readiness** — tests, error/empty states, deletion, INTEGRATION.md, contract recorder | Full suite passes; INTEGRATION.md is a checklist |

---

## 12. Testing

- **Python:** pytest. Unit tests for every formula (worked examples above). Integration tests run against Postgres + pgvector (Docker locally and in CI) and exercise RLS with two creators. Jobs run inline in tests.
- **App:** Jest (jest-expo) for logic and components, `tsc --noEmit`, ESLint, Prettier.
- **Lint/format:** ruff (lint + format) for Python.
- **CI:** GitHub Actions — Python (with Postgres+pgvector and Redis services) and app checks.
- **Contract tests:** recorded vendor/model responses replayed against each real provider's parser (Phase 9).
