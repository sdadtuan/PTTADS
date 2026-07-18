"""Pre-sales KPI helpers — chi phí + AM Lead metrics (L1–L4)."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from crm_svc_finance import (
    COST_PHASE_PRESALES,
    list_expenses,
)
from crm_service_lifecycle import stage_index

PRESALES_CATEGORY_LABELS: dict[str, str] = {
    "dien_thoai": "Điện thoại / SIM",
    "di_lai": "Đi lại / gặp KH",
    "cong_lead": "Công AM Lead / Intake",
    "cong_tu_van": "Công Consult (nội bộ)",
    "cong_cu": "Công cụ / phần mềm",
    "khac_presales": "Khác (pre-sales)",
}

PRESALES_PANEL_STAGES: frozenset[str] = frozenset({"lead", "consult", "proposal"})

ENV_PRESALES_COST_CAP = "PTT_PRESALES_COST_CAP_VND"
ENV_PRESALES_CAP_STRICT = "PTT_PRESALES_CAP_STRICT"


class PresalesCapExceededError(ValueError):
    """Chi phí pre-sales vượt cap — dùng khi PTT_PRESALES_CAP_STRICT=1."""

CONSULT_PLUS_STAGES: frozenset[str] = frozenset({
    "consult",
    "proposal",
    "onboard",
    "deliver",
    "handover",
    "retain",
})

AM_LEAD_METRIC_KEYS: tuple[str, ...] = (
    "lead_intake_completed",
    "lead_phone_within_48h_pct",
    "lead_go_decisions",
    "lead_to_consult_pct",
    "lead_task_done",
    "lead_avg_phone_minutes",
    "presales_cost_vnd",
)

AM_LEAD_METRIC_LABELS: dict[str, str] = {
    "lead_intake_completed": "Intake hoàn thành",
    "lead_phone_within_48h_pct": "Intake gọi ≤48h (%)",
    "lead_go_decisions": "Quyết định Go",
    "lead_to_consult_pct": "Go → Consult (%)",
    "lead_task_done": "Task Lead ✓",
    "lead_avg_phone_minutes": "TB phút gọi Intake",
    "presales_cost_vnd": "Chi phí pre-sales",
}


def _month_prefix(year: int, month: int) -> str:
    return f"{int(year):04d}-{int(month):02d}"


def _parse_ts(raw: str | None) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    for fmt, length in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(text[:length], fmt)
        except ValueError:
            continue
    return None


def _hours_between(start: str | None, end: str | None) -> float | None:
    a = _parse_ts(start)
    b = _parse_ts(end)
    if a is None or b is None:
        return None
    return (b - a).total_seconds() / 3600.0


def show_presales_panel(lifecycle: dict[str, Any]) -> bool:
    """Panel pre-sales trên workflow — draft hoặc stage trước Onboard."""
    stage = str(lifecycle.get("stage") or "lead")
    status = str(lifecycle.get("status") or "draft")
    if status in ("closed", "lost"):
        return False
    if status == "draft":
        return True
    return stage in PRESALES_PANEL_STAGES


def get_presales_cost_summary(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, Any]:
    """Tổng chi phí pre-sales + breakdown theo category."""
    rows = list_expenses(conn, lifecycle_id, cost_phase=COST_PHASE_PRESALES)
    total = sum(int(r.get("amount_vnd") or 0) for r in rows)
    by_cat: dict[str, int] = {}
    for r in rows:
        cat = str(r.get("category") or "khac_presales")
        by_cat[cat] = by_cat.get(cat, 0) + int(r.get("amount_vnd") or 0)
    by_category = [
        {
            "category": cat,
            "label": PRESALES_CATEGORY_LABELS.get(cat, cat),
            "amount_vnd": amt,
        }
        for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1])
    ]
    return {
        "lifecycle_id": int(lifecycle_id),
        "total_presales_vnd": total,
        "expense_count": len(rows),
        "by_category": by_category,
        "recent_expenses": rows[:5],
        **get_presales_cap_alert(conn, lifecycle_id),
    }


def get_presales_cost_summary_by_presales(
    conn: sqlite3.Connection, presales_id: int
) -> dict[str, Any]:
    """Tổng chi phí pre-sales trên lead (L3.2) — trước/sau promote."""
    from crm_svc_finance import list_presales_expenses

    pid = int(presales_id)
    rows = list_presales_expenses(conn, pid)
    total = sum(int(r.get("amount_vnd") or 0) for r in rows)
    by_cat: dict[str, int] = {}
    for r in rows:
        cat = str(r.get("category") or "khac_presales")
        by_cat[cat] = by_cat.get(cat, 0) + int(r.get("amount_vnd") or 0)
    by_category = [
        {
            "category": cat,
            "label": PRESALES_CATEGORY_LABELS.get(cat, cat),
            "amount_vnd": amt,
        }
        for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1])
    ]
    ps = conn.execute(
        "SELECT lead_id FROM crm_lead_presales WHERE id = ?", (pid,)
    ).fetchone()
    lead_id = int(ps["lead_id"]) if ps and ps["lead_id"] else None
    return {
        "presales_id": pid,
        "lead_id": lead_id,
        "total_presales_vnd": total,
        "expense_count": len(rows),
        "by_category": by_category,
        "recent_expenses": rows[:8],
        **get_presales_cap_alert_for_presales(conn, pid),
    }


def _presales_on_lead_metrics_enabled(conn: sqlite3.Connection) -> bool:
    """Bật nhánh KPI theo lead_id khi flag PTT_PRESALES_ON_LEAD và schema có sẵn."""
    try:
        from crm_lead_presales import presales_on_lead_enabled
    except ImportError:
        return False
    if not presales_on_lead_enabled():
        return False
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='crm_lead_presales'"
    ).fetchone()
    return row is not None


def _intake_am_scope_sql() -> str:
    """JOIN + WHERE gán session Intake cho AM (lifecycle draft hoặc presales-on-lead)."""
    return """
        LEFT JOIN crm_service_lifecycle lc ON lc.id = s.lifecycle_id
        LEFT JOIN crm_leads l ON l.id = COALESCE(s.lead_id, lc.lead_id)
        LEFT JOIN crm_lead_presales ps ON ps.lead_id = l.id
            AND ps.status IN ('active', 'converted')
        WHERE (
            (s.lifecycle_id IS NOT NULL AND lc.assigned_am = ?)
            OR (
                COALESCE(s.lead_id, lc.lead_id) IS NOT NULL
                AND COALESCE(ps.assigned_am, l.owner_id) = ?
            )
        )
    """


def _presales_consult_reached_sql(alias: str = "ps") -> str:
    return (
        f"({alias}.stage IN ('consult', 'proposal') "
        f"OR {alias}.status = 'converted')"
    )


def _lead_phone_within_48h(
    conn: sqlite3.Connection,
    staff_id: int,
    month_str: str,
    *,
    presales_on_lead: bool,
) -> tuple[int, int]:
    """Trả (numerator, denominator) cho metric gọi ≤48h."""
    sid = int(staff_id)
    month_pattern = f"{month_str}%"
    entities: list[tuple[str, int, str]] = []

    if presales_on_lead:
        lead_rows = conn.execute(
            """
            SELECT l.id, l.created_at
            FROM crm_leads l
            LEFT JOIN crm_lead_presales ps ON ps.lead_id = l.id
                AND ps.status IN ('active', 'converted')
            WHERE l.created_at LIKE ?
              AND COALESCE(ps.assigned_am, l.owner_id) = ?
            """,
            (month_pattern, sid),
        ).fetchall()
        for row in lead_rows:
            entities.append((str(row[1]), int(row[0]), "lead"))

    if presales_on_lead:
        lc_rows = conn.execute(
            """
            SELECT id, created_at, lead_id FROM crm_service_lifecycle
            WHERE assigned_am = ? AND created_at LIKE ?
            """,
            (sid, month_pattern),
        ).fetchall()
        lead_keys = {key for _, key, kind in entities if kind == "lead"}
        for lc in lc_rows:
            lead_id = lc[2]
            if lead_id and int(lead_id) in lead_keys:
                continue
            entities.append((str(lc[1]), int(lc[0]), "lifecycle"))
    else:
        lc_rows = conn.execute(
            """
            SELECT id, created_at FROM crm_service_lifecycle
            WHERE assigned_am = ? AND created_at LIKE ?
            """,
            (sid, month_pattern),
        ).fetchall()
        for lc in lc_rows:
            entities.append((str(lc[1]), int(lc[0]), "lifecycle"))

    phone_num = 0
    for created_at, key, kind in entities:
        if kind == "lead":
            sess = conn.execute(
                """
                SELECT completed_at FROM crm_lead_intake_sessions
                WHERE lead_id = ? AND mode = 'phone' AND status = 'completed'
                  AND completed_at != ''
                ORDER BY completed_at ASC LIMIT 1
                """,
                (key,),
            ).fetchone()
        else:
            sess = conn.execute(
                """
                SELECT completed_at FROM crm_lead_intake_sessions
                WHERE lifecycle_id = ? AND mode = 'phone' AND status = 'completed'
                  AND completed_at != ''
                ORDER BY completed_at ASC LIMIT 1
                """,
                (key,),
            ).fetchone()
        if sess is None:
            continue
        hrs = _hours_between(created_at, sess[0])
        if hrs is not None and 0 <= hrs <= 48:
            phone_num += 1
    return phone_num, len(entities)


def get_am_lead_metrics(
    conn: sqlite3.Connection, staff_id: int, year: int, month: int
) -> dict[str, Any]:
    """Actuals KPI Lead/pre-sales cho AM — tháng Y-M, filter assigned_am."""
    month_str = _month_prefix(year, month)
    sid = int(staff_id)
    month_pattern = f"{month_str}%"
    presales_on_lead = _presales_on_lead_metrics_enabled(conn)
    scope = _intake_am_scope_sql()

    intake_row = conn.execute(
        f"""
        SELECT COUNT(DISTINCT s.id) FROM crm_lead_intake_sessions s
        {scope if presales_on_lead else '''
        INNER JOIN crm_service_lifecycle lc ON lc.id = s.lifecycle_id
        WHERE lc.assigned_am = ?
        '''}
          AND s.status = 'completed'
          AND s.completed_at LIKE ?
        """,
        (sid, sid, month_pattern) if presales_on_lead else (sid, month_pattern),
    ).fetchone()
    lead_intake_completed = int(intake_row[0] if intake_row else 0)

    go_row = conn.execute(
        f"""
        SELECT COUNT(DISTINCT s.id) FROM crm_lead_intake_sessions s
        {scope if presales_on_lead else '''
        INNER JOIN crm_service_lifecycle lc ON lc.id = s.lifecycle_id
        WHERE lc.assigned_am = ?
        '''}
          AND s.status = 'completed'
          AND s.decision = 'go'
          AND s.completed_at LIKE ?
        """,
        (sid, sid, month_pattern) if presales_on_lead else (sid, month_pattern),
    ).fetchone()
    lead_go_decisions = int(go_row[0] if go_row else 0)

    if presales_on_lead:
        go_consult_sql = f"""
        SELECT COUNT(DISTINCT COALESCE(
            CAST(COALESCE(s.lead_id, lc.lead_id) AS TEXT),
            'lc:' || s.lifecycle_id
        ))
        FROM crm_lead_intake_sessions s
        {scope}
          AND s.status = 'completed'
          AND s.decision = 'go'
          AND s.completed_at LIKE ?
          AND (
            {_presales_consult_reached_sql('ps')}
            OR lc.stage IN (
              'consult','proposal','onboard','deliver','handover','retain'
            )
          )
        """
        go_consult_params: tuple[Any, ...] = (sid, sid, month_pattern)
    else:
        go_consult_sql = """
        SELECT COUNT(DISTINCT s.lifecycle_id)
        FROM crm_lead_intake_sessions s
        INNER JOIN crm_service_lifecycle lc ON lc.id = s.lifecycle_id
        WHERE lc.assigned_am = ?
          AND s.status = 'completed'
          AND s.decision = 'go'
          AND s.completed_at LIKE ?
          AND lc.stage IN (
            'consult','proposal','onboard','deliver','handover','retain'
          )
        """
        go_consult_params = (sid, month_pattern)

    go_consult_row = conn.execute(go_consult_sql, go_consult_params).fetchone()
    go_consult_count = int(go_consult_row[0] if go_consult_row else 0)
    lead_to_consult_pct = round(
        go_consult_count / lead_go_decisions * 100, 1
    ) if lead_go_decisions > 0 else 0.0

    task_row = conn.execute(
        """
        SELECT COUNT(*) FROM crm_service_lifecycle lc
        WHERE lc.assigned_am = ?
          AND EXISTS (
            SELECT 1 FROM crm_svc_tasks t
            WHERE t.lifecycle_id = lc.id AND t.stage = 'lead'
          )
          AND NOT EXISTS (
            SELECT 1 FROM crm_svc_tasks t
            WHERE t.lifecycle_id = lc.id AND t.stage = 'lead' AND t.is_done = 0
          )
          AND (
            SELECT MAX(t.updated_at) FROM crm_svc_tasks t
            WHERE t.lifecycle_id = lc.id AND t.stage = 'lead' AND t.is_done = 1
          ) LIKE ?
        """,
        (sid, month_pattern),
    ).fetchone()
    lead_task_done = int(task_row[0] if task_row else 0)

    if presales_on_lead:
        ps_task_row = conn.execute(
            """
            SELECT COUNT(*) FROM crm_lead_presales ps
            INNER JOIN crm_leads l ON l.id = ps.lead_id
            WHERE COALESCE(ps.assigned_am, l.owner_id) = ?
              AND ps.status IN ('active', 'converted')
              AND EXISTS (
                SELECT 1 FROM crm_lead_presales_tasks t
                WHERE t.presales_id = ps.id AND t.stage = 'lead'
              )
              AND NOT EXISTS (
                SELECT 1 FROM crm_lead_presales_tasks t
                WHERE t.presales_id = ps.id AND t.stage = 'lead' AND t.is_done = 0
              )
              AND (
                SELECT MAX(t.done_at) FROM crm_lead_presales_tasks t
                WHERE t.presales_id = ps.id AND t.stage = 'lead' AND t.is_done = 1
              ) LIKE ?
            """,
            (sid, month_pattern),
        ).fetchone()
        lead_task_done += int(ps_task_row[0] if ps_task_row else 0)

    if presales_on_lead:
        presales_row = conn.execute(
            """
            SELECT COALESCE(SUM(e.amount_vnd), 0)
            FROM crm_svc_expenses e
            LEFT JOIN crm_service_lifecycle lc ON lc.id = e.lifecycle_id
            LEFT JOIN crm_lead_presales ps ON ps.id = e.presales_id
            LEFT JOIN crm_leads l ON l.id = COALESCE(e.lead_id, ps.lead_id, lc.lead_id)
            WHERE e.cost_phase = ?
              AND e.expense_on LIKE ?
              AND (
                (e.lifecycle_id IS NOT NULL AND lc.assigned_am = ?)
                OR (
                  e.lifecycle_id IS NULL
                  AND COALESCE(ps.assigned_am, l.owner_id) = ?
                )
              )
            """,
            (COST_PHASE_PRESALES, month_pattern, sid, sid),
        ).fetchone()
    else:
        presales_row = conn.execute(
            """
            SELECT COALESCE(SUM(e.amount_vnd), 0)
            FROM crm_svc_expenses e
            INNER JOIN crm_service_lifecycle lc ON lc.id = e.lifecycle_id
            WHERE lc.assigned_am = ?
              AND e.cost_phase = ?
              AND e.expense_on LIKE ?
            """,
            (sid, COST_PHASE_PRESALES, month_pattern),
        ).fetchone()
    presales_cost_vnd = int(presales_row[0] if presales_row else 0)

    phone_sessions = conn.execute(
        f"""
        SELECT s.started_at, s.completed_at
        FROM crm_lead_intake_sessions s
        {scope if presales_on_lead else '''
        INNER JOIN crm_service_lifecycle lc ON lc.id = s.lifecycle_id
        WHERE lc.assigned_am = ?
        '''}
          AND s.mode = 'phone'
          AND s.status = 'completed'
          AND s.completed_at LIKE ?
          AND s.started_at != ''
          AND s.completed_at != ''
        """,
        (sid, sid, month_pattern) if presales_on_lead else (sid, month_pattern),
    ).fetchall()
    phone_minutes: list[float] = []
    for row in phone_sessions:
        hrs = _hours_between(row[0], row[1])
        if hrs is not None and hrs >= 0:
            phone_minutes.append(hrs * 60.0)
    lead_avg_phone_minutes = round(
        sum(phone_minutes) / len(phone_minutes), 1
    ) if phone_minutes else 0.0

    phone_num, phone_denom = _lead_phone_within_48h(
        conn, sid, month_str, presales_on_lead=presales_on_lead
    )
    lead_phone_within_48h_pct = round(
        phone_num / phone_denom * 100, 1
    ) if phone_denom > 0 else 0.0

    return {
        "lead_intake_completed": lead_intake_completed,
        "lead_phone_within_48h_pct": lead_phone_within_48h_pct,
        "lead_phone_within_48h_num": phone_num,
        "lead_phone_within_48h_denom": phone_denom,
        "lead_go_decisions": lead_go_decisions,
        "lead_to_consult_pct": lead_to_consult_pct,
        "lead_to_consult_num": go_consult_count,
        "lead_to_consult_denom": lead_go_decisions,
        "lead_task_done": lead_task_done,
        "lead_avg_phone_minutes": lead_avg_phone_minutes,
        "presales_cost_vnd": presales_cost_vnd,
    }


FUNNEL_STAGE_KEYS: tuple[str, ...] = (
    "funnel_entered",
    "funnel_intake_done",
    "funnel_go",
    "funnel_consult",
    "funnel_proposal",
    "funnel_won",
)

FUNNEL_STAGE_LABELS: dict[str, str] = {
    "funnel_entered": "Entered",
    "funnel_intake_done": "Intake",
    "funnel_go": "Go",
    "funnel_consult": "Consult",
    "funnel_proposal": "Proposal",
    "funnel_won": "Won",
}


def _date_end_inclusive(period_end: str) -> str:
    text = str(period_end or "").strip()[:10]
    return f"{text} 23:59:59" if text else text


def _pct(num: int, denom: int) -> float:
    return round(num / denom * 100, 1) if denom > 0 else 0.0


def _latest_intake_decision(
    conn: sqlite3.Connection, lifecycle_id: int
) -> str | None:
    row = conn.execute(
        """
        SELECT decision FROM crm_lead_intake_sessions
        WHERE lifecycle_id = ? AND status = 'completed'
        ORDER BY completed_at DESC, id DESC
        LIMIT 1
        """,
        (int(lifecycle_id),),
    ).fetchone()
    if row is None:
        return None
    decision = str(row[0] or "").strip()
    return decision or None


def _latest_intake_decision_for_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    lifecycle_id: int | None = None,
) -> str | None:
    """Quyết định intake mới nhất trên lead (hoặc lifecycle sau promote)."""
    lid = int(lead_id)
    lc_id = int(lifecycle_id) if lifecycle_id else None
    row = conn.execute(
        """
        SELECT decision FROM crm_lead_intake_sessions
        WHERE status = 'completed'
          AND (lead_id = ? OR (? IS NOT NULL AND lifecycle_id = ?))
        ORDER BY completed_at DESC, id DESC
        LIMIT 1
        """,
        (lid, lc_id, lc_id),
    ).fetchone()
    if row is None:
        return None
    decision = str(row[0] or "").strip()
    return decision or None


def _lead_has_completed_intake(
    conn: sqlite3.Connection,
    lead_id: int,
    lifecycle_id: int | None = None,
) -> bool:
    lid = int(lead_id)
    lc_id = int(lifecycle_id) if lifecycle_id else None
    row = conn.execute(
        """
        SELECT 1 FROM crm_lead_intake_sessions
        WHERE status = 'completed'
          AND (lead_id = ? OR (? IS NOT NULL AND lifecycle_id = ?))
        LIMIT 1
        """,
        (lid, lc_id, lc_id),
    ).fetchone()
    return row is not None


def _stage_first_entered_at(
    conn: sqlite3.Connection, lifecycle_id: int, stage: str
) -> datetime | None:
    row = conn.execute(
        """
        SELECT created_at FROM crm_service_lifecycle_events
        WHERE lifecycle_id = ? AND to_stage = ?
        ORDER BY created_at ASC, id ASC
        LIMIT 1
        """,
        (int(lifecycle_id), stage),
    ).fetchone()
    if row is not None:
        return _parse_ts(row[0])
    lc = conn.execute(
        "SELECT stage, stage_entered_at FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if lc is None:
        return None
    current = str(lc[0])
    if current == stage:
        return _parse_ts(lc[1])
    return None


def _is_funnel_won(lc: dict[str, Any]) -> bool:
    if lc.get("contract_id"):
        return True
    stg = str(lc.get("stage") or "lead")
    status = str(lc.get("status") or "draft")
    return stage_index(stg) >= stage_index("onboard") and status in (
        "active",
        "closed",
    )


def _has_in_person_before_consult(
    conn: sqlite3.Connection, lifecycle_id: int, consult_at: datetime | None
) -> bool:
    rows = conn.execute(
        """
        SELECT completed_at FROM crm_lead_intake_sessions
        WHERE lifecycle_id = ? AND mode = 'in_person' AND status = 'completed'
          AND completed_at != ''
        ORDER BY completed_at ASC
        """,
        (int(lifecycle_id),),
    ).fetchall()
    if not rows:
        return False
    if consult_at is None:
        return True
    for row in rows:
        completed = _parse_ts(row[0])
        if completed is not None and completed <= consult_at:
            return True
    return False


def _has_in_person_before_consult_by_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    consult_at: datetime | None,
    lifecycle_id: int | None = None,
) -> bool:
    lid = int(lead_id)
    lc_id = int(lifecycle_id) if lifecycle_id else None
    rows = conn.execute(
        """
        SELECT completed_at FROM crm_lead_intake_sessions
        WHERE mode = 'in_person' AND status = 'completed' AND completed_at != ''
          AND (lead_id = ? OR (? IS NOT NULL AND lifecycle_id = ?))
        ORDER BY completed_at ASC
        """,
        (lid, lc_id, lc_id),
    ).fetchall()
    if not rows:
        return False
    if consult_at is None:
        return True
    for row in rows:
        completed = _parse_ts(row[0])
        if completed is not None and completed <= consult_at:
            return True
    return False


def _resolve_funnel_period(
    period_start: str | None, period_end: str | None
) -> tuple[str, str]:
    start = str(period_start or "").strip()[:10]
    end = str(period_end or "").strip()[:10]
    if not start or not end:
        now = datetime.utcnow()
        start = f"{now.year:04d}-{now.month:02d}-01"
        if now.month == 12:
            end = f"{now.year:04d}-12-31"
        else:
            next_month = datetime(now.year, now.month + 1, 1)
            end = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
    return start, end


def _build_funnel_result(
    *,
    cohort_mode: str,
    start: str,
    end: str,
    am_id: int | None,
    service_slug: str | None,
    counts: dict[str, int],
    proposal_within_7d: int,
    in_person_before_consult: int,
    presales_cost_total_vnd: int,
) -> dict[str, Any]:
    funnel_go = counts["funnel_go"]
    funnel_consult = counts["funnel_consult"]
    funnel_proposal = counts["funnel_proposal"]
    funnel_won = counts["funnel_won"]
    return {
        "cohort_mode": cohort_mode,
        "period_start": start,
        "period_end": end,
        "am_id": am_id,
        "service_slug": service_slug or None,
        "funnel_entered": counts["funnel_entered"],
        "funnel_intake_done": counts["funnel_intake_done"],
        "funnel_go": funnel_go,
        "funnel_consult": funnel_consult,
        "funnel_proposal": funnel_proposal,
        "funnel_won": funnel_won,
        "go_to_consult_pct": _pct(funnel_consult, funnel_go),
        "consult_to_proposal_7d_pct": _pct(proposal_within_7d, funnel_consult),
        "consult_to_proposal_7d_num": proposal_within_7d,
        "proposal_to_won_pct": _pct(funnel_won, funnel_proposal),
        "in_person_before_consult_pct": _pct(in_person_before_consult, funnel_go),
        "in_person_before_consult_num": in_person_before_consult,
        "presales_cost_total_vnd": presales_cost_total_vnd,
        "presales_cost_per_go_vnd": (
            int(presales_cost_total_vnd / funnel_go) if funnel_go > 0 else 0
        ),
        "presales_cost_per_won_vnd": (
            int(presales_cost_total_vnd / funnel_won) if funnel_won > 0 else 0
        ),
        "stages": [
            {"key": key, "label": FUNNEL_STAGE_LABELS[key], "count": counts[key]}
            for key in FUNNEL_STAGE_KEYS
        ],
    }


def _is_presales_funnel_won(conn: sqlite3.Connection, ps: dict[str, Any]) -> bool:
    if str(ps.get("status") or "") != "converted":
        return False
    lc_id = ps.get("lifecycle_id")
    if not lc_id:
        return False
    lc_row = conn.execute(
        "SELECT * FROM crm_service_lifecycle WHERE id = ?",
        (int(lc_id),),
    ).fetchone()
    if lc_row is None:
        return False
    return _is_funnel_won(dict(lc_row))


def _get_lifecycle_funnel_stats(
    conn: sqlite3.Connection,
    *,
    am_id: int | None = None,
    service_slug: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    exclude_presales_leads: bool = False,
) -> dict[str, Any]:
    """Funnel cohort theo lifecycle.created_at (legacy / delivery path)."""
    start, end = _resolve_funnel_period(period_start, period_end)

    where = ["lc.created_at >= ?", "lc.created_at <= ?"]
    params: list[Any] = [start, _date_end_inclusive(end)]
    if am_id is not None:
        where.append("lc.assigned_am = ?")
        params.append(int(am_id))
    slug = str(service_slug or "").strip()
    if slug:
        where.append("lc.service_slug = ?")
        params.append(slug)
    if exclude_presales_leads:
        where.append(
            """
            (
                lc.lead_id IS NULL
                OR NOT EXISTS (
                    SELECT 1 FROM crm_lead_presales ps_ex
                    WHERE ps_ex.lead_id = lc.lead_id
                )
            )
            """
        )

    rows = conn.execute(
        f"""
        SELECT lc.* FROM crm_service_lifecycle lc
        WHERE {' AND '.join(where)}
        ORDER BY lc.created_at ASC, lc.id ASC
        """,
        params,
    ).fetchall()
    cohort = [dict(r) for r in rows]
    cohort_ids = [int(lc["id"]) for lc in cohort]

    counts = {key: 0 for key in FUNNEL_STAGE_KEYS}
    counts["funnel_entered"] = len(cohort)

    consult_lifecycle_ids: list[int] = []
    proposal_within_7d = 0
    in_person_before_consult = 0

    for lc in cohort:
        lid = int(lc["id"])
        if conn.execute(
            """
            SELECT 1 FROM crm_lead_intake_sessions
            WHERE lifecycle_id = ? AND status = 'completed'
            LIMIT 1
            """,
            (lid,),
        ).fetchone():
            counts["funnel_intake_done"] += 1

        decision = _latest_intake_decision(conn, lid)
        if decision == "go":
            counts["funnel_go"] += 1

        stg_idx = stage_index(str(lc.get("stage") or "lead"))
        if stg_idx >= stage_index("consult"):
            counts["funnel_consult"] += 1
            consult_lifecycle_ids.append(lid)
            if decision == "go":
                consult_at = _stage_first_entered_at(conn, lid, "consult")
                if _has_in_person_before_consult(conn, lid, consult_at):
                    in_person_before_consult += 1
        if stg_idx >= stage_index("proposal"):
            counts["funnel_proposal"] += 1
        if _is_funnel_won(lc):
            counts["funnel_won"] += 1

    for lid in consult_lifecycle_ids:
        consult_at = _stage_first_entered_at(conn, lid, "consult")
        proposal_at = _stage_first_entered_at(conn, lid, "proposal")
        if consult_at is None or proposal_at is None:
            continue
        delta_days = (proposal_at - consult_at).total_seconds() / 86400.0
        if 0 <= delta_days <= 7:
            proposal_within_7d += 1

    presales_cost_total_vnd = 0
    if cohort_ids:
        placeholders = ",".join("?" * len(cohort_ids))
        cost_row = conn.execute(
            f"""
            SELECT COALESCE(SUM(amount_vnd), 0)
            FROM crm_svc_expenses
            WHERE lifecycle_id IN ({placeholders}) AND cost_phase = ?
            """,
            (*cohort_ids, COST_PHASE_PRESALES),
        ).fetchone()
        presales_cost_total_vnd = int(cost_row[0] if cost_row else 0)

    return _build_funnel_result(
        cohort_mode="lifecycle_created",
        start=start,
        end=end,
        am_id=am_id,
        service_slug=slug,
        counts=counts,
        proposal_within_7d=proposal_within_7d,
        in_person_before_consult=in_person_before_consult,
        presales_cost_total_vnd=presales_cost_total_vnd,
    )


def _get_presales_funnel_stats(
    conn: sqlite3.Connection,
    *,
    am_id: int | None = None,
    service_slug: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict[str, Any]:
    """Funnel cohort theo crm_lead_presales.created_at (L3.4 presales-on-lead path)."""
    from crm_lead_presales import presales_stage_index

    start, end = _resolve_funnel_period(period_start, period_end)

    where = ["ps.created_at >= ?", "ps.created_at <= ?"]
    params: list[Any] = [start, _date_end_inclusive(end)]
    if am_id is not None:
        where.append("COALESCE(ps.assigned_am, l.owner_id) = ?")
        params.append(int(am_id))
    slug = str(service_slug or "").strip()
    if slug:
        where.append("ps.service_slug = ?")
        params.append(slug)

    rows = conn.execute(
        f"""
        SELECT ps.*, l.owner_id
        FROM crm_lead_presales ps
        INNER JOIN crm_leads l ON l.id = ps.lead_id
        WHERE {' AND '.join(where)}
        ORDER BY ps.created_at ASC, ps.id ASC
        """,
        params,
    ).fetchall()
    cohort = [dict(r) for r in rows]
    presales_ids = [int(ps["id"]) for ps in cohort]

    counts = {key: 0 for key in FUNNEL_STAGE_KEYS}
    counts["funnel_entered"] = len(cohort)

    in_person_before_consult = 0

    for ps in cohort:
        lead_id = int(ps["lead_id"])
        lc_id = int(ps["lifecycle_id"]) if ps.get("lifecycle_id") else None

        if _lead_has_completed_intake(conn, lead_id, lc_id):
            counts["funnel_intake_done"] += 1

        decision = _latest_intake_decision_for_lead(conn, lead_id, lc_id)
        if decision == "go":
            counts["funnel_go"] += 1

        stg_idx = presales_stage_index(str(ps.get("stage") or "lead"))
        if stg_idx >= presales_stage_index("consult"):
            counts["funnel_consult"] += 1
            if decision == "go":
                consult_at = _parse_ts(ps.get("stage_entered_at"))
                if stg_idx > presales_stage_index("consult"):
                    consult_at = None
                if _has_in_person_before_consult_by_lead(
                    conn, lead_id, consult_at, lc_id
                ):
                    in_person_before_consult += 1
        if stg_idx >= presales_stage_index("proposal"):
            counts["funnel_proposal"] += 1
        if _is_presales_funnel_won(conn, ps):
            counts["funnel_won"] += 1

    # Presales path chưa có event log consult→proposal — v1 không tính ≤7d.
    proposal_within_7d = 0

    presales_cost_total_vnd = 0
    if presales_ids:
        placeholders = ",".join("?" * len(presales_ids))
        cost_row = conn.execute(
            f"""
            SELECT COALESCE(SUM(amount_vnd), 0)
            FROM crm_svc_expenses
            WHERE presales_id IN ({placeholders}) AND cost_phase = ?
            """,
            (*presales_ids, COST_PHASE_PRESALES),
        ).fetchone()
        presales_cost_total_vnd = int(cost_row[0] if cost_row else 0)

    return _build_funnel_result(
        cohort_mode="presales_created",
        start=start,
        end=end,
        am_id=am_id,
        service_slug=slug,
        counts=counts,
        proposal_within_7d=proposal_within_7d,
        in_person_before_consult=in_person_before_consult,
        presales_cost_total_vnd=presales_cost_total_vnd,
    )


def get_funnel_stats(
    conn: sqlite3.Connection,
    *,
    am_id: int | None = None,
    service_slug: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    cohort_mode: str = "lifecycle_created",
) -> dict[str, Any]:
    """Funnel pre-sales — lifecycle cohort; dual cohort khi PTT_PRESALES_ON_LEAD=1."""
    if cohort_mode not in ("lifecycle_created", "dual"):
        raise ValueError(f"cohort_mode không hỗ trợ: {cohort_mode}")

    if _presales_on_lead_metrics_enabled(conn):
        presales = _get_presales_funnel_stats(
            conn,
            am_id=am_id,
            service_slug=service_slug,
            period_start=period_start,
            period_end=period_end,
        )
        lifecycle = _get_lifecycle_funnel_stats(
            conn,
            am_id=am_id,
            service_slug=service_slug,
            period_start=period_start,
            period_end=period_end,
            exclude_presales_leads=True,
        )
        start, end = _resolve_funnel_period(period_start, period_end)
        slug = str(service_slug or "").strip()
        return {
            **presales,
            "dual_cohort": True,
            "cohort_mode": "dual",
            "period_start": start,
            "period_end": end,
            "am_id": am_id,
            "service_slug": slug or None,
            "presales_on_lead": presales,
            "lifecycle": lifecycle,
        }

    if cohort_mode == "dual":
        raise ValueError("dual cohort chỉ khả dụng khi PTT_PRESALES_ON_LEAD=1")

    return _get_lifecycle_funnel_stats(
        conn,
        am_id=am_id,
        service_slug=service_slug,
        period_start=period_start,
        period_end=period_end,
        exclude_presales_leads=False,
    )


_LIFECYCLE_META_MARKER = "\n<!--ptt:"


def parse_lifecycle_meta(notes: str) -> dict[str, Any]:
    """Đọc meta JSON nhúng cuối lifecycle.notes (không ghi đè text ghi chú AM)."""
    text = str(notes or "")
    idx = text.rfind(_LIFECYCLE_META_MARKER)
    if idx < 0:
        return {}
    rest = text[idx + len(_LIFECYCLE_META_MARKER) :]
    end = rest.find("-->")
    if end < 0:
        return {}
    payload = rest[:end].strip()
    try:
        data = json.loads(payload)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _strip_lifecycle_meta(notes: str) -> str:
    text = str(notes or "")
    idx = text.rfind(_LIFECYCLE_META_MARKER)
    if idx < 0:
        return text.rstrip()
    return text[:idx].rstrip()


def merge_lifecycle_meta(notes: str, patch: dict[str, Any]) -> str:
    base = _strip_lifecycle_meta(notes)
    meta = {**parse_lifecycle_meta(notes), **patch}
    meta_json = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
    if base:
        return f"{base}{_LIFECYCLE_META_MARKER}{meta_json}-->"
    return f"{_LIFECYCLE_META_MARKER}{meta_json}-->"


def get_am_presales_cap_alerts(
    conn: sqlite3.Connection, staff_id: int, *, limit: int = 5
) -> dict[str, Any]:
    """Presales active của AM đang vượt cap (L5 — staff KPI)."""
    if not _presales_on_lead_metrics_enabled(conn):
        return {"over_cap_count": 0, "alerts": []}
    sid = int(staff_id)
    rows = conn.execute(
        """
        SELECT ps.id, ps.lead_id, l.full_name
        FROM crm_lead_presales ps
        INNER JOIN crm_leads l ON l.id = ps.lead_id
        WHERE ps.status = 'active'
          AND COALESCE(ps.assigned_am, l.owner_id) = ?
        ORDER BY ps.updated_at DESC, ps.id DESC
        """,
        (sid,),
    ).fetchall()
    alerts: list[dict[str, Any]] = []
    for row in rows:
        alert = get_presales_cap_alert_for_presales(conn, int(row["id"]))
        if not alert.get("over_cap"):
            continue
        alerts.append(
            {
                "presales_id": int(row["id"]),
                "lead_id": int(row["lead_id"]),
                "lead_name": str(row["full_name"] or ""),
                "total_presales_vnd": int(alert.get("total_presales_vnd") or 0),
                "presales_cost_cap_vnd": int(alert.get("presales_cost_cap_vnd") or 0),
                "cap_utilization_pct": alert.get("cap_utilization_pct"),
                "cap_alert_message": str(alert.get("cap_alert_message") or ""),
            }
        )
    return {
        "over_cap_count": len(alerts),
        "alerts": alerts[: int(limit)],
    }


def get_presales_cost_cap(conn: sqlite3.Connection, lifecycle_id: int) -> int | None:
    cap, _source = resolve_presales_cost_cap(conn, lifecycle_id=int(lifecycle_id))
    return cap


def _read_cap_from_notes_text(notes: str) -> int | None:
    cap = parse_lifecycle_meta(str(notes or "")).get("presales_cost_cap_vnd")
    if cap is None or cap == "":
        return None
    try:
        value = int(cap)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def default_presales_cost_cap_vnd() -> int | None:
    raw = (os.getenv(ENV_PRESALES_COST_CAP) or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def presales_cap_strict_enabled() -> bool:
    raw = (os.getenv(ENV_PRESALES_CAP_STRICT) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _resolve_presales_id_for_lifecycle(
    conn: sqlite3.Connection, lifecycle_id: int
) -> int | None:
    lid = int(lifecycle_id)
    try:
        row = conn.execute(
            "SELECT id FROM crm_lead_presales WHERE lifecycle_id = ?",
            (lid,),
        ).fetchone()
        if row:
            return int(row[0])
        row = conn.execute(
            """
            SELECT ps.id FROM crm_lead_presales ps
            INNER JOIN crm_service_lifecycle lc ON lc.lead_id = ps.lead_id
            WHERE lc.id = ?
            ORDER BY ps.id DESC
            LIMIT 1
            """,
            (lid,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return int(row[0]) if row else None


def resolve_presales_cost_cap(
    conn: sqlite3.Connection,
    *,
    lifecycle_id: int | None = None,
    presales_id: int | None = None,
) -> tuple[int | None, str | None]:
    """
    Thứ tự ưu tiên cap (L3.5):
    lifecycle notes → presales notes (linked) → env PTT_PRESALES_COST_CAP_VND.
    """
    if lifecycle_id is not None:
        try:
            row = conn.execute(
                "SELECT notes FROM crm_service_lifecycle WHERE id = ?",
                (int(lifecycle_id),),
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
        if row is not None:
            cap = _read_cap_from_notes_text(str(row[0] or ""))
            if cap is not None:
                return cap, "lifecycle"
        pid = _resolve_presales_id_for_lifecycle(conn, int(lifecycle_id))
        if pid is not None:
            ps_row = conn.execute(
                "SELECT notes FROM crm_lead_presales WHERE id = ?",
                (pid,),
            ).fetchone()
            if ps_row is not None:
                cap = _read_cap_from_notes_text(str(ps_row[0] or ""))
                if cap is not None:
                    return cap, "presales"
        default = default_presales_cost_cap_vnd()
        return (default, "default") if default is not None else (None, None)

    if presales_id is not None:
        try:
            row = conn.execute(
                "SELECT notes FROM crm_lead_presales WHERE id = ?",
                (int(presales_id),),
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
        if row is not None:
            cap = _read_cap_from_notes_text(str(row[0] or ""))
            if cap is not None:
                return cap, "presales"
        default = default_presales_cost_cap_vnd()
        return (default, "default") if default is not None else (None, None)

    return None, None


def transfer_presales_cap_to_lifecycle(
    conn: sqlite3.Connection, presales_id: int, lifecycle_id: int
) -> int | None:
    """Copy cap từ presales notes → lifecycle khi promote (L3.5)."""
    try:
        row = conn.execute(
            "SELECT notes FROM crm_lead_presales WHERE id = ?",
            (int(presales_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    cap = _read_cap_from_notes_text(str(row[0] or ""))
    if cap is None:
        return None
    try:
        lc_row = conn.execute(
            "SELECT notes FROM crm_service_lifecycle WHERE id = ?",
            (int(lifecycle_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        lc_row = None
    if lc_row is not None and _read_cap_from_notes_text(str(lc_row[0] or "")) is not None:
        return _read_cap_from_notes_text(str(lc_row[0] or ""))
    return set_presales_cost_cap(conn, int(lifecycle_id), cap)


def _cap_alert_payload(
    *,
    cap_vnd: int | None,
    total_vnd: int,
    cap_source: str | None,
) -> dict[str, Any]:
    if cap_vnd is None:
        return {
            "presales_cost_cap_vnd": None,
            "cap_source": None,
            "cap_remaining_vnd": None,
            "cap_utilization_pct": None,
            "over_cap": False,
            "cap_alert_message": "",
        }
    over = total_vnd > cap_vnd
    remaining = max(0, cap_vnd - total_vnd)
    util = round(total_vnd / cap_vnd * 100, 1) if cap_vnd > 0 else 0.0
    msg = ""
    if over:
        msg = (
            f"Chi phí pre-sales ({total_vnd:,} ₫) vượt cap ({cap_vnd:,} ₫). "
            "Cân nhắc giảm cước gọi/đi lại hoặc tăng cap với Sales lead."
        )
    return {
        "presales_cost_cap_vnd": cap_vnd,
        "cap_source": cap_source,
        "cap_remaining_vnd": remaining,
        "cap_utilization_pct": util,
        "over_cap": over,
        "cap_alert_message": msg,
    }


def enforce_presales_expense_cap(
    conn: sqlite3.Connection, presales_id: int, amount_vnd: int
) -> None:
    """Chặn ghi chi phí khi strict + vượt cap (L3.5)."""
    if not presales_cap_strict_enabled():
        return
    from crm_svc_finance import list_presales_expenses

    cap_vnd, _ = resolve_presales_cost_cap(conn, presales_id=int(presales_id))
    if cap_vnd is None:
        return
    current = sum(
        int(r.get("amount_vnd") or 0)
        for r in list_presales_expenses(conn, int(presales_id))
    )
    projected = current + int(amount_vnd)
    if projected > cap_vnd:
        raise PresalesCapExceededError(
            f"Chi phí pre-sales vượt cap ({cap_vnd:,} ₫): "
            f"hiện {current:,} ₫ + thêm {int(amount_vnd):,} ₫."
        )


def enforce_presales_expense_cap_for_lifecycle(
    conn: sqlite3.Connection, lifecycle_id: int, amount_vnd: int
) -> None:
    if not presales_cap_strict_enabled():
        return
    cap_vnd, _ = resolve_presales_cost_cap(conn, lifecycle_id=int(lifecycle_id))
    if cap_vnd is None:
        return
    rows = list_expenses(conn, int(lifecycle_id), cost_phase=COST_PHASE_PRESALES)
    current = sum(int(r.get("amount_vnd") or 0) for r in rows)
    projected = current + int(amount_vnd)
    if projected > cap_vnd:
        raise PresalesCapExceededError(
            f"Chi phí pre-sales vượt cap ({cap_vnd:,} ₫): "
            f"hiện {current:,} ₫ + thêm {int(amount_vnd):,} ₫."
        )


def get_presales_cost_cap_for_presales(
    conn: sqlite3.Connection, presales_id: int
) -> int | None:
    cap, _source = resolve_presales_cost_cap(conn, presales_id=int(presales_id))
    return cap


def set_presales_cost_cap_for_presales(
    conn: sqlite3.Connection, presales_id: int, cap_vnd: int | None
) -> int | None:
    try:
        row = conn.execute(
            "SELECT notes FROM crm_lead_presales WHERE id = ?",
            (int(presales_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    notes = str(row[0] or "")
    meta = parse_lifecycle_meta(notes)
    if cap_vnd is None or int(cap_vnd) <= 0:
        meta.pop("presales_cost_cap_vnd", None)
    else:
        meta["presales_cost_cap_vnd"] = int(cap_vnd)
    if meta:
        new_notes = merge_lifecycle_meta(notes, meta)
    else:
        new_notes = _strip_lifecycle_meta(notes)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE crm_lead_presales SET notes = ?, updated_at = ? WHERE id = ?",
        (new_notes, ts, int(presales_id)),
    )
    conn.commit()
    return get_presales_cost_cap_for_presales(conn, presales_id)


def set_presales_cost_cap(
    conn: sqlite3.Connection, lifecycle_id: int, cap_vnd: int | None
) -> int | None:
    try:
        row = conn.execute(
            "SELECT notes FROM crm_service_lifecycle WHERE id = ?",
            (int(lifecycle_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    notes = str(row[0] or "")
    meta = parse_lifecycle_meta(notes)
    if cap_vnd is None or int(cap_vnd) <= 0:
        meta.pop("presales_cost_cap_vnd", None)
    else:
        meta["presales_cost_cap_vnd"] = int(cap_vnd)
    if meta:
        new_notes = merge_lifecycle_meta(notes, meta)
    else:
        new_notes = _strip_lifecycle_meta(notes)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE crm_service_lifecycle SET notes = ?, updated_at = ? WHERE id = ?",
        (new_notes, ts, int(lifecycle_id)),
    )
    conn.commit()
    return get_presales_cost_cap(conn, lifecycle_id)


def get_presales_cap_alert_for_presales(
    conn: sqlite3.Connection, presales_id: int
) -> dict[str, Any]:
    """Cảnh báo cap chi phí pre-sales trên lead."""
    from crm_svc_finance import list_presales_expenses

    pid = int(presales_id)
    cap_vnd, cap_source = resolve_presales_cost_cap(conn, presales_id=pid)
    rows = list_presales_expenses(conn, pid)
    total_vnd = sum(int(r.get("amount_vnd") or 0) for r in rows)
    return {
        "total_presales_vnd": total_vnd,
        **_cap_alert_payload(
            cap_vnd=cap_vnd, total_vnd=total_vnd, cap_source=cap_source
        ),
    }


def get_presales_cap_alert(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, Any]:
    """Cảnh báo khi tổng chi phí pre-sales lifecycle vượt cap cấu hình."""
    lid = int(lifecycle_id)
    cap_vnd, cap_source = resolve_presales_cost_cap(conn, lifecycle_id=lid)
    rows = list_expenses(conn, lid, cost_phase=COST_PHASE_PRESALES)
    total_vnd = sum(int(r.get("amount_vnd") or 0) for r in rows)
    return {
        "total_presales_vnd": total_vnd,
        **_cap_alert_payload(
            cap_vnd=cap_vnd, total_vnd=total_vnd, cap_source=cap_source
        ),
    }
