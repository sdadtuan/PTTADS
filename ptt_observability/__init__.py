"""Observability helpers — Sentry + structured JSON logs (Phase 1 E8)."""
from __future__ import annotations

from ptt_observability.flask_hooks import register_flask_observability
from ptt_observability.logging_config import (
    bind_correlation_id,
    configure_json_logging,
    get_correlation_id,
    json_logs_enabled,
)
from ptt_observability.sentry_init import capture_exception, init_sentry

__all__ = [
    "bind_correlation_id",
    "capture_exception",
    "configure_json_logging",
    "get_correlation_id",
    "init_observability",
    "init_sentry",
    "json_logs_enabled",
]


def init_observability(*, component: str = "flask", app=None) -> None:
    """Configure JSON logs + optional Sentry for Flask app or worker."""
    configure_json_logging(component=component)
    init_sentry(component=component, app=app)
    if app is not None:
        register_flask_observability(app)
