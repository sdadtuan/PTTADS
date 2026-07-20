"""Technical SEO — issues, crawl import (Spec 6.5 Phase 3)."""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime
from typing import Any


ISSUE_STATUSES: tuple[str, ...] = (
    "detected",
    "triaged",
    "assigned",
    "in_progress",
    "fixed",
    "verified",
    "closed",
)
SEVERITIES: tuple[str, ...] = ("critical", "high", "medium", "low")


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def list_issues(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    severity: str | None = None,
    status: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM seo_technical_issues WHERE customer_id = ?"
    params: list[Any] = [customer_id]
    if severity:
        sql += " AND severity = ?"
        params.append(severity)
    if status:
        sql += " AND status = ?"
        params.append(status)
    else:
        sql += " AND status NOT IN ('closed', 'verified')"
    sql += " ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def severity_matrix(conn: sqlite3.Connection, customer_id: int) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT severity, COUNT(*) AS c FROM seo_technical_issues
        WHERE customer_id = ? AND status NOT IN ('closed', 'verified')
        GROUP BY severity
        """,
        (customer_id,),
    ).fetchall()
    out = {s: 0 for s in SEVERITIES}
    for r in rows:
        out[str(r["severity"])] = int(r["c"])
    return out


def create_issue(
    conn: sqlite3.Connection,
    customer_id: int,
    payload: dict[str, Any],
    *,
    crm_conn: Any | None = None,
) -> int:
    url = str(payload.get("url") or "").strip()
    issue_type = str(payload.get("issue_type") or "unknown").strip()
    if not url:
        raise ValueError("Thiếu url")
    cur = conn.execute(
        """
        INSERT INTO seo_technical_issues (
            customer_id, url, issue_type, severity, status, description,
            impact_notes, assignee_id, discovered_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            url,
            issue_type,
            str(payload.get("severity") or "medium"),
            str(payload.get("status") or "detected"),
            str(payload.get("description") or ""),
            str(payload.get("impact_notes") or ""),
            payload.get("assignee_id"),
            _ts(),
        ),
    )
    conn.commit()
    iid = int(cur.lastrowid)
    if crm_conn is not None:
        from ptt_seo.technical_tasks import maybe_auto_create_task

        maybe_auto_create_task(
            crm_conn,
            conn,
            iid,
            severity=str(payload.get("severity") or "medium"),
        )
    return iid


def update_issue(conn: sqlite3.Connection, issue_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM seo_technical_issues WHERE id = ?", (issue_id,)).fetchone()
    if row is None:
        raise ValueError("Issue không tồn tại")
    current = dict(row)
    status = str(payload.get("status") or current["status"])
    resolved_at = current.get("resolved_at")
    if status in ("fixed", "verified", "closed") and not resolved_at:
        resolved_at = _ts()
    assignee_id = payload["assignee_id"] if "assignee_id" in payload else current.get("assignee_id")
    conn.execute(
        """
        UPDATE seo_technical_issues SET
            status=?, severity=?, assignee_id=?, description=?, impact_notes=?, resolved_at=?
        WHERE id=?
        """,
        (
            status,
            str(payload.get("severity") or current["severity"]),
            assignee_id,
            str(payload.get("description") or current["description"]),
            str(payload.get("impact_notes") or current["impact_notes"]),
            resolved_at,
            issue_id,
        ),
    )
    conn.commit()
    row2 = conn.execute("SELECT * FROM seo_technical_issues WHERE id = ?", (issue_id,)).fetchone()
    return dict(row2) if row2 else {}


def import_crawl_csv(
    conn: sqlite3.Connection,
    customer_id: int,
    csv_text: str,
    *,
    crm_conn: Any | None = None,
) -> int:
    """Import crawl export: url, issue_type, severity, description."""
    reader = csv.DictReader(io.StringIO(csv_text))
    count = 0
    for row in reader:
        url = (row.get("url") or row.get("URL") or "").strip()
        if not url:
            continue
        create_issue(
            conn,
            customer_id,
            {
                "url": url,
                "issue_type": row.get("issue_type") or row.get("type") or "crawl",
                "severity": row.get("severity") or "medium",
                "description": row.get("description") or row.get("message") or "",
            },
            crm_conn=crm_conn,
        )
        count += 1
    if count:
        try:
            from ptt_seo.crawl_reminder import record_crawl_import

            record_crawl_import(conn, customer_id, count)
        except Exception:
            pass
    return count


def count_open_critical(conn: sqlite3.Connection, customer_id: int | None = None) -> int:
    sql = "SELECT COUNT(*) AS c FROM seo_technical_issues WHERE severity = 'critical' AND status NOT IN ('closed','verified')"
    params: list[Any] = []
    if customer_id is not None:
        sql += " AND customer_id = ?"
        params.append(customer_id)
    row = conn.execute(sql, params).fetchone()
    return int(row["c"] or 0) if row else 0
