"""Lưu trữ báo cáo công việc hàng ngày — CRM PTT."""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def ensure_daily_work_report_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_daily_work_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
            report_date TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            tomorrow_plan TEXT NOT NULL DEFAULT '',
            hours_worked REAL,
            support_needed TEXT NOT NULL DEFAULT '',
            tasks_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'submitted',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(staff_id, report_date)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_dwr_staff_date "
        "ON crm_daily_work_reports(staff_id, report_date DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_dwr_date "
        "ON crm_daily_work_reports(report_date DESC)"
    )


def validate_report_date(raw: str | None) -> str | None:
    s = str(raw or "").strip()
    if not _DATE_RE.match(s):
        return None
    y, m, d = int(s[:4]), int(s[5:7]), int(s[8:10])
    if y < 2000 or y > 2100 or m < 1 or m > 12 or d < 1 or d > 31:
        return None
    return s


def normalize_tasks(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw[:30]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("task") or "").strip()
        if not title:
            continue
        prog = item.get("progress_pct")
        try:
            progress = int(prog) if prog is not None and str(prog).strip() != "" else None
            if progress is not None:
                progress = max(0, min(100, progress))
        except (TypeError, ValueError):
            progress = None
        out.append(
            {
                "time_slot": str(item.get("time_slot") or "").strip()[:40],
                "title": title[:300],
                "detail": str(item.get("detail") or "").strip()[:2000],
                "related": str(item.get("related") or item.get("case_ref") or "").strip()[:200],
                "progress_pct": progress,
                "result": str(item.get("result") or "").strip()[:500],
                "note": str(item.get("note") or "").strip()[:500],
            }
        )
    return out


def daily_work_report_row_to_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    tasks_raw = d.get("tasks_json") or "[]"
    try:
        tasks = json.loads(tasks_raw) if isinstance(tasks_raw, str) else tasks_raw
    except json.JSONDecodeError:
        tasks = []
    if not isinstance(tasks, list):
        tasks = []
    hw = d.get("hours_worked")
    try:
        hours = float(hw) if hw is not None and str(hw).strip() != "" else None
    except (TypeError, ValueError):
        hours = None
    return {
        "id": int(d["id"]),
        "staff_id": int(d["staff_id"]),
        "staff_name": str(d.get("staff_name") or ""),
        "staff_code": str(d.get("staff_code") or ""),
        "department": str(d.get("department") or ""),
        "job_title": str(d.get("job_title") or ""),
        "report_date": str(d.get("report_date") or ""),
        "summary": str(d.get("summary") or ""),
        "tomorrow_plan": str(d.get("tomorrow_plan") or ""),
        "hours_worked": hours,
        "support_needed": str(d.get("support_needed") or ""),
        "tasks": tasks,
        "status": str(d.get("status") or "submitted"),
        "created_at": str(d.get("created_at") or ""),
        "updated_at": str(d.get("updated_at") or ""),
    }


def fetch_daily_work_reports(
    conn: sqlite3.Connection,
    *,
    staff_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[Any] = []
    if staff_id is not None:
        clauses.append("r.staff_id = ?")
        params.append(int(staff_id))
    if date_from:
        clauses.append("r.report_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("r.report_date <= ?")
        params.append(date_to)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    lim = max(1, min(int(limit), 500))
    off = max(0, int(offset))
    return conn.execute(
        f"""
        SELECT r.*,
               s.name AS staff_name,
               s.internal_code AS staff_code,
               s.department AS department,
               s.job_title AS job_title
        FROM crm_daily_work_reports r
        JOIN crm_staff s ON s.id = r.staff_id
        {where}
        ORDER BY r.report_date DESC, r.updated_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, lim, off),
    ).fetchall()


def fetch_daily_work_report_by_id(conn: sqlite3.Connection, report_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT r.*,
               s.name AS staff_name,
               s.internal_code AS staff_code,
               s.department AS department,
               s.job_title AS job_title
        FROM crm_daily_work_reports r
        JOIN crm_staff s ON s.id = r.staff_id
        WHERE r.id = ?
        """,
        (int(report_id),),
    ).fetchone()


def fetch_daily_work_report_by_staff_date(
    conn: sqlite3.Connection, *, staff_id: int, report_date: str
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT r.*,
               s.name AS staff_name,
               s.internal_code AS staff_code,
               s.department AS department,
               s.job_title AS job_title
        FROM crm_daily_work_reports r
        JOIN crm_staff s ON s.id = r.staff_id
        WHERE r.staff_id = ? AND r.report_date = ?
        """,
        (int(staff_id), report_date),
    ).fetchone()


def update_daily_work_report_by_id(
    conn: sqlite3.Connection,
    report_id: int,
    *,
    report_date: str,
    summary: str,
    tomorrow_plan: str,
    hours_worked: float | None,
    support_needed: str,
    tasks: list[dict[str, Any]],
    status: str,
    staff_id: int | None = None,
    ts: str,
) -> sqlite3.Row:
    tasks_json = json.dumps(tasks, ensure_ascii=False)
    st = str(status or "submitted").strip().lower()
    if st not in ("draft", "submitted"):
        st = "submitted"
    if staff_id is not None:
        clash = conn.execute(
            """
            SELECT id FROM crm_daily_work_reports
            WHERE staff_id = ? AND report_date = ? AND id != ?
            """,
            (int(staff_id), report_date, int(report_id)),
        ).fetchone()
        if clash:
            raise ValueError("Đã có báo cáo khác cùng ngày cho nhân viên này.")
        conn.execute(
            """
            UPDATE crm_daily_work_reports SET
                staff_id = ?, report_date = ?, summary = ?, tomorrow_plan = ?,
                hours_worked = ?, support_needed = ?, tasks_json = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                int(staff_id),
                report_date,
                summary,
                tomorrow_plan,
                hours_worked,
                support_needed,
                tasks_json,
                st,
                ts,
                int(report_id),
            ),
        )
    else:
        prev = conn.execute(
            "SELECT staff_id FROM crm_daily_work_reports WHERE id = ?",
            (int(report_id),),
        ).fetchone()
        if prev is None:
            raise ValueError("Không tìm thấy báo cáo")
        sid = int(prev["staff_id"])
        clash = conn.execute(
            """
            SELECT id FROM crm_daily_work_reports
            WHERE staff_id = ? AND report_date = ? AND id != ?
            """,
            (sid, report_date, int(report_id)),
        ).fetchone()
        if clash:
            raise ValueError("Đã có báo cáo khác cùng ngày cho nhân viên này.")
        conn.execute(
            """
            UPDATE crm_daily_work_reports SET
                report_date = ?, summary = ?, tomorrow_plan = ?,
                hours_worked = ?, support_needed = ?, tasks_json = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                report_date,
                summary,
                tomorrow_plan,
                hours_worked,
                support_needed,
                tasks_json,
                st,
                ts,
                int(report_id),
            ),
        )
    row = fetch_daily_work_report_by_id(conn, int(report_id))
    assert row is not None
    return row


def upsert_daily_work_report(
    conn: sqlite3.Connection,
    *,
    staff_id: int,
    report_date: str,
    summary: str,
    tomorrow_plan: str,
    hours_worked: float | None,
    support_needed: str,
    tasks: list[dict[str, Any]],
    status: str,
    ts: str,
) -> sqlite3.Row:
    tasks_json = json.dumps(tasks, ensure_ascii=False)
    st = str(status or "submitted").strip().lower()
    if st not in ("draft", "submitted"):
        st = "submitted"
    existing = conn.execute(
        "SELECT id FROM crm_daily_work_reports WHERE staff_id = ? AND report_date = ?",
        (int(staff_id), report_date),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE crm_daily_work_reports SET
                summary = ?, tomorrow_plan = ?, hours_worked = ?,
                support_needed = ?, tasks_json = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                summary,
                tomorrow_plan,
                hours_worked,
                support_needed,
                tasks_json,
                st,
                ts,
                int(existing["id"]),
            ),
        )
        rid = int(existing["id"])
    else:
        cur = conn.execute(
            """
            INSERT INTO crm_daily_work_reports (
                staff_id, report_date, summary, tomorrow_plan, hours_worked,
                support_needed, tasks_json, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(staff_id),
                report_date,
                summary,
                tomorrow_plan,
                hours_worked,
                support_needed,
                tasks_json,
                st,
                ts,
                ts,
            ),
        )
        rid = int(cur.lastrowid)
    row = fetch_daily_work_report_by_id(conn, rid)
    assert row is not None
    return row
