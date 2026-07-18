"""LeadAssigned outbox → RMQ E2E verification (Phase 2 P1 #7–#8)."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from ptt_jobs.events_catalog import lead_assigned_idempotency_key

logger = logging.getLogger(__name__)

DEFAULT_MAX_PUBLISH_LAG_SEC = 30


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def nest_leads_base_url() -> str:
    return (
        os.environ.get("PTT_NEST_LEADS_URL")
        or os.environ.get("CRM_API_URL")
        or "http://127.0.0.1:3000"
    ).rstrip("/")


def _http_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    *,
    timeout_sec: float = 15.0,
) -> tuple[int, dict[str, Any] | list[Any] | None]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode() if exc.fp else ""
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"error": raw or str(exc)}
        return exc.code, parsed


def create_staging_lead(*, full_name: str = "P1 E2E Lead") -> dict[str, Any]:
    url = f"{nest_leads_base_url()}/api/v1/leads"
    status, body = _http_json(
        "POST",
        url,
        {
            "full_name": full_name,
            "phone": "0906666666",
            "channel": "meta",
            "source": "p1-e2e",
        },
    )
    if status != 201 or not isinstance(body, dict):
        return {"ok": False, "error": "create_failed", "status": status, "body": body}
    lead_id = int(body.get("id") or 0)
    if lead_id < 1:
        return {"ok": False, "error": "invalid_lead_id", "body": body}
    return {"ok": True, "lead_id": lead_id, "lead": body}


def assign_lead_via_nest(
    lead_id: int,
    owner_id: int,
    *,
    assigned_by: str = "p1-e2e",
) -> dict[str, Any]:
    url = f"{nest_leads_base_url()}/api/v1/leads/{int(lead_id)}"
    status, body = _http_json("PATCH", url, {"owner_id": int(owner_id), "assigned_by": assigned_by})
    if status != 200 or not isinstance(body, dict):
        return {"ok": False, "error": "assign_failed", "status": status, "body": body}
    return {"ok": True, "lead_id": lead_id, "owner_id": owner_id, "lead": body}


def count_lead_assigned_events(
    *,
    lead_id: int,
    owner_id: int | None = None,
) -> dict[str, Any]:
    idem = lead_assigned_idempotency_key(lead_id, owner_id) if owner_id is not None else None
    try:
        from ptt_jobs.db import pg_connection

        clauses = ["event_type = 'LeadAssigned'", "aggregate_id = %s"]
        params: list[Any] = [str(int(lead_id))]
        if idem:
            clauses.append("idempotency_key = %s")
            params.append(idem)
        where = " AND ".join(clauses)
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, idempotency_key, published_at, created_at, payload
                    FROM domain_events
                    WHERE {where}
                    ORDER BY created_at ASC
                    """,
                    params,
                )
                rows = cur.fetchall()
        events = []
        for row in rows:
            created = _parse_ts(row[3])
            published = _parse_ts(row[2])
            lag_sec = None
            if created and published:
                lag_sec = max(0.0, (published - created).total_seconds())
            events.append(
                {
                    "id": str(row[0]),
                    "idempotency_key": row[1],
                    "published_at": published.isoformat() if published else None,
                    "created_at": created.isoformat() if created else None,
                    "publish_lag_sec": lag_sec,
                    "payload": row[4],
                }
            )
        return {
            "ok": True,
            "count": len(events),
            "events": events,
            "idempotency_key": idem,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "count": 0}


def publish_outbox_batch(*, batch_size: int = 50) -> dict[str, Any]:
    from ptt_jobs.config import event_publish_rmq_enabled
    from ptt_jobs.event_publisher import run_event_publisher

    rmq_enabled = event_publish_rmq_enabled()
    published = run_event_publisher(batch_size=max(1, batch_size))
    return {"ok": True, "rmq_enabled": rmq_enabled, "published_count": published}


def wait_for_event_published(
    event_id: str,
    *,
    timeout_sec: float = DEFAULT_MAX_PUBLISH_LAG_SEC,
    poll_interval_sec: float = 0.5,
    auto_publish: bool = True,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(1.0, timeout_sec)
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        try:
            from ptt_jobs.db import pg_connection

            with pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, published_at, created_at, idempotency_key
                        FROM domain_events
                        WHERE id = %s::uuid
                        LIMIT 1
                        """,
                        (event_id,),
                    )
                    row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "event_not_found", "event_id": event_id}
            created = _parse_ts(row[2])
            published = _parse_ts(row[1])
            lag_sec = None
            if created and published:
                lag_sec = max(0.0, (published - created).total_seconds())
            last = {
                "event_id": str(row[0]),
                "idempotency_key": row[3],
                "published_at": published.isoformat() if published else None,
                "created_at": created.isoformat() if created else None,
                "publish_lag_sec": lag_sec,
            }
            if published is not None:
                ok = lag_sec is None or lag_sec <= DEFAULT_MAX_PUBLISH_LAG_SEC
                return {**last, "ok": ok}
            if auto_publish:
                publish_outbox_batch()
        except Exception as exc:
            return {"ok": False, "error": str(exc), "event_id": event_id}
        time.sleep(max(0.1, poll_interval_sec))
    return {
        "ok": False,
        "error": "publish_timeout",
        "event_id": event_id,
        "last": last,
        "timeout_sec": timeout_sec,
    }


def verify_idempotency_duplicate_assign(
    lead_id: int,
    owner_id: int,
    *,
    assigned_by: str = "p1-e2e-idempotency",
    alt_owner_id: int | None = None,
) -> dict[str, Any]:
    """Re-assign same owner after round-trip — expect one outbox row per catalog key."""
    alt = int(alt_owner_id if alt_owner_id is not None else (int(owner_id) + 1))
    first = assign_lead_via_nest(lead_id, alt, assigned_by=f"{assigned_by}-alt")
    if not first.get("ok"):
        return {"ok": False, "error": "alt_assign_failed", "first": first}
    second = assign_lead_via_nest(lead_id, owner_id, assigned_by=assigned_by)
    if not second.get("ok"):
        return {"ok": False, "error": "assign_failed", "second": second}
    third = assign_lead_via_nest(lead_id, owner_id, assigned_by=assigned_by)
    if not third.get("ok"):
        return {"ok": False, "error": "duplicate_assign_failed", "third": third}
    counts = count_lead_assigned_events(lead_id=lead_id, owner_id=owner_id)
    count = int(counts.get("count") or 0)
    return {
        "ok": count == 1,
        "lead_id": lead_id,
        "owner_id": owner_id,
        "alt_owner_id": alt,
        "event_count": count,
        "idempotency_key": lead_assigned_idempotency_key(lead_id, owner_id),
        "events": counts.get("events") or [],
    }


def run_lead_assigned_rmq_e2e(
    *,
    lead_id: int | None = None,
    owner_id: int = 99,
    max_publish_lag_sec: float = DEFAULT_MAX_PUBLISH_LAG_SEC,
    skip_idempotency: bool = False,
) -> dict[str, Any]:
    """Full P1 gate: Nest assign → outbox → publisher → publish lag ≤ 30s."""
    steps: dict[str, Any] = {}

    if lead_id is None:
        created = create_staging_lead()
        steps["create_lead"] = created
        if not created.get("ok"):
            return {"ok": False, "steps": steps, "error": "create_lead_failed"}
        lead_id = int(created["lead_id"])

    assign = assign_lead_via_nest(int(lead_id), int(owner_id))
    steps["assign"] = assign
    if not assign.get("ok"):
        return {"ok": False, "lead_id": lead_id, "steps": steps, "error": "assign_failed"}

    events = count_lead_assigned_events(lead_id=int(lead_id), owner_id=int(owner_id))
    steps["outbox"] = events
    if not events.get("ok") or int(events.get("count") or 0) < 1:
        return {"ok": False, "lead_id": lead_id, "steps": steps, "error": "no_outbox_event"}

    event_id = str((events.get("events") or [{}])[0].get("id") or "")
    if not event_id:
        return {"ok": False, "lead_id": lead_id, "steps": steps, "error": "missing_event_id"}

    publish = publish_outbox_batch()
    steps["publish"] = publish

    wait = wait_for_event_published(
        event_id,
        timeout_sec=max_publish_lag_sec,
        auto_publish=True,
    )
    steps["publish_wait"] = wait
    publish_ok = bool(wait.get("ok"))
    lag = wait.get("publish_lag_sec")
    if lag is not None and float(lag) > max_publish_lag_sec:
        publish_ok = False

    idem_ok = True
    if not skip_idempotency:
        idem = verify_idempotency_duplicate_assign(int(lead_id), int(owner_id))
        steps["idempotency"] = idem
        idem_ok = bool(idem.get("ok"))

    ok = publish_ok and idem_ok
    return {
        "ok": ok,
        "lead_id": lead_id,
        "owner_id": owner_id,
        "max_publish_lag_sec": max_publish_lag_sec,
        "steps": steps,
        "generated_at": _utc_now().replace(microsecond=0).isoformat(),
    }
