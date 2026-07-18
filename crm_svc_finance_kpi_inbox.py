"""Đồng bộ cảnh báo KPI finance → crm_reminders (inbox Hub)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from crm_svc_finance_kpi import collect_finance_kpi_alerts

SCOPE_FINANCE_KPI = "finance_kpi"
KIND_KPI_ALERT = "kpi_alert"


def period_ref_id(year: int, month: int) -> int:
    return int(year) * 100 + int(month)


def _parse_meta(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(str(raw or "") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def sync_finance_kpi_inbox(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    alerts_result: dict[str, Any] | None = None,
    dashboard_url: str = "",
) -> dict[str, Any]:
    """
    Upsert pending reminders scope=finance_kpi theo alert_id tháng.

    Xoá pending cũ không còn trong cohort alert hiện tại.
    """
    data = alerts_result or collect_finance_kpi_alerts(conn, year=year, month=month)
    alerts = list(data.get("alerts") or [])
    period_ref = period_ref_id(year, month)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    dash = dashboard_url or f"/crm/business-dashboard?year={int(year)}&month={int(month)}"
    current_ids = {str(a.get("id") or "") for a in alerts if a.get("id")}

    rows = conn.execute(
        """
        SELECT id, meta_json FROM crm_reminders
        WHERE scope = ? AND ref_id = ? AND reminder_kind = ? AND status = 'pending'
        """,
        (SCOPE_FINANCE_KPI, period_ref, KIND_KPI_ALERT),
    ).fetchall()

    existing: dict[str, int] = {}
    for row in rows:
        meta = _parse_meta(row["meta_json"])
        aid = str(meta.get("alert_id") or "")
        if aid:
            existing[aid] = int(row["id"])

    removed = 0
    for aid, rid in list(existing.items()):
        if aid not in current_ids:
            conn.execute("DELETE FROM crm_reminders WHERE id = ?", (rid,))
            removed += 1

    synced = 0
    for alert in alerts:
        aid = str(alert.get("id") or "")
        if not aid:
            continue
        critical = str(alert.get("level") or "") == "critical"
        prefix = "[NGHIÊM TRỌNG]" if critical else "[Cảnh báo]"
        title = f"{prefix} {alert.get('title') or 'KPI'} — {int(month):02d}/{int(year)}"
        body = str(alert.get("message") or "")
        meta = json.dumps(
            {
                "alert_id": aid,
                "level": alert.get("level"),
                "category": alert.get("category"),
                "year": int(year),
                "month": int(month),
                "dashboard_url": dash,
                "metric_key": alert.get("metric_key"),
                "metric_value": alert.get("metric_value"),
            },
            ensure_ascii=False,
        )
        if aid in existing:
            conn.execute(
                """
                UPDATE crm_reminders
                SET title = ?, body = ?, meta_json = ?, remind_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, body, meta, today, ts, existing[aid]),
            )
        else:
            conn.execute(
                """
                INSERT INTO crm_reminders (
                    scope, ref_id, reminder_kind, title, body, remind_at,
                    status, staff_id, meta_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, ?, ?, ?)
                """,
                (
                    SCOPE_FINANCE_KPI,
                    period_ref,
                    KIND_KPI_ALERT,
                    title,
                    body,
                    today,
                    meta,
                    ts,
                    ts,
                ),
            )
        synced += 1

    conn.commit()
    return {
        "year": int(year),
        "month": int(month),
        "period_ref": period_ref,
        "synced": synced,
        "removed": removed,
        "alert_count": len(alerts),
    }


def get_finance_kpi_inbox_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT id, title, body, remind_at, status, meta_json
        FROM crm_reminders
        WHERE scope = ? AND reminder_kind = ? AND status = 'pending'
        ORDER BY remind_at ASC, id ASC
        LIMIT 100
        """,
        (SCOPE_FINANCE_KPI, KIND_KPI_ALERT),
    ).fetchall()
    items: list[dict[str, Any]] = []
    critical = 0
    warning = 0
    for row in rows:
        d = dict(row)
        meta = _parse_meta(d.get("meta_json"))
        level = str(meta.get("level") or "")
        if level == "critical":
            critical += 1
        else:
            warning += 1
        items.append(
            {
                "id": int(d["id"]),
                "title": d.get("title") or "",
                "body": d.get("body") or "",
                "remind_at": d.get("remind_at") or "",
                "level": level,
                "dashboard_url": meta.get("dashboard_url") or "",
                "year": meta.get("year"),
                "month": meta.get("month"),
            }
        )
    return {
        "pending_count": len(items),
        "critical_count": critical,
        "warning_count": warning,
        "items": items,
    }
