"""Job queue configuration from environment."""
from __future__ import annotations

import os


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def database_url() -> str:
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("PTT_DATABASE_URL")
        or "postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency"
    ).strip()


def jobs_enabled() -> bool:
    """Queue path active when PG URL set and not explicitly disabled."""
    if _truthy("PTT_JOBS_DISABLED", "0"):
        return False
    return _truthy("PTT_JOBS_ENABLED", "1")


def webhook_enqueue_enabled() -> bool:
    return _truthy("PTT_WEBHOOK_V1_ENQUEUE", "1")


def jobs_sync_fallback() -> bool:
    """When PG unavailable, ingest inline instead of failing webhook."""
    return _truthy("PTT_JOBS_SYNC_FALLBACK", "1")


def sqlite_db_path() -> str:
    from pathlib import Path

    base = Path(__file__).resolve().parents[1]
    return os.environ.get("PTT_SQLITE_PATH", str(base / "ptt.db"))


def rabbitmq_url() -> str:
    return (
        os.environ.get("RABBITMQ_URL")
        or os.environ.get("PTT_RABBITMQ_URL")
        or "amqp://ptt:ptt_dev@127.0.0.1:5672/"
    ).strip()


def event_publish_rmq_enabled() -> bool:
    """Publish domain_events / job wake signals to RabbitMQ (Phase 1b)."""
    return _truthy("PTT_EVENT_PUBLISH_RMQ", "0")
