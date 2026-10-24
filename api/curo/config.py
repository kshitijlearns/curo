"""Settings, read from the environment (see .env.example at the repo root).

This is the only module that knows about MOCK_MODE. Business logic asks
``settings.provider("llm")`` and never branches on mock mode itself.
"""

from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
# CURO_ENV_FILE picks a different env file; an empty value reads none (tests do this).
ENV_FILE = os.environ.get("CURO_ENV_FILE", str(REPO_ROOT / ".env")) or None

# Used only when APP_ENV=development/test and no secret is configured.
DEV_JWT_SECRET = "curo-local-dev-only-not-a-secret"

ProviderName = Literal["public_data", "video", "embedding", "llm", "storage", "monitoring", "auth"]

# What each provider resolves to when MOCK_MODE is off and no override is set.
_REAL_DEFAULTS: dict[str, str] = {
    "video": "gemini",
    "embedding": "gemini",
    "llm": "claude",
    "storage": "supabase",
    "monitoring": "live",
    "auth": "supabase",
}
# What each provider resolves to in MOCK_MODE.
_MOCK_DEFAULTS: dict[str, str] = {
    "public_data": "mock",
    "video": "mock",
    "embedding": "mock",
    "llm": "mock",
    "storage": "local",
    "monitoring": "noop",
    "auth": "local",
}


class Settings(BaseSettings):
    # Real environment variables win over the repo-root .env file.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore", case_sensitive=False)

    # --- App ---
    mock_mode: bool = True
    app_env: Literal["development", "test", "staging", "production"] = "development"
    api_base_url: str = ""

    # --- Supabase / database ---
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    database_url: str = "postgresql://postgres:postgres@localhost:5432/curo"
    storage_bucket_videos: str = "reel-videos"
    storage_bucket_thumbs: str = "reel-thumbs"

    # --- Queue ---
    redis_url: str = "redis://localhost:6379/0"
    # rq: Redis + the worker (Docker). inline: in the caller (tests, seed). thread: one
    # background thread in the API process (tools/local_stack.py, no Docker).
    queue_mode: Literal["rq", "inline", "thread"] = "rq"

    # --- Public data (no Instagram API) ---
    public_data_primary: Literal["apify", "brightdata"] = "apify"
    apify_token: str = ""
    apify_profile_actor_id: str = ""
    apify_reels_actor_id: str = ""
    apify_comments_actor_id: str = ""
    apify_hashtag_actor_id: str = ""
    apify_webhook_secret: str = ""
    brightdata_api_key: str = ""

    # --- Anthropic ---
    anthropic_api_key: str = ""
    claude_model_main: str = "claude-sonnet-5-5"
    claude_model_fast: str = "claude-haiku-5-5"

    # --- Google Gemini ---
    gemini_api_key: str = ""
    gemini_video_model: str = "gemini-3.6-flash"
    gemini_embedding_model: str = "gemini-embedding-2"
    embedding_dim: int = 768

    # --- Monitoring ---
    sentry_dsn_backend: str = ""
    posthog_key: str = ""

    # --- Per-provider overrides (empty = follow MOCK_MODE) ---
    public_data_provider: Literal["", "mock", "apify", "brightdata"] = ""
    video_provider: Literal["", "mock", "gemini"] = ""
    embedding_provider: Literal["", "mock", "gemini"] = ""
    llm_provider: Literal["", "mock", "claude"] = ""
    storage_provider: Literal["", "local", "supabase"] = ""
    monitoring_provider: Literal["", "noop", "live"] = ""
    auth_provider: Literal["", "local", "supabase"] = ""

    # --- Collection and product limits (PLAN_V2 §4.3, §4.5, §4.6) ---
    comment_limit: int = 100  # comments read per reel
    inactive_pause_days: int = 14  # collection pauses for creators away this long
    sim_agents: int = 1000
    sim_max_seconds: float = 90.0
    sim_agent_batch: int = 100
    free_projects: int = 2
    free_simulations: int = 2
    free_chat: int = 10
    pro_projects: int = 10
    pro_simulations: int = 10
    pro_chat: int = 100
    pro_price_usd: float = 30.0
    topup_price_usd: float = 1.5
    project_revisions: int = 10
    agent_chat_messages: int = 10
    cost_alert_usd: float = 5.0
    payment_provider: Literal["mock", "razorpay"] = "mock"
    admin_emails: str = ""  # comma-separated: who sees /admin/costs
    web_url: str = "curo-sand.vercel.app"  # printed on the recap share card
    cron_secret: str = ""  # POST /v1/cron/tick needs "Authorization: Bearer <CRON_SECRET>"
    claude_model_agents: str = "claude-haiku-5-5"

    # --- Local development ---
    fake_now: datetime | None = None  # time-travel anchor, e.g. 2027-08-23T10:00:00+05:30
    local_storage_dir: str = ".data/storage"
    default_timezone: str = "Asia/Kolkata"
    apply_supabase_shim: bool | None = None  # None = apply when auth provider is local
    # A folder: every AI task saves its first few inputs there, as JSON, for
    # tools/record_contracts.py to send to the real model (e.g. .data/task-inputs).
    capture_task_inputs: str = ""

    @field_validator("fake_now", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        return None if v in ("", None) else v

    @model_validator(mode="after")
    def _check(self) -> Settings:
        if self.embedding_dim != 768:
            raise ValueError("EMBEDDING_DIM must be 768: the pgvector column is fixed at 768")
        if not self.supabase_jwt_secret:
            if self.app_env in ("staging", "production"):
                raise ValueError("SUPABASE_JWT_SECRET is required outside development")
            self.supabase_jwt_secret = DEV_JWT_SECRET
        if self.app_env == "production" and self.supabase_jwt_secret == DEV_JWT_SECRET:
            raise ValueError("Refusing to run production with the development JWT secret")
        return self

    def provider(self, name: ProviderName) -> str:
        """Resolve which implementation a provider uses."""
        override = getattr(self, f"{name}_provider")
        if override:
            return override
        if self.mock_mode:
            return _MOCK_DEFAULTS[name]
        if name == "public_data":
            return self.public_data_primary
        return _REAL_DEFAULTS[name]

    @property
    def use_supabase_shim(self) -> bool:
        if self.apply_supabase_shim is not None:
            return self.apply_supabase_shim
        return self.provider("auth") == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
