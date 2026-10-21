# Build CURO — prompt for Claude Code

You are building **CURO**, a mobile app for Instagram creators. It turns a creator's public Instagram data into insights, content opportunities, a guided content studio (idea → script → storyboard → caption) and a pre-posting simulator.

Build the **whole product now, except the live connections to outside APIs**. Every outside service sits behind an interface with a working mock, so the app runs end to end on realistic fake data. I will collect the API keys in the meantime; later we will only add the real implementations behind those interfaces, run contract tests, and switch mock mode off.

---

## 1. The three attached files and how to use them

| File | What it is | Treat it as |
| --- | --- | --- |
| `CURO_prototype.html` | Interactive prototype of every screen, with mock data and interactions | **Source of truth for UI, layout, copy, interactions and animations** |
| `CURO — Backend Logic for Every Feature.md` | How every feature works: data, formulas, rules, worked examples | **Source of truth for product behaviour and logic** |
| `CURO MVP — APIs, Services and Build Plan.md` | MVP scope, stack, endpoints, database tables, jobs, AI tasks, env vars, build phases | **Source of truth for architecture and the build plan** |

If two files disagree:
- The MVP doc wins on scope and architecture.
- The logic doc wins on behaviour and formulas.
- The prototype wins on look and copy.

If you're unsure, write the question in `DECISIONS.md`, make the most reasonable choice, and keep going.

**Diagrams.** The exported docs replace their diagrams with placeholders like `[embedded content: …]`. The surrounding text describes the same thing, so rely on the text.

### Reading the prototype file

`CURO_prototype.html` is a self-contained bundle, not plain HTML.

1. Parse `<script type="__bundler/manifest">`. It is JSON mapping IDs to `{mime, compressed, data}`, where `data` is base64 and gzip-compressed when `compressed` is true.
2. Parse `<script type="__bundler/template">`. It is a JSON string of the page shell.
3. The main screen (the largest HTML entry in the manifest) is **itself a nested bundle**. Decode it the same way.
4. Its template contains:
   - the screen markup: an `<x-dc>` element using `sc-if` / `sc-for` / `{{value}}` bindings
   - a `<script type="text/x-dc">` holding all mock data (`REELS`, `OPPS`, scripts, storyboard, simulator data) and the interaction logic
5. Write a small script in `/tools/extract_prototype.py` that unpacks everything into `/reference/prototype/`.
6. Also open the HTML in a browser and screenshot every screen into `/reference/screens/`. Rebuild screens against those screenshots.

Keep these from the prototype exactly:
- **Colours:** only six, with no gradients anywhere: `#5B73F2`, `#C3BFF2`, `#F2D4E2`, `#FFFFFF`, `#E4E4EC`, `#242424`.
- **Font:** Proxima Nova Light / Regular / Semibold. Use **Figtree** as the shipped font for now, because Proxima needs an app licence. Make the font a single theme setting.
- **Layout:** the lavender fixed "Curo" header with the Saved icon, and the white rounded sheet that scrolls under it.
- **Animation:** the springy raised-circle bottom-nav animation, reused across the app.
- **Shared components:** Nav, Composer (chat + voice), ReelThumb, Sketch.
- **Metrics:** exactly **four public metrics**: views, likes, comments and shares, plus the "Public counts only" note.

---

## 2. Non-negotiable product rules

1. **Public data only. No Instagram API, no Instagram login, ever.**
   - CURO never shows or estimates saves, reach, impressions, watch time, skip rate, follower/non-follower split, demographics or online times.
   - Where the prototype or docs need one of these, use the public stand-in from the logic doc, section 3.
2. **Missing means unknown, never zero.** Hidden likes, missing share counts and disabled comments are stored as `null`, shown as a dash, and left out of rates and baselines.
3. **Every number is relative to the creator's own baseline**, using lift at the same reel age (logic doc, section 4).
4. **Honesty rules** (logic doc, section 17):
   - Predictions are ranges labelled "estimate based on your history".
   - Script notes say "associated with", never "will".
   - Percentages are shares of a scoring formula, and the screen says so.
5. **No-new-numbers check.** Any AI-written text shown to the creator may only contain numbers that exist in the facts passed in (MVP doc, section 10). Build the validator and use it everywhere.
6. **Context is preserved.** Opportunity → idea → script → storyboard → caption → simulation all hang off one project ID.
7. **Exactly 5 hashtags maximum.** Enforce it in the UI, API and database.
8. Don't invent features that aren't in the three files.

---

## 3. What to build now vs later

### Build now, fully working
- The React Native app (Expo, TypeScript) with every screen from the prototype, wired to the real backend.
- The FastAPI backend with every endpoint in MVP doc section 7, except that nothing calls an outside API yet.
- The full database schema (MVP doc section 8) as SQL migrations, with Row Level Security.
- The worker with all 12 jobs (MVP doc section 9) and the snapshot scheduler (MVP doc section 4).
- **All real logic, implemented properly and unit-tested.** None of this is mocked:
  - lifts, baselines and the arrow calculation
  - the phase rules and the views ÷ followers signal
  - audience-card selection
  - pattern cards with shrinkage
  - sub-clustering
  - opportunity candidate generation, merging, scoring and explanation assembly
  - idea scoring and the diversity rule with the three slots
  - the script word budget and note filtering by pattern cards
  - storyboard timing and feasibility
  - hashtag scoring and the five-tag mix
  - the Simulator T9 nearest-neighbour estimate, score percentile, ranges, reasons, edit re-scoring and draft comparison
  - best time to post
  - the accuracy record
  - the no-new-numbers validator
  - data-quality rules
  - account deletion
- The Ask Curo assistant loop: intent routing, tool calls on CURO's own data, streaming, project memory and creator memory. The model behind it is mocked; the tools are real.

### Build later, when I add keys (interfaces + mocks only for now)

| Interface | Real implementation later | Mock now |
| --- | --- | --- |
| `PublicDataProvider` | Apify (primary), Bright Data (backup) | Reads a deterministic fixture dataset (section 4) |
| `VideoUnderstandingProvider` (task T1) | Gemini | Returns a schema-valid transcript, shots, on-screen text and per-second descriptions from fixture files; for uploads, generates plausible output from the file name and duration |
| `EmbeddingProvider` | Gemini embeddings | A real local embedding (e.g. TF-IDF + SVD to 768 dims, or a small local sentence model) so similarity, clustering and nearest neighbours behave meaningfully |
| `LLMProvider` (tasks T2–T8, T10–T15) | Claude (`claude-sonnet-5-5`, `claude-haiku-4-5-20251001`) | Deterministic template-based generators that return **schema-valid JSON** for each task, built from the evidence passed in, so the whole pipeline runs |
| `StorageProvider` | Supabase Storage | Local filesystem |
| Monitoring (Sentry, PostHog) | Real SDKs | No-op adapters |

Rules for these interfaces:
- Every task has a typed input and output schema (Pydantic on the backend, generated TS types in the app). Mocks and real implementations must satisfy the same schema.
- One setting, `MOCK_MODE=true`, selects all mocks. Per-provider overrides are also allowed, e.g. `PUBLIC_DATA_PROVIDER=mock|apify|brightdata`.
- Put each real implementation in place as a stub file that raises `NotImplementedError` with a clear TODO, so the plug-in points are obvious.
- Prompts for every Claude/Gemini task go in `/api/prompts/` as versioned files now, even though the mocks don't use them, so the real implementation is ready.

### Local infrastructure (no cloud accounts needed yet)
- **Database, auth and storage:** Supabase via the local Supabase CLI / Docker (Postgres + pgvector, Auth, Storage, Realtime). If that's a problem, use plain Postgres + pgvector in Docker with a simple local auth stub behind the same interface.
- **Queue:** Redis in Docker.
- **One command starts everything:** `make dev` (or `docker compose up` plus `expo start`).
- Leave deployment (Railway, EAS builds) for later. Write the config files, but don't depend on them.

---

## 4. The fixture dataset (what the mocks serve)

Generate a deterministic, realistic dataset in `/fixtures/`, plus a generator script, consistent with the prototype's mock data.

- **The demo creator:** a fashion/styling creator in Mumbai with about 48k followers. Their 50 reels include the prototype's reels ("3 mistakes ruining your aesthetic reel", "Get ready with me: Navratri edition", "One kurta, five dupattas", "Thrift haul under ₹2,000") and others across 4–5 sub-clusters (festive styling, reel-making tips, GRWM, hauls, one-item-many-looks).
- **Peers:** 10 peer accounts, using the handles from the prototype, e.g. @theoutfitdiaries, @stylewithrhea, @mumbaiwardrobe, each with 30 reels. Some recent Ganpati outfit reels should have an Outlier Index ≥ 2, so the "Ganpati dress ideas" opportunity emerges naturally from the real scoring logic.
- **Reel fields:** caption, hashtags, audio, duration, posted time, and **snapshot histories** that follow realistic growth curves. Include:
  - some reels with hidden likes
  - some with missing share counts
  - one with comments off
  - a few seen only late (one snapshot)
- **Comments:** in English, Hindi and Hinglish. Include "that's me" comments, questions, requests ("part 2", "where is it from", "budget version"), friend tags, a few negative ones and some spam/bot comments.
- **Video assets:** fixture T1 outputs per reel, plus a couple of tiny sample video files for the Simulator upload flow.
- **Hashtag pages:** pages for the festival hashtags.
- **Festival calendar:** a JSON file covering the next two years, including Ganesh Chaturthi.
- **A clock:** a "time travel" utility (`FAKE_NOW`) so snapshots, phases and the scheduler can be demonstrated, e.g. setting today 12 days before Ganesh Chaturthi.

The point is that the real logic produces the prototype's outcomes from this data: Ganpati scores about 8/10, and the three ideas come out as Proven / Adapted / Explore. Don't hard-code results.

---

## 5. Repository layout

```
/app        Expo React Native (TypeScript), screens + shared components + theme
/api        FastAPI app: routes, services (logic), providers (interfaces, mocks, stubs), prompts, schemas
/worker     Job runner and scheduler, sharing /api code
/db         SQL migrations, RLS policies, seed loader
/fixtures   Generated demo dataset + generator script
/tools      extract_prototype.py, screenshot script, contract-test recorder
/reference  Unpacked prototype + screenshots (read-only reference)
/docs       Copies of the two attached docs, DECISIONS.md, INTEGRATION.md
```

---

## 6. Build order

Work in phases. **After each phase, stop and give me:**
- a short report: what was built, what's mocked, any decisions
- the exact steps to check it on my machine and phone

Then continue to the next phase when I say so.

0. **Setup.**
   - Monorepo, Docker services, migrations, `make dev`, lint/format, test runners, CI config.
   - `.env.example` from MVP doc section 11, with `MOCK_MODE=true` as default.
   - Unpack the prototype and take the screenshots.
   - *Check:* `make dev` brings up DB, Redis, API (`/health` OK), worker and the Expo app on my phone.
1. **UI port.**
   - Rebuild every prototype screen in React Native with local mock data: Home, Insights, swipeable Opportunity pages, Saved, all Studio steps, Simulator, Ask Curo.
   - Include the header, nav animation, composer with voice (on-device speech recognition) and the four metrics.
   - *Check:* side-by-side with `/reference/screens/`, every screen and button behaves like the prototype.
2. **Data layer + public collection (mocked).**
   - The full schema and RLS.
   - The `PublicDataProvider` interface with mock and stub implementations.
   - Username onboarding, the batched snapshot scheduler, data-quality rules and follower snapshots.
   - Load the fixture dataset through the same code path a real scrape would use.
   - *Check:* entering the demo handle fills Home from the database; a hidden-likes reel shows a dash.
3. **Understanding pipeline (mocked AI, real logic).**
   - T1–T4 through the providers.
   - Embeddings, baselines, sub-clusters, pattern cards with shrinkage, comment labelling and themes.
   - *Check:* every reel has DNA with confidence scores; the demo creator shows sensible pattern cards.
4. **Home + Insights on real logic.**
   - Arrows vs baseline/simulation, phases, audience cards, top comment, "updated X hours ago".
   - *Check:* three reels match hand-calculated values. Include these calculations in the report.
5. **Peers + opportunities.**
   - Peer management, peer and hashtag collection, the nightly opportunity builder, detail pages, save/dismiss.
   - *Check:* "Ganpati dress ideas" appears with score parts that add up; swiping between opportunity pages works.
6. **Studio.**
   - Projects, the 15-candidate idea contest with scoring and the diversity rule, the "Why this idea" shares, the validate chat, script and notes, revisions that touch only the targeted beats, storyboard with feasibility, captions, the 5-hashtag rule, save draft.
   - *Check:* the full Ganpati journey works from Home to a saved draft, and appears on the Saved page.
7. **Simulator v0.**
   - Upload, T1/T2 on the upload, the T9 estimate (score, ranges, reasons, edits re-scored), Edit & re-run writing back to Studio, draft comparison, audience toggle, best time, the accuracy record.
   - *Check:* a sample upload returns a full result and a re-run shows the score change.
8. **Ask Curo + memory.**
   - Intent routing, tool calls, streaming, project and creator memory (visible and deletable in settings), the no-new-numbers check.
   - *Check:* answers cite real records; a planted made-up number is caught.
9. **Hardening + integration readiness.**
   - Tests across logic and endpoints, error states, empty states, account deletion.
   - Write `INTEGRATION.md`: every provider stub, its env vars, the prompts it uses, and the contract tests to run once keys exist.
   - Add a script that records real API responses into fixtures.
   - *Check:* the full test suite passes, and `INTEGRATION.md` lists exactly what to do when keys arrive.

---

## 7. Working rules

- **Read all three files fully before writing code.** Then write `PLAN.md` covering screens, modules, schema, provider interfaces, task schemas and the phase plan, and start Phase 0.
- **Test the logic properly.** Unit-test every formula against the worked examples in the logic doc:
  - the ↗32% arrow example
  - Ganpati = 0.82 → 8/10
  - idea scores 0.80 / 0.71 / 0.60, and the diversity-rule numbers 0.27 vs 0.34
  - shrinkage at n = 10 and n = 40
- **Keep secrets and data clean.** No secrets in code. No real Instagram data in the repo.
- **Keep the mocks honest.** Mocks must exercise the same code paths as real providers. Never branch the business logic on `MOCK_MODE`.
- **Log deviations.** Record every deviation from the docs in `DECISIONS.md`, with the reason.
- **Keep it simple.** Prefer simple, readable code over clever abstractions. This is an MVP that will grow.
- **Ask about destructive or ambiguous choices.** When something is genuinely blocking, ask me one clear question rather than guessing.

Start now: read the three files, write `PLAN.md`, then do Phase 0.
