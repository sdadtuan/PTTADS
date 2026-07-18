from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)
_HAIKU = "claude-haiku-4-5-20251001"

_AM_PROMPT = """Bạn là chuyên gia phân tích hiệu suất nhân sự.

Nhân viên: {staff_name} (vai trò: Account Manager)
Kỳ: tháng {month}/{year}

KPI thực tế:
- Doanh thu thực nhận: {received_revenue:,} VND
- Số dịch vụ đang quản lý: {active_services}
- Biên lợi nhuận trung bình: {avg_margin_pct:.1f}%
- Công nợ tồn đọng: {outstanding:,} VND

Target tháng này:
- Doanh thu: {target_received_revenue:,} VND
- Số dịch vụ: {target_active_services}
- Biên lợi nhuận: {target_avg_margin_pct:.1f}%

Phân tích ngắn gọn (tối đa 200 từ):
1. So sánh actual vs target, highlight gap lớn nhất
2. Đánh giá điểm mạnh và điểm cần cải thiện
3. Gợi ý 2-3 hành động cụ thể cho tháng tới"""

_SP_PROMPT = """Bạn là chuyên gia phân tích hiệu suất nhân sự.

Nhân viên: {staff_name} (vai trò: Specialist/Thực thi)
Kỳ: tháng {month}/{year}

KPI thực tế:
- Tasks hoàn thành: {tasks_completed}
- Tasks đang chờ: {tasks_pending}
- Rủi ro đã xử lý: {risks_resolved}

Target tháng này:
- Tasks hoàn thành: {target_tasks_completed}
- Rủi ro xử lý: {target_risks_resolved}

Phân tích ngắn gọn (tối đa 200 từ):
1. So sánh actual vs target, highlight gap lớn nhất
2. Đánh giá tốc độ xử lý và backlog
3. Gợi ý 2-3 hành động ưu tiên cho tháng tới"""

_AM_LEAD_PROMPT = """Bạn là chuyên gia phân tích hiệu suất pre-sales (Lead → Consult → Proposal).

Nhân viên: {staff_name} (Account Manager — giai đoạn Lead)
Kỳ: tháng {month}/{year}

KPI Lead thực tế (nội bộ, trước HĐ):
- Intake hoàn thành: {lead_intake_completed}
- Intake gọi ≤48h: {lead_phone_within_48h_pct:.1f}% ({lead_phone_within_48h_num}/{lead_phone_within_48h_denom})
- Quyết định Go: {lead_go_decisions}
- Go → Consult: {lead_to_consult_pct:.1f}% ({lead_to_consult_num}/{lead_to_consult_denom})
- Chi phí pre-sales tháng: {presales_cost_vnd:,} VND
- Chi phí / Go (ước tính): {presales_cost_per_go_vnd:,} VND
- TB phút gọi Intake: {lead_avg_phone_minutes:.1f}

Target tháng:
- Intake hoàn thành: {target_lead_intake_completed}
- Intake gọi ≤48h: {target_lead_phone_within_48h_pct:.1f}%
- Go → Consult: {target_lead_to_consult_pct:.1f}%
- Cap chi phí pre-sales: {target_presales_cost_vnd:,} VND
- Lead đang vượt cap: {presales_over_cap_count}

Phân tích ngắn gọn (tối đa 220 từ):
1. So sánh actual vs target — metric lệch nhiều nhất
2. Đánh giá tốc độ intake và chuyển Go → Consult
3. Gợi ý 2-3 hành động giảm chi phí/Go và cải thiện funnel pre-sales
4. Nếu có lead vượt cap — gợi ý giảm chi phí hoặc xin tăng cap với Sales lead"""


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_kpi_targets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id     INTEGER NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
            role         TEXT NOT NULL DEFAULT 'am',
            metric_key   TEXT NOT NULL DEFAULT '',
            year         INTEGER NOT NULL,
            month        INTEGER NOT NULL,
            target_value REAL NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL DEFAULT '',
            updated_at   TEXT NOT NULL DEFAULT '',
            UNIQUE(staff_id, metric_key, year, month)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_kpi_targets "
        "ON crm_svc_kpi_targets(staff_id, year, month)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_kpi_scans (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id   INTEGER NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
            ai_output  TEXT NOT NULL DEFAULT '',
            role       TEXT NOT NULL DEFAULT 'am',
            year       INTEGER NOT NULL,
            month      INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_kpi_scans "
        "ON crm_svc_kpi_scans(staff_id, role, year, month)"
    )
    conn.commit()


def get_am_metrics(
    conn: sqlite3.Connection, staff_id: int, year: int, month: int
) -> dict[str, Any]:
    month_str = f"{year:04d}-{month:02d}"

    recv_row = conn.execute(
        """
        SELECT COALESCE(SUM(p.amount_vnd), 0)
        FROM crm_svc_payments p
        JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
        WHERE lc.assigned_am = ? AND p.status = 'received' AND p.received_on LIKE ?
        """,
        (staff_id, f"{month_str}%"),
    ).fetchone()
    received_revenue = int(recv_row[0])

    lcs = conn.execute(
        """
        SELECT lc.id, COALESCE(ct.amount_vnd, 0) AS contract_amount
        FROM crm_service_lifecycle lc
        LEFT JOIN crm_contracts ct ON ct.id = lc.contract_id
        WHERE lc.assigned_am = ? AND lc.status = 'active'
        """,
        (staff_id,),
    ).fetchall()

    active_services = len(lcs)
    total_margin = 0.0
    total_outstanding = 0

    for lc in lcs:
        lc_id = int(lc[0])
        contract_amount = int(lc[1])

        pay = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN status='received' THEN amount_vnd ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN status='pending'  THEN amount_vnd ELSE 0 END), 0)
            FROM crm_svc_payments WHERE lifecycle_id = ?
            """,
            (lc_id,),
        ).fetchone()
        recv = int(pay[0])

        exp = int(
            conn.execute(
                f"SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_expenses "
                f"WHERE lifecycle_id = ? AND COALESCE(NULLIF(cost_phase, ''), 'delivery') = 'delivery'",
                (lc_id,),
            ).fetchone()[0]
        )

        profit = recv - exp
        margin = (profit / recv * 100) if recv > 0 else 0.0
        total_margin += margin
        total_outstanding += max(0, contract_amount - recv)

    avg_margin_pct = round(total_margin / active_services, 2) if active_services > 0 else 0.0

    return {
        "received_revenue": received_revenue,
        "active_services": active_services,
        "avg_margin_pct": avg_margin_pct,
        "outstanding": total_outstanding,
    }


def get_sp_metrics(
    conn: sqlite3.Connection, staff_id: int, year: int, month: int
) -> dict[str, Any]:
    month_str = f"{year:04d}-{month:02d}"

    tasks_row = conn.execute(
        """
        SELECT COUNT(*) FROM crm_svc_tasks
        WHERE done_by = ? AND is_done = 1 AND updated_at LIKE ?
        """,
        (staff_id, f"{month_str}%"),
    ).fetchone()
    tasks_completed = int(tasks_row[0])

    pending_row = conn.execute(
        """
        SELECT COUNT(*) FROM crm_svc_tasks t
        JOIN crm_service_lifecycle lc ON lc.id = t.lifecycle_id
        WHERE lc.assigned_sp = ? AND t.is_done = 0
        """,
        (staff_id,),
    ).fetchone()
    tasks_pending = int(pending_row[0])

    risks_row = conn.execute(
        """
        SELECT COUNT(*) FROM crm_svc_risks r
        JOIN crm_service_lifecycle lc ON lc.id = r.lifecycle_id
        WHERE lc.assigned_sp = ? AND r.is_active = 0 AND r.updated_at LIKE ?
        """,
        (staff_id, f"{month_str}%"),
    ).fetchone()
    risks_resolved = int(risks_row[0])

    return {
        "tasks_completed": tasks_completed,
        "tasks_pending": tasks_pending,
        "risks_resolved": risks_resolved,
    }


def get_lifecycle_staff_metrics(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, Any]:
    lc = conn.execute(
        "SELECT assigned_am, assigned_sp FROM crm_service_lifecycle WHERE id = ?",
        (lifecycle_id,),
    ).fetchone()
    if lc is None:
        return {"am": None, "sp": None}

    am_id = lc["assigned_am"]
    sp_id = lc["assigned_sp"]

    def _staff_name(sid: int | None) -> str | None:
        if sid is None:
            return None
        row = conn.execute("SELECT name FROM crm_staff WHERE id = ?", (sid,)).fetchone()
        return row["name"] if row else None

    am = None
    if am_id:
        tasks_done = int(
            conn.execute(
                "SELECT COUNT(*) FROM crm_svc_tasks WHERE lifecycle_id = ? AND is_done = 1",
                (lifecycle_id,),
            ).fetchone()[0]
        )
        rev = int(
            conn.execute(
                "SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_payments "
                "WHERE lifecycle_id = ? AND status = 'received'",
                (lifecycle_id,),
            ).fetchone()[0]
        )
        am = {"id": am_id, "name": _staff_name(am_id), "tasks_done": tasks_done, "received_revenue": rev}

    sp = None
    if sp_id:
        tasks_done_sp = int(
            conn.execute(
                "SELECT COUNT(*) FROM crm_svc_tasks "
                "WHERE lifecycle_id = ? AND is_done = 1 AND done_by = ?",
                (lifecycle_id, sp_id),
            ).fetchone()[0]
        )
        risks_resolved = int(
            conn.execute(
                "SELECT COUNT(*) FROM crm_svc_risks WHERE lifecycle_id = ? AND is_active = 0",
                (lifecycle_id,),
            ).fetchone()[0]
        )
        sp = {
            "id": sp_id,
            "name": _staff_name(sp_id),
            "tasks_done": tasks_done_sp,
            "risks_resolved": risks_resolved,
        }

    return {"am": am, "sp": sp}


def set_target(
    conn: sqlite3.Connection,
    staff_id: int,
    role: str,
    metric_key: str,
    year: int,
    month: int,
    target_value: float,
) -> None:
    ts = _ts()
    conn.execute(
        """
        INSERT INTO crm_svc_kpi_targets
            (staff_id, role, metric_key, year, month, target_value, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(staff_id, metric_key, year, month)
        DO UPDATE SET target_value = excluded.target_value, updated_at = excluded.updated_at
        """,
        (staff_id, role, metric_key, year, month, target_value, ts, ts),
    )
    conn.commit()


def get_targets(
    conn: sqlite3.Connection, staff_id: int, year: int, month: int
) -> dict[str, float]:
    rows = conn.execute(
        "SELECT metric_key, target_value FROM crm_svc_kpi_targets "
        "WHERE staff_id = ? AND year = ? AND month = ?",
        (staff_id, year, month),
    ).fetchall()
    return {r["metric_key"]: r["target_value"] for r in rows}


def get_latest_kpi_scan(
    conn: sqlite3.Connection, staff_id: int, role: str, year: int, month: int
) -> str:
    row = conn.execute(
        "SELECT ai_output FROM crm_svc_kpi_scans "
        "WHERE staff_id = ? AND role = ? AND year = ? AND month = ? "
        "ORDER BY id DESC LIMIT 1",
        (staff_id, role, year, month),
    ).fetchone()
    return row["ai_output"] if row else ""


def get_staff_kpi_readiness(
    conn: sqlite3.Connection, staff_id: int
) -> dict[str, Any]:
    """Chẩn đoán vì sao KPI AM/Lead có thể đang = 0 — dùng banner trên /crm/staff-kpi."""
    sid = int(staff_id)

    def _scalar(sql: str, params: tuple[Any, ...] = ()) -> int:
        row = conn.execute(sql, params).fetchone()
        return int(row[0] if row else 0)

    leads_owned = _scalar(
        "SELECT COUNT(*) FROM crm_leads WHERE owner_id = ?", (sid,)
    )
    lifecycles_as_am = _scalar(
        "SELECT COUNT(*) FROM crm_service_lifecycle WHERE assigned_am = ?", (sid,)
    )
    lifecycles_on_owned_leads = _scalar(
        """
        SELECT COUNT(*) FROM crm_service_lifecycle lc
        INNER JOIN crm_leads l ON l.id = lc.lead_id
        WHERE l.owner_id = ?
        """,
        (sid,),
    )
    pending_am_sync = _scalar(
        """
        SELECT COUNT(*) FROM crm_service_lifecycle lc
        INNER JOIN crm_leads l ON l.id = lc.lead_id
        WHERE l.owner_id = ?
          AND (lc.assigned_am IS NULL OR lc.assigned_am != l.owner_id)
        """,
        (sid,),
    )

    presales_on_owned_leads = 0
    try:
        presales_on_owned_leads = _scalar(
            """
            SELECT COUNT(*) FROM crm_lead_presales ps
            INNER JOIN crm_leads l ON l.id = ps.lead_id
            WHERE l.owner_id = ?
            """,
            (sid,),
        )
    except sqlite3.OperationalError:
        pass

    intake_completed = 0
    try:
        intake_completed = _scalar(
            """
            SELECT COUNT(*) FROM crm_lead_intake_sessions s
            LEFT JOIN crm_service_lifecycle lc ON lc.id = s.lifecycle_id
            LEFT JOIN crm_leads l ON l.id = COALESCE(s.lead_id, lc.lead_id)
            WHERE s.status = 'completed'
              AND (l.owner_id = ? OR lc.assigned_am = ?)
            """,
            (sid, sid),
        )
    except sqlite3.OperationalError:
        pass

    lead_ids = [
        int(r[0])
        for r in conn.execute(
            "SELECT id FROM crm_leads WHERE owner_id = ? ORDER BY id DESC LIMIT 8",
            (sid,),
        ).fetchall()
    ]

    show_gap_banner = (
        leads_owned > 0
        and lifecycles_as_am == 0
        and lifecycles_on_owned_leads == 0
    )
    show_presales_hint = (
        leads_owned > 0
        and presales_on_owned_leads == 0
        and intake_completed == 0
    )

    return {
        "leads_owned": leads_owned,
        "lifecycles_as_am": lifecycles_as_am,
        "lifecycles_on_owned_leads": lifecycles_on_owned_leads,
        "pending_am_sync": pending_am_sync,
        "presales_on_owned_leads": presales_on_owned_leads,
        "intake_completed": intake_completed,
        "lead_ids": lead_ids,
        "show_gap_banner": show_gap_banner,
        "show_presales_hint": show_presales_hint,
    }


def run_ai_kpi_scan(
    conn: sqlite3.Connection,
    staff_id: int,
    role: str,
    year: int,
    month: int,
    context: dict,
) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    prompt_template = _AM_PROMPT if role == "am" else _SP_PROMPT
    try:
        prompt = prompt_template.format(**context)
    except (KeyError, ValueError):
        return ""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        output = response.content[0].text.strip()
        conn.execute(
            "INSERT INTO crm_svc_kpi_scans "
            "(staff_id, ai_output, role, year, month, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (staff_id, output, role, year, month, _ts()),
        )
        conn.commit()
        return output
    except Exception as exc:
        logger.warning("run_ai_kpi_scan error staff_id=%s: %s", staff_id, exc)
        return ""


def run_ai_lead_kpi_scan(
    conn: sqlite3.Connection,
    staff_id: int,
    year: int,
    month: int,
    context: dict,
) -> str:
    """AI scan KPI Lead/pre-sales — lưu role am_lead."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    try:
        prompt = _AM_LEAD_PROMPT.format(**context)
    except (KeyError, ValueError):
        return ""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=650,
            messages=[{"role": "user", "content": prompt}],
        )
        output = response.content[0].text.strip()
        conn.execute(
            "INSERT INTO crm_svc_kpi_scans "
            "(staff_id, ai_output, role, year, month, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (staff_id, output, "am_lead", year, month, _ts()),
        )
        conn.commit()
        return output
    except Exception as exc:
        logger.warning("run_ai_lead_kpi_scan error staff_id=%s: %s", staff_id, exc)
        return ""
