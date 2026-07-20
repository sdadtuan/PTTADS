"""Eligibility helpers — frequency cap + quiet hours (EM-10 send hardening)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA = "email_mkt"


def _parse_quiet_hours(config: dict[str, Any] | None) -> tuple[str, str, str]:
    cfg = config or {}
    start = str(cfg.get("start") or "22:00")
    end = str(cfg.get("end") or "07:00")
    tz_name = str(cfg.get("timezone") or "Asia/Ho_Chi_Minh")
    return start, end, tz_name


def _parse_hhmm(value: str) -> tuple[int, int]:
    parts = value.strip().split(":")
    hour = int(parts[0]) if parts else 0
    minute = int(parts[1]) if len(parts) > 1 else 0
    return hour, minute


def in_quiet_hours(
    *,
    now: datetime | None = None,
    quiet_config: dict[str, Any] | None = None,
    workspace_tz: str | None = None,
) -> bool:
    start_s, end_s, rule_tz = _parse_quiet_hours(quiet_config)
    tz_name = workspace_tz or rule_tz or "Asia/Ho_Chi_Minh"
    try:
        local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(tz_name))
    except Exception:
        local = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    sh, sm = _parse_hhmm(start_s)
    eh, em = _parse_hhmm(end_s)
    start_m = sh * 60 + sm
    end_m = eh * 60 + em
    cur_m = local.hour * 60 + local.minute

    if start_m <= end_m:
        return start_m <= cur_m < end_m
    return cur_m >= start_m or cur_m < end_m


def next_send_after_quiet_hours(
    *,
    now: datetime | None = None,
    quiet_config: dict[str, Any] | None = None,
    workspace_tz: str | None = None,
) -> datetime:
    now = now or datetime.now(timezone.utc)
    if not in_quiet_hours(now=now, quiet_config=quiet_config, workspace_tz=workspace_tz):
        return now

    start_s, _end_s, rule_tz = _parse_quiet_hours(quiet_config)
    tz_name = workspace_tz or rule_tz or "Asia/Ho_Chi_Minh"
    try:
        local = now.astimezone(ZoneInfo(tz_name))
        tz = ZoneInfo(tz_name)
    except Exception:
        local = now
        tz = timezone.utc

    eh, em = _parse_hhmm(_parse_quiet_hours(quiet_config)[1])
    candidate = local.replace(hour=eh, minute=em, second=0, microsecond=0)
    if candidate <= local:
        candidate = candidate + timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def contact_over_frequency_cap(cur, contact_id: str, cap: int) -> bool:
    if cap <= 0:
        return False
    cur.execute(
        f"""
        SELECT COUNT(*)::int
        FROM {SCHEMA}.send_queue
        WHERE contact_id = %s::uuid
          AND status IN ('pending', 'processing', 'sent', 'delivered')
          AND COALESCE(sent_at, created_at) >= NOW() - INTERVAL '7 days'
        """,
        (contact_id,),
    )
    row = cur.fetchone()
    count = int(row[0]) if row else 0
    return count >= cap


def load_quiet_hours_rule(cur) -> dict[str, Any] | None:
    cur.execute(
        f"""
        SELECT config_json
        FROM {SCHEMA}.rules
        WHERE scope = 'global' AND rule_type = 'quiet_hours' AND enabled = TRUE
        ORDER BY priority ASC
        LIMIT 1
        """,
    )
    row = cur.fetchone()
    if not row:
        return None
    raw = row[0]
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None
