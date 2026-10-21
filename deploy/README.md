# Deployment (later)

Nothing here is used for local development; it is ready for when accounts exist.

| Target | Config | Notes |
| --- | --- | --- |
| Railway: API | `railway/api.toml` | Runs Supabase migrations (`--no-shim`) then uvicorn; health check `/health` |
| Railway: worker | `railway/worker.toml` | RQ worker on the `studio` and `curo` queues (Studio jobs first) |
| Railway: scheduler | `railway/scheduler.toml` | Exactly one replica |
| Railway: Redis | Railway's Redis plugin | Set `REDIS_URL` on all three services |
| Expo (EAS) | `../app/eas.json` | `npx eas-cli@latest build --profile preview`; the `development` profile needs `expo-dev-client` (added with voice input) |

All three Railway services use the same image (`api/Dockerfile`, build context = repo root)
and the same environment variables (`.env.example`, with `MOCK_MODE=false`).
