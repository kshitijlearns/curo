"""Provider factory: the only place that turns settings into implementations.

Business logic asks for ``get_public_data()``, ``get_llm()``… and never checks MOCK_MODE.
Tests replace an implementation with ``override(name, instance)``. (Factories are named
``get_*`` so they never collide with the provider subpackages of the same name.)
"""

from __future__ import annotations

import os
import threading
from typing import Any

from curo.config import get_settings

_instances: dict[str, Any] = {}
_lock = threading.RLock()  # re-entrant: building one provider may build another (video → storage)


def override(name: str, instance: Any | None) -> None:
    """Use ``instance`` for provider ``name`` (None restores the configured one)."""
    with _lock:
        if instance is None:
            _instances.pop(name, None)
        else:
            _instances[name] = instance


def reset() -> None:
    with _lock:
        _instances.clear()


def _get(name: str, build) -> Any:
    with _lock:
        if name not in _instances:
            _instances[name] = build()
        return _instances[name]


def get_public_data():
    """The PublicDataProvider, wrapped in retry → backup vendor failover."""
    from curo.providers.public_data.failover import FailoverProvider

    def build():
        settings = get_settings()
        choice = settings.provider("public_data")
        if choice == "mock":
            from curo.providers.public_data.mock import MockPublicDataProvider

            return FailoverProvider(MockPublicDataProvider())

        from curo.providers.public_data.apify import ApifyProvider
        from curo.providers.public_data.brightdata import BrightDataProvider

        apify = ApifyProvider(
            settings.apify_token,
            {
                "profile": settings.apify_profile_actor_id,
                "reels": settings.apify_reels_actor_id,
                "comments": settings.apify_comments_actor_id,
                "hashtag": settings.apify_hashtag_actor_id,
            },
        )
        bright = (
            BrightDataProvider(settings.brightdata_api_key) if settings.brightdata_api_key else None
        )
        if choice == "brightdata":
            return FailoverProvider(BrightDataProvider(settings.brightdata_api_key), apify)
        return FailoverProvider(apify, bright)

    return _get("public_data", build)


def get_storage():
    def build():
        settings = get_settings()
        if settings.provider("storage") == "local":
            from curo.config import REPO_ROOT
            from curo.providers.storage.local import LocalStorage

            root = settings.local_storage_dir
            return LocalStorage(
                root if os.path.isabs(root) else REPO_ROOT / root,
                secret=settings.supabase_jwt_secret,
            )
        from curo.providers.storage.supabase import SupabaseStorage

        return SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)

    return _get("storage", build)


def get_video():
    """VideoUnderstandingProvider (T1)."""

    def build():
        settings = get_settings()
        if settings.provider("video") == "mock":
            from curo.providers.video.mock import MockVideoProvider

            return MockVideoProvider(get_storage())
        from curo.providers.video.gemini import GeminiVideoProvider

        return GeminiVideoProvider(
            settings.gemini_api_key, settings.gemini_video_model, get_storage()
        )

    return _get("video", build)


def get_embedding():
    def build():
        settings = get_settings()
        if settings.provider("embedding") == "mock":
            from curo.providers.embedding.mock import MockEmbeddingProvider

            return MockEmbeddingProvider()
        from curo.providers.embedding.gemini import GeminiEmbeddingProvider

        return GeminiEmbeddingProvider(settings.gemini_api_key, settings.gemini_embedding_model)

    return _get("embedding", build)


def get_llm():
    def build():
        settings = get_settings()
        if settings.provider("llm") == "mock":
            from curo.providers.llm.mock import MockLLMProvider

            return MockLLMProvider()
        from curo.providers.llm.claude import ClaudeProvider

        return ClaudeProvider(
            settings.anthropic_api_key,
            settings.claude_model_main,
            settings.claude_model_fast,
            settings.claude_model_agents,
        )

    return _get("llm", build)


def get_monitoring():
    """Monitoring: errors (Sentry) and product events (PostHog)."""

    def build():
        settings = get_settings()
        if settings.provider("monitoring") == "noop":
            from curo.providers.monitoring.noop import NoopMonitoring

            return NoopMonitoring()
        from curo.providers.monitoring.live import LiveMonitoring

        return LiveMonitoring(settings.sentry_dsn_backend, settings.posthog_key)

    return _get("monitoring", build)


def get_payments():
    """The PaymentProvider (PAYMENT_PROVIDER: mock | razorpay)."""

    def build():
        if get_settings().payment_provider == "razorpay":
            from curo.providers.payments.razorpay import RazorpayPaymentProvider

            return RazorpayPaymentProvider()
        from curo.providers.payments.mock import MockPaymentProvider

        return MockPaymentProvider()

    return _get("payments", build)
