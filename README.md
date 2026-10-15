# CURO

A mobile app for Instagram creators: insights from public data, content opportunities,
a guided Studio (idea → script → storyboard → caption) and a pre-posting Simulator.

Everything outside CURO (Apify, Gemini, Claude, Supabase Storage, Sentry/PostHog) sits behind
an interface with a working mock, so the whole app runs on realistic fake data until keys
arrive. See [PLAN.md](PLAN.md), [docs/DECISIONS.md](docs/DECISIONS.md) and
[docs/INTEGRATION.md](docs/INTEGRATION.md).

## Run it

You need **Docker Desktop**, **Python 3.12**, **Node.js 20+** and the **Expo Go** app on your phone.

```bash
make setup     # once: Python venv + app packages     (Windows: ./dev.ps1 setup)
make dev       # Docker stack + Expo                  (Windows: ./dev.ps1 dev)
```

`make dev` starts Postgres + pgvector, Redis, the API, the worker and the scheduler, waits
until `http://localhost:8000/health` is OK, then starts Expo. Scan the QR code with Expo Go
(Android) or the Camera app (iOS). The phone must be on the same Wi-Fi as your computer.

If Windows blocks the script: `powershell -ExecutionPolicy Bypass -File dev.ps1 dev`.

### Without Docker

No Docker Desktop? Run the same backend in one process, with Postgres embedded and the
worker as a background thread (DECISIONS D115):

```bash
./dev.ps1 local --seed   # first time: loads the demo, then serves on :8000   (make local ARGS=--seed)
./dev.ps1 app            # in a second terminal: Expo                       (make app)
```

Later starts are just `./dev.ps1 local`. `./dev.ps1 local-seed` reloads the demo while it
runs, and `./dev.ps1 local-time advance 36h` moves its clock. Data is kept in
`.data/pgserver-dev`.

### Signing in and the demo data

Sign in with any email: in development there's no email service, so the 6-digit code is
filled in for you. Then enter **@curo.demo** as your Instagram username: CURO collects its
(synthetic) public reels through the mock provider, exactly as it would a real account, and
then suggests creators to track (peers), which you confirm in the last onboarding step or
later in Settings.

For the demo creator with two weeks of history, run `make seed` (`./dev.ps1 seed`) once
and sign in as **demo@curo.local**. It tracks 10 peers, and Home shows the opportunities
built from them. "Open in Studio" on any of them runs the Studio (ideas, script,
storyboard, caption) on your data, and saved drafts appear under Saved. In the Simulator,
upload a recorded reel (MP4 or MOV, up to 90 seconds) or use one of the two sample takes:
the first take scores lower, its edits are written back to your Studio draft, and the
re-recorded take shows the score change. Every chat box is Ask Curo: ask why a line is in
your script, which reels did best, or "what if I end with a send prompt?" on a simulation.
Answers come from your own records, cite them, and carry only numbers those records give;
tell it "never suggest dance trends" and it remembers (see and delete memories in Settings).
After you post: simulate the first sample take, then move the clock forward a day and a half
(`./dev.ps1 local-time advance 36h`, or `make time ARGS="advance 36h"`). The Ganpati reel
posted after the demo's moment appears, and Home asks whether it's the reel you simulated;
say yes and its arrows compare it with the simulation, and the weekly accuracy record counts
it once it's a week old. Settings also deletes the account and everything Curo holds about
it. The seed takes about two minutes. The data is entirely synthetic
(`fixtures/`), and `FAKE_NOW` in `.env` pins CURO's clock to the dataset's moment,
23 Aug 2027.

| Command | What it does |
| --- | --- |
| `make up` / `make down` | start / stop the Docker stack |
| `make seed` | (re)load the demo creator with 14 days of replayed collection |
| `make learning ARGS=curo.demo` | print what CURO learned: DNA, baselines, sub-clusters, pattern cards, comment themes |
| `make logs` | follow API, worker and scheduler logs |
| `make test` | Python tests + app typecheck, lint and tests |
| `make lint` / `make format` | checks / auto-format |
| `make time ARGS="advance 6h"` | move CURO's clock for every process |
| `make api-types` | regenerate the app's typed API client after changing API schemas |
| `make extract` / `make screenshots` | unpack the prototype / re-take reference screenshots |
| `make compare` | screenshot the app's journey next to the prototype (`reference/compare.html`) |
| `make local` / `make local-seed` | the backend without Docker / reload its demo (`./dev.ps1 local`, `local-seed`) |
| `python tools/record_contracts.py …` | record real vendor and model answers for the contract tests (once keys exist; `docs/INTEGRATION.md`) |

## Layout

```
app/        Expo React Native app (TypeScript, Expo Router)
api/        FastAPI backend: routes, services (logic), providers, schemas, jobs, prompts
worker/     RQ worker + scheduler (share the api package)
db/         SQL migrations; db/local = Supabase shim for local Postgres only
fixtures/   deterministic demo dataset + generator
tools/      prototype extractor + screenshots, time travel, wait-for-API
reference/  unpacked prototype + screenshots of every screen
docs/       the source docs, DECISIONS.md, INTEGRATION.md
deploy/     Railway configs (not used locally)
```

## Rules the code enforces

Public data only (no Instagram API or login). Missing counts are unknown, never zero. Every
number is relative to the creator's own baseline. Predictions are ranges labelled
"estimate based on your history". AI text may only contain numbers from its input facts.
At most five hashtags.
