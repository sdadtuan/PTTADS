# crm_svc_risk.py
"""Risk management per-lifecycle cho 12 dịch vụ PTTP."""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)
_HAIKU = "claude-haiku-4-5-20251001"


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_risks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            stage        TEXT NOT NULL DEFAULT '',
            title        TEXT NOT NULL DEFAULT '',
            category     TEXT NOT NULL DEFAULT '',
            probability  TEXT NOT NULL DEFAULT 'trung',
            impact       TEXT NOT NULL DEFAULT 'trung',
            mitigation   TEXT NOT NULL DEFAULT '',
            is_active    INTEGER NOT NULL DEFAULT 1,
            is_custom    INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL DEFAULT '',
            updated_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_risks_lifecycle ON crm_svc_risks(lifecycle_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_risk_scans (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            ai_output    TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()


def seed_risks(
    conn: sqlite3.Connection, lifecycle_id: int, service_slug: str
) -> int:
    from crm_svc_risk_registry import SERVICE_RISK_REGISTRY
    existing = conn.execute(
        "SELECT COUNT(*) FROM crm_svc_risks WHERE lifecycle_id = ? AND is_custom = 0",
        (lifecycle_id,),
    ).fetchone()[0]
    if existing > 0:
        return 0
    risks = SERVICE_RISK_REGISTRY.get(service_slug, [])
    ts = _ts()
    for risk in risks:
        conn.execute(
            """
            INSERT INTO crm_svc_risks
                (lifecycle_id, stage, title, category, probability, impact,
                 mitigation, is_active, is_custom, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)
            """,
            (
                lifecycle_id,
                risk.get("stage", ""),
                risk["title"],
                risk.get("category", ""),
                risk.get("probability", "trung"),
                risk.get("impact", "trung"),
                risk.get("mitigation", ""),
                ts, ts,
            ),
        )
    conn.commit()
    return len(risks)


def list_risks(
    conn: sqlite3.Connection, lifecycle_id: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM crm_svc_risks
        WHERE lifecycle_id = ?
        ORDER BY is_active DESC,
                 CASE impact WHEN 'cao' THEN 3 WHEN 'trung' THEN 2 WHEN 'thap' THEN 1 ELSE 0 END DESC,
                 CASE probability WHEN 'cao' THEN 3 WHEN 'trung' THEN 2 WHEN 'thap' THEN 1 ELSE 0 END DESC,
                 id
        """,
        (lifecycle_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def update_risk(
    conn: sqlite3.Connection,
    risk_id: int,
    *,
    probability: str | None = None,
    impact: str | None = None,
    mitigation: str | None = None,
    is_active: bool | None = None,
) -> None:
    ts = _ts()
    sets = ["updated_at = ?"]
    params: list[Any] = [ts]
    if probability is not None:
        sets.append("probability = ?")
        params.append(probability)
    if impact is not None:
        sets.append("impact = ?")
        params.append(impact)
    if mitigation is not None:
        sets.append("mitigation = ?")
        params.append(mitigation[:2000])
    if is_active is not None:
        sets.append("is_active = ?")
        params.append(1 if is_active else 0)
    params.append(risk_id)
    conn.execute(
        f"UPDATE crm_svc_risks SET {', '.join(sets)} WHERE id = ?", params
    )
    conn.commit()


def create_custom_risk(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    stage: str,
    title: str,
    category: str = "",
) -> int:
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_svc_risks
            (lifecycle_id, stage, title, category, probability, impact,
             mitigation, is_active, is_custom, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'trung', 'trung', '', 1, 1, ?, ?)
        """,
        (lifecycle_id, stage, title[:500], category[:100], ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def delete_risk(conn: sqlite3.Connection, risk_id: int) -> bool:
    row = conn.execute(
        "SELECT is_custom FROM crm_svc_risks WHERE id = ?", (risk_id,)
    ).fetchone()
    if row is None or not row["is_custom"]:
        return False
    conn.execute("DELETE FROM crm_svc_risks WHERE id = ?", (risk_id,))
    conn.commit()
    return True


def get_latest_scan(conn: sqlite3.Connection, lifecycle_id: int) -> str:
    row = conn.execute(
        "SELECT ai_output FROM crm_svc_risk_scans "
        "WHERE lifecycle_id = ? ORDER BY id DESC LIMIT 1",
        (lifecycle_id,),
    ).fetchone()
    return row["ai_output"] if row else ""


def run_ai_risk_scan(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    customer_context: dict,
) -> str:
    from crm_svc_risk_registry import AI_RISK_SCAN_PROMPT
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    active_risks = [r for r in list_risks(conn, lifecycle_id) if r["is_active"]]
    if not active_risks:
        return ""
    risk_lines = "\n".join(
        f"- [{r['stage'] or 'tổng'}/{r['category']}] {r['title']} "
        f"(xác suất: {r['probability']}, ảnh hưởng: {r['impact']})"
        for r in active_risks
    )
    ctx = {
        "service_name": customer_context.get("service_name", ""),
        "customer_name": customer_context.get("customer_name", "KH"),
        "current_stage": customer_context.get("current_stage", ""),
        "progress_summary": customer_context.get("progress_summary", ""),
        "risks_list": risk_lines,
    }
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=600,
            messages=[{"role": "user", "content": AI_RISK_SCAN_PROMPT.format(**ctx)}],
        )
        output = response.content[0].text.strip()
        conn.execute(
            "INSERT INTO crm_svc_risk_scans (lifecycle_id, ai_output, created_at) "
            "VALUES (?, ?, ?)",
            (lifecycle_id, output, _ts()),
        )
        conn.commit()
        return output
    except Exception as exc:
        logger.warning("run_ai_risk_scan lỗi lifecycle_id=%s: %s", lifecycle_id, exc)
        return ""
