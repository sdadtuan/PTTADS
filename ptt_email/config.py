"""Email send platform configuration."""
from __future__ import annotations

import os


def email_send_enabled() -> bool:
    return _flag("PTT_EMAIL_SEND_ENABLED", default=True)


def email_journeys_enabled() -> bool:
    return _flag("PTT_EMAIL_JOURNEYS_ENABLED", default=False)


def email_esp_dry_run() -> bool:
    if not email_send_enabled():
        return True
    return _flag("PTT_EMAIL_ESP_DRY_RUN", default=False)


def email_batch_size() -> int:
    raw = (os.environ.get("PTT_EMAIL_SEND_BATCH_SIZE") or "100").strip()
    try:
        return max(1, min(int(raw), 1000))
    except ValueError:
        return 100


def email_webhook_verify() -> bool:
    return _flag("PTT_EMAIL_WEBHOOK_VERIFY", default=False)


def email_clickhouse_export_enabled() -> bool:
    return _flag("PTT_EMAIL_CLICKHOUSE_EXPORT", default=True)


def email_deliverability_alerts_enabled() -> bool:
    return _flag("PTT_EMAIL_DELIVERABILITY_ALERTS", default=True)


def email_complaint_pause_pct() -> float:
    raw = (os.environ.get("PTT_EMAIL_COMPLAINT_PAUSE_PCT") or "0.3").strip()
    try:
        return float(raw)
    except ValueError:
        return 0.3


def warmup_volume_for_stage(stage: int) -> int:
    caps = [500, 2000, 5000, 10000, 25000, 50000]
    idx = max(0, min(stage, len(caps) - 1))
    return caps[idx]


def _flag(name: str, *, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}
