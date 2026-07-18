"""Flask request/response observability hooks (P0-09)."""
from __future__ import annotations

import logging
import time
from typing import Any

from ptt_observability.logging_config import get_correlation_id

logger = logging.getLogger(__name__)


def register_flask_observability(app: Any) -> None:
    """Attach access logging + X-Correlation-Id response header."""

    @app.before_request
    def _ptt_obs_request_start() -> None:
        from flask import g

        g._ptt_request_start = time.perf_counter()

    @app.after_request
    def _ptt_obs_after_request(response: Any) -> Any:
        from flask import g, request

        cid = get_correlation_id()
        if cid:
            response.headers["X-Correlation-Id"] = cid
            try:
                import sentry_sdk

                sentry_sdk.get_current_scope().set_tag("correlation_id", cid)
            except Exception:
                pass

        started = getattr(g, "_ptt_request_start", None)
        duration_ms = None
        if started is not None:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)

        if request.path.startswith("/static/"):
            return response

        logger.info(
            "http_request",
            extra={
                "correlation_id": cid,
                "http_method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
