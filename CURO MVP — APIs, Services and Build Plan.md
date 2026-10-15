# CURO MVP — APIs, Services and Build Plan

Oct 13, 2026 · @Kshitij

## 1. Summary

The CURO MVP needs **six outside services**: Apify for public Instagram data, Anthropic's Claude API, Google's Gemini API (video and embeddings), Supabase, Railway for the backend and jobs, and Expo for app builds. Everything else is CURO's own backend, which Claude Code can build from the prototype and the backend logic doc.

The MVP keeps the whole journey clickable on real data: username onboarding, Home, Insights, Opportunities, all five Studio steps, Simulator and Saved. It simplifies the parts that need data CURO doesn't have yet. The biggest one: the Simulator starts with a **nearest-neighbour estimate** built from the creator's own similar reels, not a trained model. The trained model comes once enough results have been collected.

**There is no Instagram API in CURO.** Creators sign up with just a username, nobody logs in with Instagram, and there is no Meta app review to wait for. Every Instagram number comes from public, logged-out collection. The critical path moves to data quality: public pages change, some counts are hidden or missing, and every snapshot costs a scrape. Build the collection layer and its data-quality rules first (section 4).

**How to use this doc with Claude Code.** Give Claude Code three things: the prototype file, the backend logic doc, and this doc. Section 12 is the build order, phase by phase, each with a done-check. Sections 7–11 are the specs it builds against.

## 2. MVP scope

Every screen in the prototype ships, but five pieces of the full design are simplified or deferred until CURO has real data.

| Feature | MVP | How it is built in the MVP | Later |
| --- | --- | --- | --- |
| Username onboarding | In | Apify fetches the profile, latest 50 reels and comments; the pipeline processes the latest 30 | Same |
| Metrics shown | In | Views, likes, comments and shares (where shown); saves, reach and watch time are never shown | Same |
| Home carousel and arrows | In | Arrows compare with the creator's baseline, or with the simulation when one exists | Same |
| Insights: phase, audience cards, top comment | In | Phase from CURO's own view snapshots and views ÷ followers; cards from public rates and comments | Same |
| Opportunity areas | In, simplified | Competitor, Audience and Your content sources fully; Trend from a festival calendar and public hashtag pages | Add search-trend data |
| Peers | In, simplified | Creator types or confirms 5–10 peer usernames; Apify collects their reels | Auto-suggested peers |
| Studio: ideas, script, notes | In | Logic doc sections 9–10 | Same |
| Studio: storyboard | In, simplified | Text frames plus a small library of pre-drawn shot icons | AI-drawn sketches |
| Studio: caption and 5 hashtags | In | Hashtags from the creator's and peers' past hashtags and public hashtag pages | Same |
| Simulator score, report, reasons, edits | In, simplified | Nearest-neighbour estimate (section 10, task T9) | Trained LightGBM model with SHAP |
| Simulator persona fit | Out | Hidden in the MVP | When enough commenters per creator exist |
| Best time to post | In, simplified | From the creator's past views lift by posting day and hour | Add first-hours growth for tracked reels |
| Ask Curo | In | Claude with tool calls on CURO's own data | Same |
| Saved | In | Opportunities and drafts | Same |
| Learning loop | Partial | Store every estimate and actual; refit weights by hand monthly | Automatic refits |
| Publishing to Instagram | Out | The final draft is saved, not posted | Not planned without an API |

**Why no trained model yet.** A model that predicts reel performance needs thousands of reels with known results. The MVP collects exactly that data: every onboarding, every peer and every posted reel adds labelled examples. Plan to train the first model at around 5,000 reels with 7-day results.

## 3. Accounts and keys checklist

Sign up for these before Claude Code starts; none of them has a long lead time.

| Service | Why CURO needs it | What to get from it | Lead time | Cost model |
| --- | --- | --- | --- | --- |
| [Apify](https://apify.com/scrapesmith/instagram-reels-scraper) | All Instagram data: profiles, reels, counts, comments, hashtag pages | API token; chosen actors for profiles, reels, comments and hashtags | Same day | Pay per result |
| Bright Data (optional backup) | Second public-data vendor if Apify actors break | API key | 1–2 days | Pay per result |
| [Anthropic Console](https://docs.claude.com/en/api/overview) | Ideas, scripts, notes, captions, explanations, Ask Curo, DNA extraction | API key | Same day | Pay per token |
| Google AI Studio (Gemini API) | Watching videos: transcript, shots, on-screen text, visual description; text embeddings | API key | Same day | Pay per token |
| Supabase | PostgreSQL database with pgvector, user login, file storage | Project URL, anon key, service-role key | Same day | Free tier, then monthly plan |
| Railway (or Render) | Hosts the backend API, the worker and Redis for the job queue | Project and deploy token | Same day | Usage-based |
| Expo (EAS) | Builds the React Native app for TestFlight and Play testing | Expo account | Same day | Free tier available |
| Apple Developer Program | iOS TestFlight builds | Developer account | 1–2 days | Annual fee |
| Google Play Console | Android test builds | Developer account | 1–2 days | One-time fee |
| Sentry | Error reporting for app and backend | DSN keys | Same day | Free tier |
| PostHog | Product analytics: which ideas are picked, drop-off per step | Project key | Same day | Free tier |
| A domain and a privacy page | App stores require a privacy policy URL | Domain, hosted page | 1 day | Small yearly fee |

No Meta developer account, Instagram app, Business Verification or App Review is needed.

**Voice input needs no service.** The app uses the phone's built-in speech recognition, which is free, fast and works offline on most devices. Gemini audio transcription is the fallback for long recordings.

## 4. Instagram data: public collection only

CURO uses no Instagram API. Every Instagram number comes from public, logged-out collection through a vendor (Apify first, Bright Data as a backup), wrapped in one `PublicDataProvider` interface so features never call a vendor directly.

**What this changes.** There is no Meta app, no tokens and no review. In exchange, CURO only ever sees public counts, and it must take its own snapshots to see how a reel grows.

### What CURO collects

| Object | Fields | Used for |
| --- | --- | --- |
| Profile | Username, bio, follower count, following count, post count, category, is private | Onboarding, baselines, follower growth |
| Reel | ID, shortcode, URL, caption, hashtags, mentions, audio name, duration, posted time, view count, like count, comment count, share count where shown, paid-partnership flag, video URL, thumbnail URL | Reel Records, metrics, DNA |
| Comment | ID, text, time, like count, reply count | Audience cards, top comment, demand themes |
| Hashtag or audio page | Top and recent reels using it | Trend momentum, hashtag candidates |

Commenter handles are read only to filter bots and spot friend tags, then dropped.

### What CURO never collects

- Anything only the account owner can see: saves, reach, impressions, watch time, skip rate, follower vs non-follower split, audience demographics, when followers are online.
- Anything from private accounts or behind a login.
- Instagram passwords or logins, ever.

The app labels its numbers "Public counts only". The backend logic doc, section 3, lists the public stand-in CURO uses for each missing number.

### Snapshot schedule

1. Creator's new reels: every 3 hours for the first 48 hours.
2. Then every 12 hours until day 7.
3. Then daily until day 30, weekly until day 90, then stop.
4. Peers' reels: daily for 14 days after posting, plus a daily check of each peer's latest 5 reels.
5. The profile's follower count is saved with every run.

Every snapshot is a paid scrape, so batch them: one run per account covers all of its reels that are due, never one run per reel.

### Data-quality rules

Public fields go missing often, so the code treats missing as unknown and never as zero.

| Situation | What the code does |
| --- | --- |
| Likes hidden | Store null, show a dash, leave likes out of rates and baselines |
| Share count not shown | Store null, show a dash, leave the reel out of share baselines |
| Comments turned off | Store null; no comment-based audience cards for that reel |
| A snapshot lower than the previous one | Keep the previous value; flag the snapshot |
| Reel deleted | Mark it deleted; keep its past snapshots in baselines |
| Account turned private or deleted | Stop collecting; hide it from peers; keep only aggregates |
| Scrape fails | Retry once, then try the backup vendor, then mark the snapshot missed |

Pin each actor's version and run contract tests on recorded responses every day, so a change in the vendor's output is caught before it reaches creators.

### Collection rules

- Logged-out, public data only; refuse private accounts.
- Collect only what a feature needs, at the schedule above.
- Drop commenter handles after analysis.
- Honour takedown and deletion requests, and let creators delete their data in settings.
- Get a legal review before launch; the backend logic doc, section 3, covers the legal background.

## 5. Public data, AI and trend APIs

The MVP calls three outside APIs: Apify for public data, Claude for language work and Gemini for watching videos and making embeddings.

### Apify (public mode and peers)

| Actor type | Input | Output CURO keeps |
| --- | --- | --- |
| Instagram profile scraper | Username | Bio, follower count, following count, post count, category, is private |
| Instagram reels scraper (with share counts enabled) | Username or reel URLs, number of reels | Reel ID, shortcode, permalink, caption, hashtags, mentions, audio name, timestamp, duration, view count, like count, comment count, share count, paid-partnership flag, video URL, thumbnail URL |
| Instagram comments scraper | Reel URL, comment limit | Comment text, timestamp, like count, reply count (handles dropped after analysis) |
| Instagram hashtag scraper | Hashtag, number of reels | Top and recent reels with the same reel fields |

Some reel actors charge extra for share counts or return them only when visible ([example actor](https://apify.com/brilliant_gum/instagram-reel-scraper-pro.md)); test two or three actors on the same 20 reels and pick the most complete.

Rules for the code:

- Call actors through Apify's REST API and wait for results, or start runs and receive a webhook when they finish.
- Wrap Apify in one `PublicDataProvider` interface so it can be swapped for another vendor without touching features.
- Pin each actor's version and validate every field, because public fields go missing (hidden likes, disabled comments).
- Download videos and thumbnails into Supabase Storage straight away, since Instagram's media links expire. Delete peers' videos once their DNA is extracted.
- Refuse private accounts and never log in.

### Claude API (language work)

Use the [Messages API](https://docs.claude.com/en/api/overview) for every writing and reasoning task in section 10.

- **Models.** `claude-sonnet-5-5` for ideas, scripts, captions, explanations and Ask Curo. `claude-haiku-4-5-20251001` for high-volume labelling such as comments and DNA fields. Check the [models page](https://docs.claude.com/en/docs/about-claude/models/overview) for current names when building.
- **Structured output.** Define a JSON schema for every task and have Claude return it through tool use, so the backend never parses free text.
- **Tool use.** Ask Curo calls CURO's own functions (search reels, score ideas, run simulation) as tools.
- **Prompt caching.** Cache the creator's evidence pack, which is the same across many calls in one Studio session.
- **Batch processing.** Run nightly comment labelling and peer DNA extraction as batch jobs, which are cheaper and don't need instant answers.

### Gemini API (video and embeddings)

- **Video understanding.** Upload the reel through the File API and ask for a JSON result: transcript with word timings, shot changes, on-screen text, a description per second, audio type and the time of the first payoff. Google samples video at about 1 frame per second, roughly 300 tokens per second of video at default settings ([Gemini docs mirror](https://hex.pm/packages/ex_llm/0.7.1/files/docs/gemini/GEMINI-DOCS-18-VIDEO-UNDERSTANDING.md)).
- **Embeddings.** Use Gemini's text-embedding model on transcript + caption + visual description. Fix one vector size (for example 768) for pgvector, and never mix embedding models in one table.

### Trend data

- **MVP: a curated festival calendar.** A JSON file in the repo with each event's name, dates for the next two years, regions, related niches and keywords. Examples: Ganesh Chaturthi, Navratri, Diwali, Karva Chauth, Holi, Eid, Christmas, wedding season.
- **Search trends: later.** Google announced an official Trends API in July 2025, but it is still an application-gated alpha, and the popular unofficial library was archived ([Scrapfly](https://scrapfly.io/blog/posts/google-trends-api-alternatives)). Apply for the alpha now; add search trends once access comes through.
- **CURO's own index.** Topic growth across all collected peer reels is computed internally and needs no outside API.

## 6. Infrastructure

The MVP is four parts you run (app, API, queue, worker) plus Supabase, and every outside service is called from the server so no key ever ships inside the app.

&#91;embedded content: CURO MVP system · 4 parts and 4 outside services\]

The app sends every request to the CURO API. Slow work goes onto the Redis queue, and the worker runs it, calls the outside services and writes results to Supabase. The app talks to Supabase directly only for login and to watch job progress live. Apify reports finished runs back to the API through a webhook.

### Stack choices

| Part | Choice | Why |
| --- | --- | --- |
| Mobile app | Expo (React Native, TypeScript) | The prototype is React; one codebase for iOS and Android; easy TestFlight builds |
| Backend API | Python with FastAPI | Same language as the data and ML work (clustering now, LightGBM later) |
| Worker and queue | Python worker with Celery or RQ, Redis on Railway | Schedules, retries and timeouts for snapshots and video processing |
| Database | Supabase PostgreSQL with pgvector | Records, embeddings and similarity search in one place |
| Login | Supabase Auth (email or phone OTP, Google, Apple) | Separate from Instagram, so public-mode users can sign up first |
| Files | Supabase Storage | Reel videos, thumbnails, uploads, with signed URLs |
| Live updates | Supabase Realtime | Job progress on onboarding and simulation screens |
| Hosting | Railway (or Render) | Runs API, worker and Redis together with simple deploys |
| Clustering | HDBSCAN in the worker | Sub-clusters without choosing the number of groups |
| Monitoring | Sentry and PostHog | Errors, and which steps creators finish or abandon |

## 7. CURO's own backend API

The app talks only to CURO's backend, never to Apify or the AI providers directly; that keeps every key on the server. All endpoints are JSON over HTTPS, under `/v1`, and require the Supabase login token.

**Two patterns for slow work.** Anything that can take more than about 5 seconds (onboarding, simulations, generation of a whole storyboard) returns `202` with a job ID. The app follows progress through Supabase Realtime on the `jobs` table. Chat and text generation stream their reply as server-sent events so words appear as they are written.

| Method and path | What it does | Screen |
| --- | --- | --- |
| `POST /v1/onboarding/username` | Starts onboarding for a public handle | Onboarding |
| `GET /v1/onboarding/status` | Progress: reels found, processed, ready | Onboarding, Home |
| `GET /v1/me` | Profile, follower count, counts, saved count | Header, Saved icon |
| `DELETE /v1/me` | Deletes the creator's account and all their data | Settings |
| `GET /v1/peers/suggestions` · `POST /v1/peers` · `DELETE /v1/peers/{id}` | Suggest, add and remove tracked peers | Onboarding, settings |
| `GET /v1/reels?limit=10` | Carousel cards: thumbnail, four public metrics, change, comparison type | Home |
| `POST /v1/reels/refresh` | Requests a new snapshot if the last is older than 3 hours | Home |
| `GET /v1/reels/{id}/insights` | Phase, phase range, velocity timeline, audience cards, top comment | Insights |
| `GET /v1/opportunities` | Top 5 with name, tag, score | Home |
| `GET /v1/opportunities/{id}` | Detail: description, score parts, peer evidence, why it fits | Opportunity pages |
| `POST` · `DELETE /v1/opportunities/{id}/save` | Bookmark or un-bookmark | Opportunity pages |
| `POST /v1/opportunities/{id}/dismiss` | Hide it and record the signal | Opportunity pages |
| `POST /v1/projects` | New Studio project, optionally from an opportunity | Open in Studio |
| `GET /v1/projects/{id}` | Full project state: step, idea, versions | Studio, Saved |
| `POST /v1/projects/{id}/ideas` | Generates 3 ideas, with optional creator input | Studio step 1 |
| `POST /v1/ideas/validate` | Scores a free-typed idea: verdict, reasons, tweaks | Studio tab chat |
| `POST /v1/projects/{id}/ideas/{ideaId}/select` | Locks the idea and moves to the script step | Studio step 1 |
| `POST /v1/projects/{id}/script` | Generates the script with notes | Studio step 2 |
| `POST /v1/projects/{id}/script/revise` | Applies a chat or voice instruction; returns the changed beats | Studio step 2 |
| `PUT /v1/projects/{id}/script` | Saves the creator's own script and adds notes | Studio step 2 |
| `POST /v1/projects/{id}/storyboard` · `/storyboard/revise` | Builds or changes frames | Studio step 3 |
| `POST /v1/projects/{id}/captions` · `/captions/revise` | Three captions and suggested hashtags | Studio step 4 |
| `PUT /v1/projects/{id}/hashtags` | Saves up to 5 hashtags; rejects a sixth | Studio step 4 |
| `POST /v1/projects/{id}/save` | Saves the final draft | Final draft |
| `POST /v1/uploads/sign` | Signed URL to upload a video to storage | Simulator |
| `POST /v1/simulations` | Starts a simulation: video, optional project, audience toggle | Simulator |
| `GET /v1/simulations/{id}` | Status or full result | Simulator |
| `POST /v1/simulations/{id}/edits/{editId}/apply` | Writes an accepted edit back to the Studio project | Simulator |
| `POST /v1/simulations/{id}/rerun` | Re-runs with a new upload | Simulator |
| `POST /v1/chat` | Ask Curo; body carries screen, project or simulation ID and message; streams the reply | All chat boxes |
| `GET /v1/saved` | Saved opportunities and drafts | Saved |
| `POST /v1/webhooks/apify` | Apify run finished | System |
| `GET /health` | Health check for hosting | System |

Claude Code should generate an OpenAPI file from these routes, and the app's API client from that file, so the two never drift.

## 8. Database tables

The database has 27 tables in four groups, all in Supabase PostgreSQL with Row Level Security, so a creator can only ever read their own rows. Peers' public reels sit in the same `reels` table as the creator's, tagged by account.

### Accounts and data

| Table | Key columns | Notes |
| --- | --- | --- |
| `creators` | `id, user_id, ig_username, niche, goal, voice_profile` | One per CURO user |
| `accounts` | `id, username, followers, is_private, last_collected_at` | Every Instagram account CURO knows, creator or peer |
| `account_snapshots` | `account_id, taken_at, followers, following, posts` | Follower growth over time |
| `peers` | `creator_id, account_id, source, confirmed` | Who each creator tracks |
| `reels` | `id, account_id, ig_media_id, shortcode, permalink, posted_at, duration_s, caption, hashtags, audio_name, is_paid_partnership, video_path, thumb_path, first_seen_at` | `first_seen_at` tells whether CURO saw the reel early or late |
| `metric_snapshots` | `reel_id, taken_at, age_hours, views, likes, comments, shares, flagged` | Index on `(reel_id, taken_at)`; null where hidden |
| `comments` | `id, reel_id, text, posted_at, like_count, reply_count, sentiment, intent, theme_id, is_bot, tags_friend` | No commenter handles stored |

### Learned data

| Table | Key columns | Notes |
| --- | --- | --- |
| `reel_dna` | `reel_id, content, production, transcript, confidence, model_version` | JSON columns follow the fixed taxonomy |
| `reel_embeddings` | `reel_id, embedding vector(768), model` | pgvector index for similarity search |
| `baselines` | `account_id, metric, age_bucket, median, p25, p75, n` | Recomputed after each new reel |
| `subclusters` | `id, account_id, label, centroid, reel_ids, lifts` | Named groups of reels |
| `comment_themes` | `id, account_id, label, share, sample_comment_ids` | Requests and questions |
| `pattern_cards` | `id, account_id, feature, value, metric, effect, n, confidence, scope` | `account_id` null means a cross-creator prior |
| `hashtag_pages` | `tag, fetched_at, top_reel_ids, recent_reel_ids, reel_count_7d` | Cached public hashtag pages, refreshed at most daily |
| `festival_calendar` | `id, name, starts_on, ends_on, regions, niches, keywords` | Seeded from the repo's JSON file |

### Product data

| Table | Key columns | Notes |
| --- | --- | --- |
| `opportunities` | `id, creator_id, name, tag, score, parts, evidence, status, window_ends_on` | Status: active, saved, dismissed, expired |
| `projects` | `id, creator_id, opportunity_id, step, status, posted_reel_id` | Anchors the whole Studio journey |
| `ideas` | `id, project_id, text, slot, score, parts, evidence_ids, source, selected` | Source: generated or creator |
| `script_versions` | `id, project_id, version, beats, instruction` | Beats carry ID, text, timing and note |
| `storyboard_versions` | `id, project_id, version, frames, feasibility` | Frames link to beat IDs |
| `captions` | `id, project_id, version, options, chosen, hashtags` | Check constraint: at most 5 hashtags |
| `simulations` | `id, creator_id, project_id, video_path, audience, status, score, predicted, result, method_version` | Stores every estimate for the accuracy record |
| `simulation_edits` | `id, simulation_id, description, feature_change, delta, effort, applied` | One row per suggested edit |

### System

| Table | Key columns | Notes |
| --- | --- | --- |
| `chat_messages` | `id, creator_id, context, role, content, tool_calls` | Context names the screen and project |
| `creator_memory` | `creator_id, key, value, source` | Visible and deletable in settings |
| `jobs` | `id, type, status, progress, payload, error` | Watched by the app through Realtime |
| `events` | `creator_id, name, props, created_at` | Signals such as idea picked or opportunity dismissed |

## 9. Background jobs and schedules

Twelve jobs run on the worker, queued in Redis; each job is safe to run twice, so a retry never duplicates data.

| Job | When it runs | What it does |
| --- | --- | --- |
| `onboard_public` | Creator submits a username | Fetches profile and latest 50 reels; queues `process_reel` for the newest 30 and comment collection |
| `snapshot_account` | On the schedule in section 4, batched per account | One scrape per account for all its reels that are due, plus the follower count |
| `process_reel` | New reel found or video uploaded | Downloads video, runs Gemini understanding, Claude DNA extraction and embedding |
| `label_comments` | Nightly as a batch, plus after each new reel | Bot filter, sentiment, intent, friend tags, theme grouping |
| `recompute_learning` | After each batch of processed reels | Baselines, sub-clusters, pattern cards |
| `collect_peers` | Weekly full refresh; daily check of each peer's latest 5 reels | Keeps peer reels and Outlier Index fresh |
| `collect_hashtags` | Daily, for hashtags linked to creators' niches and upcoming festivals | Refreshes cached hashtag pages for trends and hashtag suggestions |
| `build_opportunities` | Nightly per creator | Finds, merges, scores and explains the top 5 |
| `match_posted_reel` | When a snapshot finds a new reel | Links it to a saved project or simulation and asks the creator to confirm |
| `run_simulation` | Creator starts a simulation | Processes the upload and computes the estimate |
| `cleanup` | Daily | Deletes peer videos after DNA extraction, expires past-window opportunities, carries out deletion requests |
| `accuracy_report` | Weekly | Compares stored estimates with 7-day actuals and updates each creator's accuracy record |

## 10. AI task catalog

The MVP has 15 AI tasks; 14 call a model and one (the Simulator estimate) is plain code. Every model call returns JSON that matches a schema, and every task has a version number stored with its output so results can be traced and re-run.

| ID | Task | Model | Input | Output (key fields) | Called by |
| --- | --- | --- | --- | --- | --- |
| T1 | Watch a video | Gemini | Video file | `transcript[{t, word}], shots[{start, end}], onscreen_text[{t, text}], seconds[{t, description}], audio_type, first_payoff_s` | `process_reel`, `run_simulation` |
| T2 | Extract DNA | Claude Haiku | T1 output, caption, hashtags | `content{cluster, context, characters, core_tension}`, `production{format, hook_type, hook_text, opening_style, narrative, ending, cta_type, pov, camera, cuts_per_10s, audio, visual_style, setting}`, `confidence{…}` | `process_reel` |
| T3 | Label comments | Claude Haiku, batch | Up to 200 comments | `[{id, is_bot, sentiment, intent, theme}]` | `label_comments` |
| T4 | Name groups | Claude Haiku | Sample reels or comments of one group | `{label}` | `recompute_learning` |
| T5 | Name and explain an opportunity | Claude Sonnet | Merged evidence and score parts | `{name, description, why_it_fits}` | `build_opportunities` |
| T6 | Generate idea candidates | Claude Sonnet | Evidence pack, optional creator input | 15 × `{text, angle, format, target_behaviour, evidence_ids}` | Ideas endpoint |
| T7 | Write a script | Claude Sonnet | Idea, voice profile, beat structure, word budget | `beats[{id, text, est_seconds}]` | Script endpoints |
| T8 | Tag script notes | Claude Haiku | Beats and the creator's pattern cards | `[{beat_id, note_type, pattern_card_id}]` | Script endpoints |
| T9 | Simulator estimate | Code, no model | Draft DNA and embedding, neighbour reels, pattern cards | `score, range per metric, reasons, edit deltas` | `run_simulation` |
| T10 | Write explanations | Claude Sonnet | Computed facts only | Short plain sentences | Insights, Simulator, opportunities |
| T11 | Build storyboard | Claude Sonnet | Beats, creator's camera setups, peer visual devices | `frames[{beat_id, start, end, shot_type, instruction, onscreen_text, transition, icon_key}]` | Storyboard endpoints |
| T12 | Captions and hashtags | Claude Sonnet | Project, caption patterns, scored hashtag candidates | `captions[3]{text, job}, hashtags[5]` | Caption endpoints |
| T13 | Route a revision | Claude Haiku | Instruction and current state | `{action, targets, params}` | All revise endpoints |
| T14 | Ask Curo | Claude Sonnet with tools | Conversation, screen context | Streamed reply, tool calls | Chat endpoint |
| T15 | Propose edits | Claude Sonnet | Draft DNA, negative factors | `[{description, feature_change, effort}]` | `run_simulation` (re-scored by T9) |

### The no-new-numbers check

T5, T10, T12 and T14 write text a creator will trust. After each call, the backend extracts every number in the output and checks that it appears in the input facts. If not, it regenerates once, then falls back to a template sentence. This enforces the logic doc's honesty rules in code.

### T9: how the MVP Simulator estimates without a trained model

1. **Find neighbours.** Take the 15 reels most similar to the upload by embedding, preferring the same format. The creator's own reels count double compared with peers'.
2. **Read their lifts.** Use each neighbour's 7-day lift per metric, with peers measured against their own baselines.
3. **Estimate.** Take the weighted average of the neighbours' lifts. Adjust it by the pattern-card effects of production features where the upload differs from most neighbours, capped at ±30%.
4. **Range.** Use the weighted 10th to 90th percentile of neighbour lifts. Widen it when fewer than 8 neighbours are the creator's own.
5. **Score.** Rank the weighted mix of predicted lifts (audience-toggle weights from the logic doc) against the creator's last 50 reels.
6. **Reasons.** The strongest pattern effects present in the upload become "What's working"; the strongest ones missing or reversed become "What's holding it back".
7. **Edits.** T15 proposes changes as feature edits. Each is re-scored with steps 3–5, and the top three by gain per effort are shown.

The result screens stay the same when the trained model replaces steps 1–4 later.

## 11. Environment variables

Claude Code should commit this as `.env.example` with empty values and read every secret from the environment; real values live only in Railway, Supabase and Expo settings.

```bash
# --- Backend (Railway) ---
MOCK_MODE=false                    # true = run everything on recorded mock data
APP_ENV=development                # development | staging | production
API_BASE_URL=

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=         # backend only, never in the app
SUPABASE_JWT_SECRET=
DATABASE_URL=                      # direct Postgres connection for the worker
STORAGE_BUCKET_VIDEOS=reel-videos
STORAGE_BUCKET_THUMBS=reel-thumbs

# Queue
REDIS_URL=

# Public data (no Instagram API)
PUBLIC_DATA_PRIMARY=apify          # apify | brightdata
APIFY_TOKEN=
APIFY_PROFILE_ACTOR_ID=
APIFY_REELS_ACTOR_ID=
APIFY_COMMENTS_ACTOR_ID=
APIFY_HASHTAG_ACTOR_ID=
APIFY_WEBHOOK_SECRET=
BRIGHTDATA_API_KEY=                # optional backup vendor

# Anthropic
ANTHROPIC_API_KEY=
CLAUDE_MODEL_MAIN=claude-sonnet-5-5
CLAUDE_MODEL_FAST=claude-haiku-4-5-20251001

# Google Gemini
GEMINI_API_KEY=
GEMINI_VIDEO_MODEL=
GEMINI_EMBEDDING_MODEL=
EMBEDDING_DIM=768

# Monitoring
SENTRY_DSN_BACKEND=
POSTHOG_KEY=

# --- Mobile app (Expo, public values only) ---
EXPO_PUBLIC_API_BASE_URL=
EXPO_PUBLIC_SUPABASE_URL=
EXPO_PUBLIC_SUPABASE_ANON_KEY=
EXPO_PUBLIC_SENTRY_DSN=
EXPO_PUBLIC_POSTHOG_KEY=
```

The app gets only `EXPO_PUBLIC_` values, which are safe to ship inside the app. Everything else stays on the server.

## 12. Build order for Claude Code

Build in 10 phases, each ending with a check you can do yourself on a phone. Give Claude Code one phase per session, with the prototype, the logic doc and this doc attached.

0. **Set up the project.** One repository with `/app` (Expo React Native), `/api` (Python FastAPI), `/worker` (job runner sharing the API's code) and `/db` (SQL migrations). Add automated tests and deploys.
   - *Done when:* `/health` answers on Railway, the app opens on your phone through Expo, and all migrations run on Supabase.
1. **Port the prototype UI.** Rebuild every screen in React Native from the prototype file, with mock data. Keep the shared components (Nav, Composer, ReelThumb, Sketch), the six colours, the fonts, the springy nav animation and the four public metrics.
   - *Done when:* every screen and button works on mock data and matches the prototype side by side.
2. **Build public data collection.** The `PublicDataProvider` interface, Apify actors, username onboarding, the batched snapshot schedule and the data-quality rules from section 4.
   - *Done when:* typing a real public handle fills Home with that creator's real reels and numbers within 2 minutes, and a reel with hidden likes shows a dash, not a zero.
3. **Understand reels.** Tasks T1–T4, embeddings, baselines, sub-clusters and pattern cards.
   - *Done when:* every reel has DNA with confidence scores, and a creator with 30 reels shows at least a few pattern cards.
4. **Home and Insights on real data.** Arrows against the baseline, phase from snapshots and views ÷ followers, audience cards (T10) and top comment.
   - *Done when:* for three reels, the phase and cards match numbers you check by hand.
5. **Peers and opportunities.** Peer management, peer and hashtag collection, festival calendar, nightly opportunity builder (T5), detail pages, save and dismiss.
   - *Done when:* a real creator sees 5 opportunities whose score parts add up to the shown score.
6. **Studio.** Projects, idea generation with scoring and the diversity rule, the validate chat, script and notes (T7, T8), revisions (T13), storyboard (T11), captions (T12), the 5-hashtag rule, save draft.
   - *Done when:* the full Ganpati-style journey works for a real creator from opportunity to saved draft.
7. **Simulator v0.** Upload, T1 and T2 on the upload, the T9 estimate, edits (T15) with apply, draft comparison and the accuracy record.
   - *Done when:* a 30-second upload returns a score, range, three reasons and three edits in under 3 minutes.
8. **Ask Curo, Saved and memory.** T14 with tools, the no-new-numbers check, creator memory in settings.
   - *Done when:* answers point to real reels or comments, and the number check catches a planted made-up number.
9. **Harden and launch the beta.** Error reporting, analytics events, backup vendor switch, account deletion, privacy page, legal review.
   - *Done when:* 20 beta creators have onboarded with just their usernames.

**Three habits that keep Claude Code on track.** Record real API responses once and replay them in tests, so tests never call Apify or the AI providers. Keep a `MOCK_MODE` switch so the app can always run on mock data. Ask Claude Code to update a `DECISIONS.md` file whenever it deviates from these docs.

## 13. Open decisions and risks

With no Instagram API, the biggest risks sit in public data collection: whether it keeps working, how complete it is and what it costs. Decide the vendor and test it on real accounts before anything else.

| Decision or risk | Why it matters | Recommendation |
| --- | --- | --- |
| Public collection breaks | Instagram changes its pages, and vendor actors can stop returning fields overnight | One `PublicDataProvider` interface, a backup vendor, daily contract tests on recorded responses |
| Incomplete counts | Likes can be hidden and share counts aren't always visible | Store null, show a dash, and leave missing values out of baselines; never fill in zeros |
| No owner-only metrics | Saves, reach, watch time and demographics are never available | Say "Public counts only" in the app; rely on public stand-ins from the logic doc |
| Growth only from first sighting | Reels posted before onboarding have one final number, not a curve | Mark older reels as estimated; track every new reel from its first hours |
| Scraping cost | Every snapshot is a paid result, and snapshot frequency multiplies cost | Batch per account, follow the schedule, stop at day 90, cap peers per creator |
| Legal position | Scraping public data is lawful in some cases and less tested in others, including India | Logged-out public data only, no logins, delete on request; legal review before launch |
| AI cost per creator | Video understanding and generation add up with many reels | Haiku and batch jobs for volume, prompt caching in Studio, a monthly token budget per creator with alerts |
| Early Simulator accuracy | With few reels and public-only data, estimates will be rough | Show ranges and the accuracy record from day one; label the Simulator "beta" |
| Instagram's own Edits Assistant | Meta offers explanations from private first-party data | Lead with peer evidence, scored ideas, storyboards and tested edits that work for any public account |
| India DPDP Act duties | Phased obligations are coming into force | Clear notice and consent at sign-up, deletion on request, logs kept as required |
| Proxima Nova licence | Embedding a font inside an app usually needs a separate app licence | Buy an app licence, or ship Figtree (free) as the app font |
| Video storage | Videos are large and peer videos aren't needed after analysis | Delete peer videos after DNA extraction; keep creators' uploads for 90 days |

## 14. Sources

- [Instagram API updates, April 2026](https://developers.facebook.com/blog/post/2026/04/22/instagram-api-updates-for-partnerships-metrics-collaboration-and-engagement/) — Meta for Developers (saves are owner-only)
- [Instagram Reels Scraper](https://apify.com/scrapesmith/instagram-reels-scraper) — Apify Store
- [Instagram Reel Scraper Pro](https://apify.com/brilliant_gum/instagram-reel-scraper-pro.md) — Apify Store (share counts)
- [Claude API overview](https://docs.claude.com/en/api/overview) and [models overview](https://docs.claude.com/en/docs/about-claude/models/overview) — Anthropic
- [Gemini video understanding notes](https://hex.pm/packages/ex_llm/0.7.1/files/docs/gemini/GEMINI-DOCS-18-VIDEO-UNDERSTANDING.md) — mirror of Google's Gemini docs
- [Google Trends API alternatives](https://scrapfly.io/blog/posts/google-trends-api-alternatives) — Scrapfly
- Companion doc: CURO — Backend Logic for Every Feature
