"""Sentry + PostHog implementation of Monitoring — NOT IMPLEMENTED YET (needs
SENTRY_DSN_BACKEND and POSTHOG_KEY).

TODO when the keys arrive (see docs/INTEGRATION.md):
1. sentry-sdk: sentry_sdk.init(dsn=SENTRY_DSN_BACKEND, environment=APP_ENV,
   traces_sample_rate=0.1, send_default_pii=False) once at startup; capture_exception →
   sentry_sdk.capture_exception with context as a scope's extras (route or job type and
   ids only).
2. posthog: Posthog(POSTHOG_KEY, host=POSTHOG_HOST); capture_event → posthog.capture(
   distinct_id=creator_id or "anonymous", event=name, properties=props). Never send
   captions, comments, usernames or emails.
3. The app's own crash and analytics SDKs (sentry-expo, posthog-react-native) are set up
   in the app with EXPO_PUBLIC_ keys.
4. Check on staging: a job that crashes shows in Sentry with its type and id (no captions or
   comments); run a simulation and see `simulation_done` in PostHog.
"""

from __future__ import annotations

from .base import Monitoring

_TODO = "Live monitoring not implemented yet: set MONITORING_PROVIDER=noop (see INTEGRATION.md)"


class LiveMonitoring(Monitoring):
    name = "live"

    def __init__(self, sentry_dsn: str, posthog_key: str):
        raise NotImplementedError(_TODO)

    def capture_exception(self, exc, context=None):
        raise NotImplementedError(_TODO)

    def capture_event(self, name, props, creator_id):
        raise NotImplementedError(_TODO)
