"""Structured JSON logging with correlation_id context."""
from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
_component: contextvars.ContextVar[str] = contextvars.ContextVar("component", default="ptt")


def json_logs_enabled() -> bool:
    """Enable JSON logs in prod/staging or when PTT_JSON_LOGS=1."""
    explicit = os.environ.get("PTT_JSON_LOGS", "").strip().lower()
    if explicit in ("1", "true", "yes", "on"):
        return True
    if explicit in ("0", "false", "no", "off"):
        return False
    env = (
        os.environ.get("SENTRY_ENVIRONMENT")
        or os.environ.get("PTT_ENV")
        or os.environ.get("FLASK_ENV")
        or ""
    ).strip().lower()
    return env in ("production", "staging", "prod")


def bind_correlation_id(value: str | None) -> contextvars.Token:
    return _correlation_id.set(value)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "component": getattr(record, "component", None) or _component.get(),
        }
        cid = getattr(record, "correlation_id", None) or _correlation_id.get()
        if cid:
            payload["correlation_id"] = cid
        for key in (
            "job_type",
            "channel",
            "client_code",
            "job_id",
            "http_method",
            "path",
            "status",
            "duration_ms",
            "request_id",
        ):
            val = getattr(record, key, None)
            if val is not None and val != "":
                payload[key] = val
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_json_logging(*, component: str = "ptt", level: int = logging.INFO) -> None:
    _component.set(component)
    root = logging.getLogger()
    if not json_logs_enabled():
        if not root.handlers:
            logging.basicConfig(level=level)
        return
    if any(isinstance(h.formatter, JsonLogFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
