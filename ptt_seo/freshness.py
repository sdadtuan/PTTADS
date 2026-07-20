"""Content freshness — decay scoring and refresh queue (Phase 4B)."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from typing import Any

from ptt_seo.connectors.freshness_signals import collect_signals, content_url_path
from ptt_seo.constants import SEO_AEO_SERVICE_SLUGS
from ptt_seo.content import transition_status
from ptt_seo.db import crm_connection, seo_write

logger = logging.getLogger(__name__)

SCOREABLE_STATUSES = frozenset({"published", "monitoring"})
REFRESH_THRESHOLD = float(os.environ.get("PTT_FRESHNESS_REFRESH_THRESHOLD", "60"))


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def freshness_sync_enabled() -> bool:
    return os.environ.get("PTT_FRESHNESS_SCAN_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def refresh_priority(decay_score: float) -> str:
    if decay_score >= 80:
        return "urgent"
    if decay_score >= 60:
        return "high"
    if decay_score >= 40:
        return "medium"
    return "low"


def compute_decay_score(
    *,
    age_days: int,
    traffic_delta_pct: float | None,
    gsc_clicks_current: int,
    gsc_clicks_previous: int,
    workflow_status: str,
) -> float:
    if workflow_status not in SCOREABLE_STATUSES:
        return 0.0
    base = min(age_days / 365.0 * 40.0, 40.0)
    traffic_component = 0.0
    if traffic_delta_pct is not None:
        traffic_component = min(max(0.0, -traffic_delta_pct), 40.0)
    gsc_decay = 0.0
    if gsc_clicks_previous > 10 and gsc_clicks_current < gsc_clicks_previous * 0.7:
        gsc_decay = 20.0
    return min(100.0, round(base + traffic_component + gsc_decay, 2))


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    text = str(raw).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _age_days(item: dict[str, Any]) -> int:
    anchor = (
        _parse_date(item.get("publish_date"))
        or _parse_date(item.get("updated_at"))
        or _parse_date(item.get("created_at"))
    )
    if anchor is None:
        return 0
    return max(0, (date.today() - anchor).days)


def score_content_item(conn: Any, customer_id: int, content_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM seo_content WHERE id = ?", (content_id,)).fetchone()
    if row is None:
        return {"ok": False, "error": "content_not_found"}
    item = dict(row)
    if int(item.get("customer_id") or 0) != customer_id:
        return {"ok": False, "error": "customer_mismatch"}

    signals = collect_signals(conn, customer_id, item)
    age = _age_days(item)
    decay = compute_decay_score(
        age_days=age,
        traffic_delta_pct=signals.get("traffic_delta_pct"),
        gsc_clicks_current=int(signals.get("gsc_clicks_current") or 0),
        gsc_clicks_previous=int(signals.get("gsc_clicks_previous") or 0),
        workflow_status=str(item.get("workflow_status") or ""),
    )
    priority = refresh_priority(decay)
    signals_json = json.dumps({**signals, "url_path": content_url_path(item)}, ensure_ascii=False)

    conn.execute(
        """
        INSERT INTO seo_content_freshness (
            customer_id, content_id, decay_score, traffic_delta_pct, age_days,
            signals_json, refresh_priority, last_scored_at
        ) VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(customer_id, content_id) DO UPDATE SET
            decay_score=excluded.decay_score,
            traffic_delta_pct=excluded.traffic_delta_pct,
            age_days=excluded.age_days,
            signals_json=excluded.signals_json,
            refresh_priority=excluded.refresh_priority,
            last_scored_at=excluded.last_scored_at
        """,
        (
            customer_id,
            content_id,
            decay,
            signals.get("traffic_delta_pct"),
            age,
            signals_json,
            priority,
            _ts(),
        ),
    )
    conn.commit()
    return {
        "ok": True,
        "content_id": content_id,
        "decay_score": decay,
        "refresh_priority": priority,
        "age_days": age,
        "signals": signals,
    }


def apply_refresh_flags(
    conn: Any,
    customer_id: int,
    *,
    threshold: float = REFRESH_THRESHOLD,
) -> int:
    rows = conn.execute(
        """
        SELECT f.content_id, f.decay_score, c.workflow_status
        FROM seo_content_freshness f
        JOIN seo_content c ON c.id = f.content_id
        WHERE f.customer_id = ? AND f.decay_score >= ?
          AND c.workflow_status IN ('published', 'monitoring')
        """,
        (customer_id, threshold),
    ).fetchall()
    count = 0
    for row in rows:
        try:
            transition_status(
                conn,
                int(row["content_id"]),
                "refresh_required",
                actor_id="freshness_scan",
                notes=f"Auto-flag decay_score={row['decay_score']}",
            )
            count += 1
        except ValueError:
            continue
    return count


def score_customer_content(
    customer_id: int,
    *,
    apply_refresh: bool = True,
    threshold: float = REFRESH_THRESHOLD,
) -> dict[str, Any]:
    scored = 0
    flagged = 0
    with seo_write() as conn:
        rows = conn.execute(
            """
            SELECT id FROM seo_content
            WHERE customer_id = ? AND workflow_status IN ('published', 'monitoring')
            """,
            (customer_id,),
        ).fetchall()
        for row in rows:
            outcome = score_content_item(conn, customer_id, int(row["id"]))
            if outcome.get("ok"):
                scored += 1
        if apply_refresh:
            flagged = apply_refresh_flags(conn, customer_id, threshold=threshold)
    return {
        "ok": True,
        "customer_id": customer_id,
        "scored": scored,
        "refresh_flagged": flagged,
    }


def list_freshness(
    conn: Any,
    customer_id: int,
    *,
    min_priority: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    sql = """
        SELECT f.*, c.title, c.slug, c.workflow_status
        FROM seo_content_freshness f
        JOIN seo_content c ON c.id = f.content_id
        WHERE f.customer_id = ?
    """
    params: list[Any] = [customer_id]
    priority_order = {"urgent": 4, "high": 3, "medium": 2, "low": 1}
    if min_priority and min_priority in priority_order:
        allowed = [p for p, v in priority_order.items() if v >= priority_order[min_priority]]
        placeholders = ",".join("?" for _ in allowed)
        sql += f" AND f.refresh_priority IN ({placeholders})"
        params.extend(allowed)
    sql += " ORDER BY f.decay_score DESC, f.last_scored_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        try:
            d["signals"] = json.loads(d.pop("signals_json", "{}") or "{}")
        except json.JSONDecodeError:
            d["signals"] = {}
        out.append(d)
    return out


def freshness_map(conn: Any, customer_id: int | None) -> dict[int, dict[str, Any]]:
    if customer_id is None:
        return {}
    items = list_freshness(conn, customer_id, limit=500)
    return {int(i["content_id"]): i for i in items}


def list_freshness_customer_ids() -> list[int]:
    slug_ph = ",".join("?" for _ in SEO_AEO_SERVICE_SLUGS)
    with crm_connection() as crm:
        rows = crm.execute(
            f"""
            SELECT DISTINCT customer_id FROM crm_service_lifecycle
            WHERE service_slug IN ({slug_ph})
              AND COALESCE(status, 'active') != 'cancelled'
            """,
            tuple(SEO_AEO_SERVICE_SLUGS),
        ).fetchall()
    return sorted({int(r["customer_id"]) for r in rows})


def scan_all_freshness_customers(*, apply_refresh: bool = True) -> dict[str, Any]:
    if not freshness_sync_enabled():
        return {"ok": True, "skipped": True, "reason": "PTT_FRESHNESS_SCAN_ENABLED=0"}

    customer_ids = list_freshness_customer_ids()
    if not customer_ids:
        return {"ok": True, "skipped": True, "reason": "no_seo_customers", "customers": 0}

    results: list[dict[str, Any]] = []
    total_scored = 0
    total_flagged = 0
    for cid in customer_ids:
        outcome = score_customer_content(cid, apply_refresh=apply_refresh)
        results.append(outcome)
        total_scored += int(outcome.get("scored") or 0)
        total_flagged += int(outcome.get("refresh_flagged") or 0)

    return {
        "ok": True,
        "customers": len(customer_ids),
        "scored": total_scored,
        "refresh_flagged": total_flagged,
        "results": results,
    }


def enqueue_freshness_scan(customer_id: int) -> dict[str, Any]:
    payload = {"customer_id": customer_id}
    idem = f"seo_freshness_scan:{customer_id}:{date.today().isoformat()}"
    try:
        from ptt_jobs.config import jobs_enabled, jobs_sync_fallback
        from ptt_jobs.db import pg_available
        from ptt_jobs.enqueue import enqueue_job

        if jobs_enabled() and pg_available():
            job = enqueue_job("seo_freshness_scan", payload, idem)
            return {"ok": True, "mode": "queue", "job": job}
        if jobs_sync_fallback():
            outcome = score_customer_content(customer_id)
            return {"ok": outcome.get("ok", False), "mode": "sync", "outcome": outcome}
        return {"ok": False, "error": "job_queue_unavailable"}
    except Exception as exc:
        logger.exception("enqueue_freshness_scan failed")
        return {"ok": False, "error": str(exc)}


def process_seo_freshness_scan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    customer_id = int(payload.get("customer_id") or 0)
    if customer_id:
        return score_customer_content(customer_id)
    return scan_all_freshness_customers()
