"""FastAPI application.

Run locally:  uvicorn curo.main:app --reload   (from /api)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from curo import __version__, providers
from curo.config import get_settings
from curo.db import close_pool
from curo.routes import (
    auth,
    chat,
    cron,
    health,
    jobs,
    matches,
    me,
    onboarding,
    opportunities,
    personas,
    projects,
    recaps,
    reels,
    simulations,
    uploads,
    webhooks,
)
from curo.routes import (
    billing as billing_routes,
)
from curo.services import billing


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CURO API",
        version=__version__,
        description="CURO's own backend. The app talks only to this API; keys stay on the server.",
        lifespan=lifespan,
    )
    if settings.app_env in ("development", "test"):
        # Expo web and local tools; the native app doesn't need CORS.
        app.add_middleware(
            CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
        )

    @app.exception_handler(billing.OutOfCredits)
    async def out_of_credits(request: Request, exc: billing.OutOfCredits) -> JSONResponse:
        """402: the web shows the upgrade screen."""
        return JSONResponse(
            status_code=402,
            content={
                "detail": {
                    "code": "out_of_credits",
                    "resource": exc.resource,
                    "plan": exc.plan,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(billing.RevisionLimit)
    async def revision_limit(request: Request, exc: billing.RevisionLimit) -> JSONResponse:
        return JSONResponse(
            status_code=402,
            content={"detail": {"code": "revision_limit", "limit": exc.limit, "message": str(exc)}},
        )

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        """An error CURO didn't expect: reported (route only, no request body), and a plain
        message for the app."""
        providers.get_monitoring().capture_exception(
            exc, {"route": request.url.path, "method": request.method}
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong on Curo’s side. Try again in a moment."},
        )

    app.include_router(health.router)
    if settings.provider("auth") == "local":
        app.include_router(auth.router)
    for module in (
        me,
        onboarding,
        reels,
        opportunities,
        projects,
        personas,
        recaps,
        uploads,
        simulations,
        chat,
        matches,
        jobs,
        webhooks,
        billing_routes,
        cron,
    ):
        app.include_router(module.router)
    return app


app = create_app()
