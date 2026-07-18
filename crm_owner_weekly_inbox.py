"""Đồng bộ brief dashboard tuần → crm_reminders (Hub)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from crm_owner_weekly_dashboard import RAG_RED, get_owner_weekly_dashboard

SCOPE_OWNER_WEEKLY = "owner_weekly"
KIND_WEEKLY_ALERT = "owner_weekly_alert"


def period_ref_id(iso_year: int, iso_week: int) -> int:
    return int(iso_year) * 100 + int(iso_week)


def _parse_meta(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(str(raw or "") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def sync_owner_weekly_inbox(
    conn: sqlite3.Connection,
    *,
    iso_year: int,
    iso_week: int,
    dashboard: dict[str, Any] | None = None,
    dashboard_url: str = "",
) -> dict[str, Any]:
    """
    Upsert pending reminders scope=owner_weekly theo metric_key tuần.

    Xoá pending cũ không còn trong cohort đỏ/vàng hiện tại.
    """
    dash = dashboard or get_owner_weekly_dashboard(
        conn, year=int(iso_year), iso_week=int(iso_week)
    )
    brief = dash.get("pre_execution") or {}
    actions = list(brief.get("actions") or [])
    period_ref = period_ref_id(iso_year, iso_week)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    week = dash.get("week") or {}
    dash_url = dashboard_url or (
        f"/crm/owner-weekly?year={int(iso_year)}&week={int(iso_week)}"
    )
    current_ids = {
        f"{int(iso_year)}-W{int(iso_week):02d}-{a.get('metric_key') or ''}"
        for a in actions
        if a.get("metric_key")
    }

    rows = conn.execute(
        """
        SELECT id, meta_json FROM crm_reminders
        WHERE scope = ? AND ref_id = ? AND reminder_kind = ? AND status = 'pending'
        """,
        (SCOPE_OWNER_WEEKLY, period_ref, KIND_WEEKLY_ALERT),
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
    for action in actions:
        metric_key = str(action.get("metric_key") or "")
        if not metric_key:
            continue
        alert_id = f"{int(iso_year)}-W{int(iso_week):02d}-{metric_key}"
        is_red = str(action.get("status") or "") == RAG_RED
        prefix = "[ĐỎ · 7 ngày]" if is_red else "[Vàng · theo dõi]"
        week_label = str(week.get("label") or f"Tuần {iso_week}/{iso_year}")
        title = f"{prefix} {action.get('metric_label') or metric_key} — {week_label}"
        body_parts = [str(action.get("hint") or "").strip()]
        steps = action.get("steps") or []
        if steps:
            body_parts.append("Bước: " + " · ".join(str(s) for s in steps[:4]))
        body = "\n".join(p for p in body_parts if p)
        meta = json.dumps(
            {
                "alert_id": alert_id,
                "level": "critical" if is_red else "warning",
                "status": action.get("status"),
                "iso_year": int(iso_year),
                "iso_week": int(iso_week),
                "metric_key": metric_key,
                "block": action.get("block"),
                "dashboard_url": dash_url,
            },
            ensure_ascii=False,
        )
        if alert_id in existing:
            conn.execute(
                """
                UPDATE crm_reminders
                SET title = ?, body = ?, meta_json = ?, remind_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, body, meta, today, ts, existing[alert_id]),
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
                    SCOPE_OWNER_WEEKLY,
                    period_ref,
                    KIND_WEEKLY_ALERT,
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
        "iso_year": int(iso_year),
        "iso_week": int(iso_week),
        "period_ref": period_ref,
        "synced": synced,
        "removed": removed,
        "action_count": len(actions),
        "red_count": int(brief.get("red_count") or 0),
        "yellow_count": int(brief.get("yellow_count") or 0),
    }


def get_owner_weekly_inbox_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT id, title, body, remind_at, status, meta_json
        FROM crm_reminders
        WHERE scope = ? AND reminder_kind = ? AND status = 'pending'
        ORDER BY remind_at ASC, id ASC
        LIMIT 100
        """,
        (SCOPE_OWNER_WEEKLY, KIND_WEEKLY_ALERT),
    ).fetchall()
    items: list[dict[str, Any]] = []
    critical = warning = 0
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
                "iso_year": meta.get("iso_year"),
                "iso_week": meta.get("iso_week"),
                "metric_key": meta.get("metric_key"),
            }
        )
    return {
        "pending_count": len(items),
        "critical_count": critical,
        "warning_count": warning,
        "items": items,
    }
