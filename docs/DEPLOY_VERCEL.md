# Deploying CURO on Vercel — planned, not built yet (D200)

The web app and the API run today as a Next.js app plus a FastAPI backend with an RQ worker and
a scheduler process (`./dev.ps1 local`, or Docker / Railway: `deploy/README.md`). Vercel was
left for later on purpose. This page records what Vercel allows and what the move needs, so it
can be picked up without re-research. The full design is in `PLAN_V2.md` §1–3.

## What Vercel allows (checked 2026-10-21)

| Limit | Hobby | Pro |
|---|---|---|
| Function max duration (Fluid compute, Python included) | 300 s | 800 s |
| Request / response body | 4.5 MB | 4.5 MB |
| Python bundle size | 500 MB | 500 MB |
| Cron jobs | once a day at most (±59 min) | every minute |

## Already in place

- The web app calls only `/api/v1/*` on its own domain. On Vercel, the FastAPI service is
  mounted at `/api` and the Next.js rewrite in `web/next.config.mjs` is unused.
- Uploads never pass through a function: the browser PUTs the video straight to storage
  through a signed URL (`POST /v1/uploads/sign`).
- `POST /v1/cron/tick` runs the scheduler once (guarded by `CRON_SECRET`), for Vercel Cron.
- Only `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` reach the browser.

## Still to build

1. **A Postgres job queue** in place of RQ/Redis: `jobs` rows claimed with
   `for update skip locked`, a lease and an attempt count (PLAN_V2 §3).
2. **Resumable steps**: every long job (onboarding, a simulation's 10 agent batches,
   calibration, nightly learning) split into steps that each finish well under 300 s and
   record where they got to.
3. **A worker endpoint** (`POST /api/v1/worker/run`, `CRON_SECRET`) that runs steps until
   its time budget is spent; kicked on enqueue, pumped while the app polls a job, and run by
   the cron.
4. **`vercel.json`** with two services (Next.js in `web/`, FastAPI in `api/` via
   `tool.vercel.entrypoint`), `/api/*` routed to the backend, and the cron schedule.
5. **On Hobby**, 6-hourly snapshots and 12-hourly new-reel checks need either Pro (per-minute
   cron) or `worker/standalone.py` (the same job loop as a long-lived process on a small host).
6. Environment: everything in `.env.example` with `MOCK_MODE=false` on the backend service;
   `web/.env.example` on the web service. Never put a service-role key in a `NEXT_PUBLIC_`
   variable.
