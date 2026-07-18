"""Optional Sentry initialization — no-op when SENTRY_DSN unset."""
from __future__ import annotations

import logging
import os
from typing import Any

from ptt_observability.logging_config import get_correlation_id

logger = logging.getLogger(__name__)


def _sentry_before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    cid = get_correlation_id()
    if cid:
        tags = event.setdefault("tags", {})
        tags["correlation_id"] = cid
    return event


def init_sentry(*, component: str = "flask", app: Any = None) -> None:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        logger.warning("sentry-sdk not installed — pip install sentry-sdk[flask]")
        return

    integrations = [
        LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
    ]
    if app is not None and component == "flask":
        integrations.append(FlaskIntegration())

    sentry_sdk.init(
        dsn=dsn,
        integrations=integrations,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "development"),
        release=os.environ.get("SENTRY_RELEASE", "").strip() or None,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0")),
        send_default_pii=False,
        before_send=_sentry_before_send,
    )
    sentry_sdk.set_tag("component", component)


def capture_exception(exc: BaseException, *, tags: dict[str, str] | None = None) -> None:
    """Best-effort Sentry capture with correlation_id tag."""
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            cid = get_correlation_id()
            if cid:
                scope.set_tag("correlation_id", cid)
            if tags:
                for k, v in tags.items():
                    scope.set_tag(k, v)
            sentry_sdk.capture_exception(exc)
    except Exception:
        logger.debug("sentry capture_exception skipped", exc_info=True)
