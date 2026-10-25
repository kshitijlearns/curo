# CURO

A web app for Instagram creators: what to make next (opportunity areas and trends in your
niche), a guided Studio (idea → script → storyboard → caption) and a pre-posting Simulator
where an AI audience built from your own comments watches your reel before you post it.

Everything outside CURO (Apify, Gemini, Claude, Supabase, payments, Sentry/PostHog) sits
behind an interface with a working mock, so the whole app runs on realistic fake data until
keys arrive. See [PLAN_V2.md](PLAN_V2.md), [docs/DECISIONS.md](docs/DECISIONS.md) (v2:
D200–D211, v2.1: D212–D222, v2.2: D223–D240) and [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Run it

You need **Python 3.12** and **Node.js 20+**. Docker is optional.

```bash
./dev.ps1 setup          # once: Python venv + web packages        (make setup)
./dev.ps1 local --seed   # API + worker + scheduler on :8000, demo data loaded   (make local ARGS=--seed)
./dev.ps1 web            # in a second terminal: the web app on http://localhost:3000   (make app)
```

`local` runs the backend in one process with Postgres embedded (`.data/pgserver-dev`) and the
worker as a thread (D115). Later starts are just `./dev.ps1 local`; `./dev.ps1 local-seed`
reloads the demo and `./dev.ps1 local-time advance 36h` moves its clock. With Docker,
`./dev.ps1 dev` starts the Docker stack and then the web app.

The web app calls only `/api/v1/*`; in development Next.js forwards that to the API at
`API_ORIGIN` (default `http://127.0.0.1:8000`). Copy `web/.env.example` to `web/.env.local`
to set it, or the public Supabase values for real email sign-in.

**Deployed without a backend** (Vercel, Root Directory `web`), the web app runs in demo mode:
it plays back a recorded journey of the demo creator, so every screen can be seen (D211). Set
`API_ORIGIN` to a hosted API to switch it off. Re-record with `python tools/record_web_demo.py`
while `./dev.ps1 local --seed` runs; try it locally with `cd web && npm run dev:demo`.

If Windows blocks the script: `powershell -ExecutionPolicy Bypass -File dev.ps1 local`.

### The first run (v2.1)

Open the app with no session and it starts at **`/start`**: type an Instagram username (try a
fixture handle such as **@stylewithrhea**). Three cards explain Home, Idea Studio and the
Simulator while a live strip shows the backend reading the profile; then your first **Creator
Recap** plays as a story, ending with what type of creator you are and a share card. After it
you can save the account with an email code, or choose "Maybe later". Home then shows four
swipeable sections: What your followers think of you, your Creator Recap, Opportunity areas
and Trending for you. A new recap arrives on the 1st of every month.

### Follower Personas (v2.2)

Every creator gets **4 Follower Personas**: characters that summarise the main groups of people
commenting on their reels (k-means on comment embeddings and behaviour, profiled in code,
written by Claude, checked for numbers and sensitive attributes). Each has a dot-cluster avatar
that reacts (see **`/dev/avatars`**). They're introduced in the recap ("Meet your followers"),
get a card each at the top of Home (tap for the detail sheet and a chat), react to every Studio
idea and draft from a row above the composer (tap one for its own take; A in the idea score is
their share-weighted score), and the Simulator's 1,000 agents are drawn from them, with "How
each follower group reacted". Personas are summaries, not real people.

### Signing in and the demo data

Sign in with any email: in development there's no email service, so the 6-digit code is
shown on screen. For the demo creator with two weeks of history, sign in as
**demo@curo.local** after `--seed`. Or enter **@curo.demo** as your Instagram username on a
new email: CURO collects its (synthetic) public reels through the mock provider exactly as
it would a real account.

- **Home**: Opportunity areas (scored 10 × (0.35 fit + 0.25 audience demand + 0.25 timing +
  0.15 room left)) and **Trending for you**, a shared daily trend feed per niche ranked for
  your reels. Tap an angle to start a project from it.
- **Studio**: ideas (proven / a trend made yours / worth exploring), script, storyboard,
  caption with at most five hashtags. The Composer is Ask Curo: type or tap the mic to
  change any step in your words.
- **Simulator**: upload a recorded reel (MP4 or MOV, up to 90 seconds) or a sample take.
  1,000 AI followers watch it: you get an engagement score, predicted ranges (saves are
  always "simulated"), a skip curve, the best time to post, what's working and what to
  change with timestamps, and simulated comments — tap one to talk to that agent. Re-run
  with a new take to see the score change.
- **Settings**: your plan and credits (Free: 2 projects, 2 simulations, 10 Ask Curo
  messages a month; Pro $30: 10, 10, 100; top-ups never expire), what Curo remembers, and
  deleting your account. Admins (`ADMIN_EMAILS`) also see `/admin/costs`.

The data is entirely synthetic (`fixtures/`), and `FAKE_NOW` in `.env` pins CURO's clock to
the dataset's moment, 23 Aug 2027.

| Command | What it does |
| --- | --- |
| `./dev.ps1 local [--seed]` | the backend without Docker (optionally loading the demo) |
| `./dev.ps1 web` | the web app on :3000 |
| `./dev.ps1 test` | Python tests + web type-check and tests |
| `./dev.ps1 lint` / `format` | checks / auto-format |
| `./dev.ps1 api-types` | regenerate the web app's typed API client after changing API schemas |
| `./dev.ps1 local-time advance 6h` | move CURO's clock |
| `./dev.ps1 learning curo.demo` | print what CURO learned about an account |
| `python tools/reembed.py [--apply]` | re-embed every reel after changing the embedding model (D210) |
| `python tools/record_contracts.py …` | record real vendor and model answers for the contract tests (`docs/INTEGRATION.md`) |
| `python tools/avatar_sketch.py` | redraw the persona avatar mood sketch and the avatar test fixture |

## Layout

```
web/         Next.js web app (App Router, TypeScript); types generated from the API's OpenAPI
api/         FastAPI backend: routes, services (logic), providers, schemas, jobs, prompts
worker/      RQ worker + scheduler (share the api package)
db/          SQL migrations; db/local = Supabase shim for local Postgres only
fixtures/    deterministic demo dataset + generator
tools/       local stack, time travel, re-embedding, contract recorder, prototype tools
legacy/app/  the v1 Expo app, frozen
reference/   unpacked prototype + screenshots of every screen
docs/        the source docs, DECISIONS.md, INTEGRATION.md, DEPLOY_VERCEL.md
```

## Rules the code enforces

Public data only (no Instagram API, no Instagram login, never an Instagram password).
Missing counts are unknown, never zero. Every number is relative to the creator's own
reels. Predictions are ranges. AI text may only contain numbers from its input facts.
Simulated audience output is always labelled simulated. At most five hashtags, in the web
app, the API and the database. Every plan limit is enforced on the server. Personas never state
or imply age, gender, religion, caste, ethnicity, sexuality, health, income, politics or exact
location, and always carry "Built from your public comments. Personas are summaries, not real
people."
