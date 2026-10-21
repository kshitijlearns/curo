# Integration: switching from mocks to real services

Status: **ready (Phase 9)**. Everything outside CURO sits behind an interface with a working
mock. This page is the checklist for when the keys arrive: what to implement, which settings
to fill in, which prompts each provider sends, and which contract tests prove it works.

## How switching works

- `MOCK_MODE=true` (default) selects every mock. Each provider can be switched on its own:
  `PUBLIC_DATA_PROVIDER`, `VIDEO_PROVIDER`, `EMBEDDING_PROVIDER`, `LLM_PROVIDER`,
  `STORAGE_PROVIDER`, `MONITORING_PROVIDER`, `AUTH_PROVIDER` (see `.env.example`). Switch one
  at a time and keep the rest mocked until it passes its checks.
- Only `api/curo/config.py` and the provider factory (`api/curo/providers/__init__.py`) read
  these settings. Product logic is identical in mock and real mode.
- Each real implementation sits next to its mock as a stub that raises `NotImplementedError`
  with a numbered TODO list. The parsers that read each vendor's answers live in the same file.
  The Claude and Gemini parsers are already written and tested; Apify's and Bright Data's wait
  for the actors you pick (DECISIONS D112).
- Install the real SDKs once: `pip install -e "api[live]"` (the Anthropic SDK; Apify, Gemini
  and Supabase are called over plain HTTPS with `httpx`, already installed).

## The checklist

Do these in order; each step keeps everything after it mocked.

| # | Provider | Implement | Env vars | Prompts | Contract test | Done when |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Database + auth (Supabase) | `db/` migrations on Supabase; app sign-in with supabase-js | `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `DATABASE_URL`, `AUTH_PROVIDER=supabase`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (web/.env.local) | — | a Supabase session token opens `GET /v1/me`; two accounts can't read each other's rows | the web app signs in through Supabase (email code) and Home loads |
| 2 | `StorageProvider` → Supabase Storage | `providers/storage/supabase.py` | `SUPABASE_SERVICE_ROLE_KEY`, `STORAGE_BUCKET_VIDEOS`, `STORAGE_BUCKET_THUMBS`, `STORAGE_PROVIDER=supabase` | — | put → exists → list → get → delete; signed upload from the phone | a phone upload runs a simulation |
| 3 | `EmbeddingProvider` → Gemini | `providers/embedding/gemini.py` (`parse_embeddings` is done) | `GEMINI_API_KEY`, `GEMINI_EMBEDDING_MODEL`, `EMBEDDING_PROVIDER=gemini` | — | `record_contracts.py gemini-embed …` | every reel re-embedded; sub-clusters rebuilt |
| 4 | `VideoUnderstandingProvider` (T1) → Gemini | `providers/video/gemini.py` (`parse_response` is done) | `GEMINI_VIDEO_MODEL`, `VIDEO_PROVIDER=gemini` | `T1_watch_video.v1.md` | `record_contracts.py gemini-video <file>` | a real reel has a transcript, shots and a payoff time |
| 5 | `LLMProvider` (T2–T15) → Claude | `providers/llm/claude.py` (`parse_message`, `parse_chat_message` and the T14 request mapping are done) | `ANTHROPIC_API_KEY`, `CLAUDE_MODEL_MAIN`, `CLAUDE_MODEL_FAST`, `LLM_PROVIDER=claude` | `T2_…` to `T15_…` in `api/prompts/` | `record_contracts.py claude --all` | the checks under "LLMProvider" below pass |
| 6 | `PublicDataProvider` → Apify | `providers/public_data/apify.py` (calls and the four parsers) | `APIFY_TOKEN`, `APIFY_*_ACTOR_ID`, `APIFY_WEBHOOK_SECRET`, `PUBLIC_DATA_PROVIDER=apify` | — | `record_contracts.py apify {profile,reels,comments,hashtag} …` | a real public handle fills Home within 2 minutes; hidden likes show a dash |
| 7 | Backup vendor → Bright Data | `providers/public_data/brightdata.py` | `BRIGHTDATA_API_KEY`, `PUBLIC_DATA_PRIMARY` | — | same four recordings under `public_data/brightdata/` | with `PUBLIC_DATA_PRIMARY=brightdata`, onboarding works |
| 8 | Monitoring → Sentry + PostHog | `providers/monitoring/live.py`; the app's SDKs | `SENTRY_DSN_BACKEND`, `POSTHOG_KEY`, `MONITORING_PROVIDER=live` | — | a forced error reaches Sentry; `simulation_done` reaches PostHog | errors and events arrive with ids only |
| 9 | Job progress → Supabase Realtime | `app/src/api/jobs.ts` (`waitForJob`) | as step 1 | — | the app sees a job finish without polling | onboarding and simulations update live |
| 10 | Deploy → Railway + EAS | `deploy/` | everything above, `MOCK_MODE=false`, `APP_ENV=staging` | — | `/health` answers on Railway | the phone build talks to Railway |

Then clear `FAKE_NOW` (real time) and finish the launch list at the end of this page.

## Contract tests

MVP doc §4: "Pin each actor's version and run contract tests on recorded responses every
day, so a change in the vendor's output is caught before it reaches creators."

- **Record** with `python tools/record_contracts.py …` (examples in its header). Recordings land
  in `api/tests/contracts/<kind>/<name>.json`: the request (no secrets), the source (model,
  actor, build) and the raw response.
- **Replay** with `python tools/record_contracts.py check` (or `pytest tests/test_contracts.py`,
  part of the normal suite). Each recording goes through the real provider's parser
  (`curo/providers/contracts.py`), then CURO's rules: the task's schema, hidden counts as None,
  768-long normalised vectors, one vector per text.
- **Daily:** `.github/workflows/contracts.yml` records fresh answers from your test account and
  replays them every morning, once the repository has the secrets it names. A failure means a
  vendor changed its output: fix the parser before creators see it.
- **Privacy:** record only your own test account. The recorder replaces every other handle with
  a placeholder and masks @mentions before writing; read a new file before committing it.
- **Inputs for Claude:** set `CAPTURE_TASK_INPUTS=.data/task-inputs`, run the demo once
  (`./dev.ps1 local --seed`, open a Studio draft and a simulation, ask Curo something) and
  every task's first five inputs are saved there. `record_contracts.py claude --all` sends one
  per task to the real model.

---

## 1 · Database and sign-in on Supabase

1. Create the project; note the URL, anon key, service-role key and JWT secret.
2. `DATABASE_URL=<direct connection> python -m curo.db.migrate --no-shim` (never apply
   `db/local/`, the local stand-in for what Supabase provides).
3. Check that the `postgres` role can `SET ROLE authenticated` (Supabase grants this).
4. Sign-in: the API already verifies Supabase-format tokens (HS256, `aud=authenticated`,
   `SUPABASE_JWT_SECRET`), so set `AUTH_PROVIDER=supabase` and the local code routes
   (`/v1/auth/otp`, `/v1/auth/verify`) disappear. In the app, replace the two calls in
   `app/src/app/login.tsx` (`useRequestCode`, `useVerifyCode`) with supabase-js
   `signInWithOtp({ email })` and `verifyOtp({ email, token, type: 'email' })`, and store the
   session's `access_token` through `useSession().signIn` as now. Configure the email template
   to send the 6-digit code.
5. Check: sign in on the phone; `GET /v1/me` answers; a second account sees none of the first
   one's rows (RLS is tested locally with two creators in `tests/`).

## 2 · StorageProvider → Supabase Storage

- Contract (`providers/storage/base.py`): `put / get / delete / exists / list` by bucket and
  path, and `signed_upload(bucket, path, content_type) -> SignedUpload{url, method, headers,
  expires_at}`. Videos go to `STORAGE_BUCKET_VIDEOS`, covers to `STORAGE_BUCKET_THUMBS`, under
  `<account_id>/<shortcode>`; uploads under `uploads/<creator_id>/`. `list(prefix)` returns
  each file's `created_at`, which the daily cleanup uses (D107).
- Local: `LOCAL_STORAGE_DIR` (default `.data/storage`). Its signed upload URL is a path on the
  API, `PUT /v1/uploads/local/{token}`: an HMAC-signed token naming one path, valid 15 minutes
  (D88).
- Switch: create both buckets as private, implement `providers/storage/supabase.py` (its TODO
  list), then `STORAGE_PROVIDER=supabase`. `signed_upload` calls
  `POST /storage/v1/object/upload/sign/{bucket}/{path}` and returns the absolute upload URL with
  its token, so the app sends the file straight to Supabase. Keep `accept_upload`
  unimplemented there.
- Check: sign, upload a short MP4 from the phone, then `POST /v1/simulations` with its path.
  Run `cleanup` and see a 90-day-old upload go.

## 3 · EmbeddingProvider → Gemini embeddings

- Contract: `embed(texts) -> list[768-float, L2-normalised]`; `model` names the exact model. The
  embedded text is caption + transcript + on-screen text + the per-second descriptions
  (`services/dna.embedding_text`).
- Mock: feature hashing (D9), `mock-hash-768-v1`.
- Switch: implement `providers/embedding/gemini.py` (`batchEmbedContents` with
  `outputDimensionality=768`; read the answer with `parse_embeddings`), set
  `GEMINI_EMBEDDING_MODEL`, then `EMBEDDING_PROVIDER=gemini`. **Re-embed every reel** (re-run
  `process_reel` with `force`): vectors from different models must never be compared, and
  sub-clusters are rebuilt on the next learning run.
- Contract test: `python tools/record_contracts.py gemini-embed "One kurta, five dupattas"
  "3 mistakes ruining your aesthetic reel"`.

## 4 · VideoUnderstandingProvider (T1) → Gemini

- Contract: `understand(T1Input{bucket, path, duration_s}) -> T1Output`: transcript with word
  timings (original language and script), shots, on-screen text, one description per second,
  audio type, time of the first payoff. The provider reads the file from storage itself.
- Mock: `providers/video/mock.py` returns the fixture's T1 for files the mock vendor
  downloaded and for the demo's sample recordings, and a deliberately thin description for
  anything else. A real provider offers no sample recordings, so the app shows no sample
  buttons.
- Switch: implement `providers/video/gemini.py` (TODO list: File API upload, wait for ACTIVE,
  generateContent with `responseMimeType: application/json` and the T1 schema, prompt
  `T1_watch_video.v1.md`, read the answer with `parse_response`, delete the file), set
  `GEMINI_API_KEY`, `GEMINI_VIDEO_MODEL`, then `VIDEO_PROVIDER=gemini`. The recorder sends the
  schema as `responseJsonSchema`; if the model you pick only takes `responseSchema` (an OpenAPI
  subset), convert `T1Output.model_json_schema()` there and in the recorder.
- Contract test: `python tools/record_contracts.py gemini-video path/to/a-reel.mp4` with a few
  of your own reels (talking, voiceover, music only). Budget: about 300 tokens per second.

## 5 · LLMProvider → Claude (T2–T8, T10–T22)

**The tasks**

| Task | Model | Used for |
| --- | --- | --- |
| T2 extract DNA | fast | Reel DNA |
| T3 label comments | fast | Comment labels; Message Batches for the nightly run |
| T4 name a group | fast | Sub-cluster and theme names |
| T5 name an opportunity | main | Name, description and "why it fits" from computed facts |
| T6 write idea candidates | main | About 15 per round from the evidence pack |
| T7 write a script | main | The words, to a plan CURO computes |
| T8 tag script notes | fast | Which lines carry a note |
| T10 write an explanation | main | Insights' audience cards |
| T11 build a storyboard | main | One frame per beat |
| T12 captions and hashtags | main | Three captions and hashtag picks |
| T13 route a revision | fast | Sorts a Studio request into an action |
| T14 Ask Curo | main, tools, streamed | Every chat box, from CURO's tools on the creator's records |
| T15 propose edits | main | Simulator edits as DNA feature changes |

"main" is `CLAUDE_MODEL_MAIN` (`claude-sonnet-5-5`), "fast" is `CLAUDE_MODEL_FAST`. Which Haiku
to use is open (D114): compare `claude-haiku-4-5-20251001` with `claude-haiku-5-5` on recorded
T2/T3/T4/T8/T13 answers before choosing.

**How to call it** (TODO list in `providers/llm/claude.py`; D113):
- Structured output, not forced tool use: `client.messages.parse(model=…, max_tokens=16000,
  system=<the task's prompt>, messages=[{"role": "user", "content": <input JSON>}],
  output_format=<the task's output model>)`. `claude-sonnet-5-5` answers a forced
  `tool_choice` with a 400. Read the answer with `parse_message` (raises on a refusal, a
  cut-off answer or a schema mismatch).
- No `temperature` (removed from the 1.x SDK). Set `output_config={"effort": …}` per task:
  "low" for the fast labelling tasks, "medium" for the Studio's writing; tune on recordings.
- T14 is a tool loop: `client.messages.stream` with `tools=to_claude_tools(data)`,
  `system=chat_system(data, prompt)`, `messages=to_claude_messages(data)`, tool_choice auto.
  Mind preserved thinking when sending tool results back: replay each assistant turn's content
  blocks exactly as returned, or send `thinking={"type": "between_tools"}`.
- Prompt caching on the system prompt and the creator's evidence pack (Studio); Message
  Batches for the nightly T3 labelling and the Simulator's T19 agent batches (send the
  timeline as a cached prefix: every batch of a run shares it).

**What the backend does around them** (already built, unchanged by the switch)
- Confidence below 0.6 becomes "unknown" in the backend (`services/dna.apply_confidence`).
- T5, T10, T12, T14 and T15's words go through the no-new-numbers check
  (`services/validator.py`; streamed per sentence for T14): a new number means one retry, then
  the template.
- T6 candidates citing no evidence id are dropped. T7's beats outside a revision's targets are
  kept word for word by code. T8's notes are kept only when a pattern card backs them. T11's
  "easier" is enforced in code. T15's feature changes are kept only for taxonomy values, and
  every edit is re-scored by T9 and shown only if it raises a score.
- T14 runs in a loop CURO controls (`services/assistant/loop.py`): the intent is decided in
  code first and decides which tools the model may call; CURO runs the tools under the
  creator's RLS session; every sentence is checked before it is sent.

**Checks after switching**
- **T3:** check a sample of labels on real Hinglish comments by hand before trusting themes.
- **T5:** check a night's names by hand.
- **T6:** in `events`, a high `without_evidence` count in `ideas_generated` means the prompt
  isn't citing ids.
- **T7:** compare a few scripts' real length with the creator's length band.
- **T12:** frequent template captions mean numbers are slipping in.
- **T14:** ask each screen a few questions. `chat_check_failed` events show how often a reply is
  held back; `chat_messages.checked = 'template'` marks replies that fell back. Ask "what if"
  on a simulation and check the tool call's `feature_change`.
- **T15:** run the Simulator on a few real recordings; each edit should be something the
  creator can do with the video they have, matching its effort.

**Speed.** Studio tasks, simulations and Simulator edits run on the `studio` queue, which the
worker serves first (D68). Expect about 10–30 seconds for ideas and 5–15 seconds per other
step with real models.

## 6–7 · PublicDataProvider → Apify, then Bright Data

**Contract** (`providers/public_data/base.py`). Every implementation:
- is logged out and public only; raises `PrivateAccount` for a private profile and
  `AccountNotFound` for a missing one (both final, never retried);
- returns `None` for any count that isn't public (hidden likes, no share count, comments off)
  and sets `likes_hidden` / `comments_disabled` where the vendor says so. Never 0;
- `get_reels(username, limit)`: latest reels, newest first, with current counts;
- `get_reels_by_shortcodes(username, shortcodes)`: **one** batched run for all due reels of an
  account; reels that are gone are simply absent (the job marks them deleted);
- `get_comments(permalink, limit=200)`: text, likes, replies, time; the author handle is read
  only to detect the creator and friend tags and is never stored;
- `get_hashtag_page(tag, limit)`: post count, top reels, and up to `limit` of the most recent
  reels, newest first, each with its owner's handle and posting time. The momentum index (D61)
  needs the recent list complete back to its oldest reel; check this when choosing the actor.
  CURO asks for 300 recent reels once a day per watched tag;
- raises `TransientError` for timeouts, rate limits and failed runs.

**Cost shape (v2, D204).** Per creator: a profile and the latest 50 reels at onboarding
(comments on the newest 30, up to `COMMENT_LIMIT`); 18 snapshots per reel over 30 days; a
new-reel check every 12 h (the latest 3); comment re-reads at about 24 h and 7 days, newer
comments only. Paused after `INACTIVE_PAUSE_DAYS`. Hashtag pages are read once a day per
niche for the shared trend feed, never per creator. No peers.

**Switching**
1. Choose and pin actors (profile, reels with share counts, comments, hashtag). Run two or
   three reel actors on the same 20 public reels of your own test account and keep the most
   complete:
   `python tools/record_contracts.py apify reels --account <you> --input '{…}' --build <tag>`.
2. Write `parse_profile`, `parse_reels`, `parse_comments`, `parse_hashtag_page` in `apify.py`
   against those recordings, then `python tools/record_contracts.py check`.
3. Implement the calls (the file's TODO list): `run-sync-get-dataset-items` for small runs, or
   start a run with a webhook to `/v1/webhooks/apify` for large ones (finish the webhook's TODO
   to resume the waiting job).
4. Fill `APIFY_TOKEN`, `APIFY_*_ACTOR_ID`, `APIFY_WEBHOOK_SECRET`; set
   `PUBLIC_DATA_PROVIDER=apify` (everything else can stay mocked), clear `FAKE_NOW`, onboard
   your test account, and check `/health` and the job rows.
5. Bright Data the same way, as the backup (`FailoverProvider`: retry once, then the backup,
   then the snapshot is marked missed). Test the switch with `PUBLIC_DATA_PRIMARY=brightdata`.
6. Never commit recorded data from real accounts other than your own test account.

## 8 · Monitoring → Sentry + PostHog

- Contract (`providers/monitoring/base.py`): `capture_exception(exc, context)` with the route or
  job only, `capture_event(name, props, creator_id)` with the creator's id only (D110).
- Switch: implement `providers/monitoring/live.py` (its TODO list: `sentry-sdk` and `posthog`),
  set the keys, then `MONITORING_PROVIDER=live`. In the web app, add `@sentry/nextjs` and
  `posthog-js` with public (`NEXT_PUBLIC_`) keys only.
- Check: a forced error shows in Sentry with its route and no request body; product events
  (`ideas_generated`, `simulation_done`, `match_confirmed`, `account_deleted` …) reach PostHog
  without names, captions or comments.

## 9 · Job progress → Supabase Realtime

The web app follows slow jobs with `waitForJob` (`web/src/lib/api.ts`), which polls
`GET /v1/jobs/{id}` (D2). With Supabase, subscribe to the job's row in `public.jobs` (RLS lets a
creator read their own jobs) and resolve on `succeeded` / `failed`; callers don't change.

## 10 · Deploy

`deploy/README.md`: three Railway services from one image (API with migrations, worker,
scheduler with exactly one replica) plus Railway's Redis, all with the same environment
(`.env.example`, `MOCK_MODE=false`); the web app deploys anywhere Next.js runs, with
`API_ORIGIN` pointing at the API. Vercel is planned but not built yet: `docs/DEPLOY_VERCEL.md`
(D200).

## 11 · Payments → Razorpay (or Stripe)

- Contract (`providers/payments/base.py`): `create_checkout(creator, item)` for `pro` or a
  top-up (`topup_project`, `topup_simulation`, `topup_chat`) returns `completed` (grant now) or
  `pending` with a `url` to pay at; `handle_webhook(body, headers)` returns what was paid;
  `cancel(creator, ref)`. Granting goes through the credit ledger in `routes/billing.py` (D208).
- `providers/payments/razorpay.py` is a stub that raises `NotImplementedError` (the API answers
  501). To build it: a Razorpay subscription plan for Pro and an order per top-up; verify the
  webhook signature with the webhook secret (add `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`,
  `RAZORPAY_WEBHOOK_SECRET` to settings and `.env.example`); map `subscription.charged` and
  `payment.captured` to `Paid`; point Razorpay's webhook at
  `POST /v1/billing/webhook/razorpay`. Then `PAYMENT_PROVIDER=razorpay`.
- A Stripe provider follows the same interface (Checkout Sessions + `checkout.session.completed`).
- Check: buy Pro and each top-up in test mode; the balances on Settings move; a replayed
  webhook doesn't grant twice (the ledger's `ref_id`).

## Before launch (MVP doc Phase 9)

- [ ] Every provider above switched and its checks passed; contract recordings committed; the
      daily contract workflow green.
- [ ] `FAKE_NOW` empty; `APP_ENV=production`; a real `SUPABASE_JWT_SECRET` (the API refuses the
      development one in production).
- [ ] Backup vendor tested with `PUBLIC_DATA_PRIMARY=brightdata`.
- [ ] Account deletion tested on staging: Settings → Delete account, then the account's rows and
      files are gone and its handle can't be tracked (D106).
- [ ] Privacy page hosted and linked from the store listings; legal review done (D116).
- [ ] 20 beta creators onboarded with just their usernames.
