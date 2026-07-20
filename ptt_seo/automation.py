"""Automation & alerts (Spec 6.13 Phase 3)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from ptt_seo.connectors.gsc import list_sync_runs
from ptt_seo.technical import count_open_critical


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def create_alert(
    conn: sqlite3.Connection,
    *,
    customer_id: int | None,
    alert_type: str,
    message: str,
    severity: str = "warn",
    link: str = "",
) -> int | None:
    """Dedupe: skip if same open alert type+message in last 24h."""
    existing = conn.execute(
        """
        SELECT id FROM seo_alerts
        WHERE alert_type = ? AND message = ? AND status = 'open'
          AND created_at >= datetime('now', '-1 day')
        LIMIT 1
        """,
        (alert_type, message),
    ).fetchone()
    if existing:
        return None
    cur = conn.execute(
        """
        INSERT INTO seo_alerts (customer_id, alert_type, severity, message, link, status, created_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (customer_id, alert_type, severity, message, link, "open", _ts()),
    )
    conn.commit()
    alert_id = int(cur.lastrowid)
    try:
        from ptt_seo.alert_notify import notify_seo_alert

        notify_seo_alert(alert_type=alert_type, message=message, link=link)
    except Exception:
        pass
    return alert_id


def list_alerts(conn: sqlite3.Connection, *, status: str = "open", limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM seo_alerts WHERE status = ? ORDER BY id DESC LIMIT ?
        """,
        (status, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def resolve_alert(conn: sqlite3.Connection, alert_id: int) -> None:
    conn.execute(
        "UPDATE seo_alerts SET status = 'resolved', resolved_at = ? WHERE id = ?",
        (_ts(), alert_id),
    )
    conn.commit()


def run_alert_checks(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Evaluate rules and create alerts. Returns new alerts."""
    created: list[dict[str, Any]] = []

    # Critical technical issues
    crit = count_open_critical(conn)
    if crit > 0:
        aid = create_alert(
            conn,
            customer_id=None,
            alert_type="critical_issues",
            severity="danger",
            message=f"Có {crit} issue kỹ thuật nghiêm trọng cần xử lý.",
            link="/crm/seo/technical",
        )
        if aid:
            created.append({"id": aid, "type": "critical_issues"})

    # Failed sync runs (last 7 days)
    failed = conn.execute(
        """
        SELECT customer_id, source, error_message FROM seo_sync_runs
        WHERE status = 'failed' AND started_at >= datetime('now', '-7 days')
        ORDER BY id DESC LIMIT 5
        """
    ).fetchall()
    for r in failed:
        msg = f"Sync {r['source']} thất bại: {(r['error_message'] or '')[:120]}"
        aid = create_alert(
            conn,
            customer_id=int(r["customer_id"]),
            alert_type="sync_failed",
            severity="warn",
            message=msg,
            link="/crm/seo/automations",
        )
        if aid:
            created.append({"id": aid, "type": "sync_failed"})

    # Low AEO coverage per customer
    try:
        from ptt_seo.aeo_store import list_aeo_questions, list_customers_with_aeo

        for cid in list_customers_with_aeo(conn):
            qs = list_aeo_questions(conn, cid)
            if len(qs) >= 3:
                visible = sum(1 for q in qs if int(q.get("brand_visible") or 0) == 1)
                pct = 100.0 * visible / len(qs)
                if pct < 50:
                    aid = create_alert(
                        conn,
                        customer_id=cid,
                        alert_type="aeo_coverage_low",
                        severity="warn",
                        message=f"AEO coverage thấp ({pct:.0f}%) — {visible}/{len(qs)} queries.",
                        link=f"/crm/seo/clients/{cid}",
                    )
                    if aid:
                        created.append({"id": aid, "type": "aeo_coverage_low"})
    except Exception:
        pass

    # Overdue content
    overdue = conn.execute(
        """
        SELECT customer_id, COUNT(*) AS c FROM seo_content
        WHERE due_date != '' AND due_date < date('now')
          AND workflow_status NOT IN ('published','monitoring','archived','approved')
        GROUP BY customer_id
        """
    ).fetchall()
    for r in overdue:
        cid = int(r["customer_id"])
        aid = create_alert(
            conn,
            customer_id=cid,
            alert_type="content_overdue",
            severity="warn",
            message=f"{r['c']} nội dung quá hạn due date.",
            link=f"/crm/seo/content?customer_id={cid}",
        )
        if aid:
            created.append({"id": aid, "type": "content_overdue"})

    urgent = conn.execute(
        """
        SELECT customer_id, COUNT(*) AS c FROM seo_content_freshness
        WHERE refresh_priority = 'urgent'
        GROUP BY customer_id
        """
    ).fetchall()
    for r in urgent:
        cid = int(r["customer_id"])
        aid = create_alert(
            conn,
            customer_id=cid,
            alert_type="freshness_urgent",
            severity="warn",
            message=f"{r['c']} nội dung freshness urgent — cần refresh.",
            link=f"/crm/seo/content?customer_id={cid}",
        )
        if aid:
            created.append({"id": aid, "type": "freshness_urgent"})

    return created
