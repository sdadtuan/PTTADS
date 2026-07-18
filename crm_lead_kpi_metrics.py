"""KPI Lead đủ chuẩn + Close rate — nguồn thống nhất cho CRM."""
from __future__ import annotations

import calendar
import sqlite3
from datetime import date
from typing import Any

from crm_service_lifecycle import stage_index

# Loại khỏi mọi metric lead
LEAD_EXCLUDE_STATUSES: frozenset[str] = frozenset({
    "junk",
    "spam",
    "duplicate",
    "pending_cleanup",
})

# Legacy: đã qua qualify trước intake/pre-sales
LEGACY_QUALIFIED_STATUSES: frozenset[str] = frozenset({
    "qualified",
    "proposal_sent",
    "nurturing",
    "negotiation",
})

LEAD_WON_STATUSES: frozenset[str] = frozenset({"post_sale", "won"})
LEAD_LOST_STATUS = "lost"

LIFECYCLE_QUALIFY_STAGES: frozenset[str] = frozenset({
    "consult",
    "proposal",
    "onboard",
    "deliver",
    "handover",
    "retain",
})


def _parse_ymd(text: str | None) -> date | None:
    raw = str(text or "").strip()[:10]
    if len(raw) != 10:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    y, m = int(year), int(month)
    last_day = calendar.monthrange(y, m)[1]
    return date(y, m, 1), date(y, m, last_day)


def _in_period(ts: str | None, period_start: date, period_end: date) -> bool:
    d = _parse_ymd(ts)
    if d is None:
        return False
    return period_start <= d <= period_end


def _in_month(ts: str | None, period_start: date, period_end: date) -> bool:
    return _in_period(ts, period_start, period_end)


def _tables_exist(conn: sqlite3.Connection, *names: str) -> dict[str, bool]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ({})".format(
            ",".join("?" * len(names))
        ),
        names,
    ).fetchall()
    found = {str(r[0]) for r in rows}
    return {n: n in found for n in names}


def _lead_row_excluded(row: dict[str, Any]) -> bool:
    if int(row.get("is_duplicate") or 0) == 1:
        return True
    status = str(row.get("status") or "").strip().lower()
    return status in LEAD_EXCLUDE_STATUSES


def _fetch_lead_signals(conn: sqlite3.Connection, lead_id: int) -> dict[str, Any]:
    """Thu thập mốc qualify/won cho một lead."""
    lid = int(lead_id)
    tables = _tables_exist(
        conn,
        "crm_lead_intake_sessions",
        "crm_lead_presales",
        "crm_service_lifecycle",
        "crm_contracts",
    )
    go_at = ps_at = lc_at = None
    has_go = has_presales = has_lc_consult = False
    is_won = False
    is_lost = False

    row = conn.execute(
        "SELECT status, created_at, updated_at FROM crm_leads WHERE id = ?",
        (lid,),
    ).fetchone()
    status = str(row["status"] or "").strip().lower() if row else ""
    legacy_qualified_at = str(row["updated_at"] or row["created_at"] or "") if row else ""

    if status in LEAD_WON_STATUSES:
        is_won = True
        has_go = True
        if not go_at:
            go_at = legacy_qualified_at
    if status == LEAD_LOST_STATUS:
        is_lost = True
    if status in LEGACY_QUALIFIED_STATUSES:
        has_go = True
        if not go_at:
            go_at = legacy_qualified_at

    if tables.get("crm_lead_intake_sessions"):
        go_row = conn.execute(
            """
            SELECT MIN(completed_at) AS ts
            FROM crm_lead_intake_sessions
            WHERE lead_id = ? AND status = 'completed' AND decision = 'go'
              AND completed_at != ''
            """,
            (lid,),
        ).fetchone()
        if go_row and go_row["ts"]:
            has_go = True
            go_at = str(go_row["ts"])

    if tables.get("crm_lead_presales"):
        ps_row = conn.execute(
            """
            SELECT MIN(created_at) AS ts, MAX(CASE WHEN status = 'converted' THEN 1 ELSE 0 END) AS converted
            FROM crm_lead_presales
            WHERE lead_id = ?
            """,
            (lid,),
        ).fetchone()
        if ps_row and ps_row["ts"]:
            has_presales = True
            ps_at = str(ps_row["ts"])
        if ps_row and int(ps_row["converted"] or 0) == 1:
            lc_id_row = conn.execute(
                "SELECT lifecycle_id FROM crm_lead_presales WHERE lead_id = ? AND status = 'converted'",
                (lid,),
            ).fetchone()
            if lc_id_row and lc_id_row["lifecycle_id"]:
                is_won = is_won or _lifecycle_is_won(
                    conn, int(lc_id_row["lifecycle_id"])
                )

    if tables.get("crm_service_lifecycle"):
        lc_rows = conn.execute(
            """
            SELECT id, stage, status, contract_id, stage_entered_at, created_at
            FROM crm_service_lifecycle
            WHERE lead_id = ?
            ORDER BY id ASC
            """,
            (lid,),
        ).fetchall()
        for lc in lc_rows:
            lc = dict(lc)
            stg = str(lc.get("stage") or "lead")
            if stg in LIFECYCLE_QUALIFY_STAGES or stage_index(stg) >= stage_index("consult"):
                has_lc_consult = True
                lc_at = str(lc.get("stage_entered_at") or lc.get("created_at") or "")
            if _lifecycle_row_is_won(lc):
                is_won = True

    if tables.get("crm_contracts"):
        ct = conn.execute(
            """
            SELECT 1 FROM crm_contracts
            WHERE lead_id = ? AND status IN ('signed', 'active', 'renewed')
            LIMIT 1
            """,
            (lid,),
        ).fetchone()
        if ct:
            is_won = True

    qualified = has_go or has_presales or has_lc_consult
    qualified_at = _earliest_ts(go_at, ps_at, lc_at if has_lc_consult else None)

    return {
        "qualified": qualified,
        "qualified_at": qualified_at,
        "won": is_won,
        "lost": is_lost and qualified and not is_won,
    }


def _earliest_ts(*values: str | None) -> str | None:
    parsed: list[tuple[date, str]] = []
    for raw in values:
        if not raw:
            continue
        d = _parse_ymd(raw)
        if d is not None:
            parsed.append((d, str(raw)))
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[0])
    return parsed[0][1]


def _lifecycle_row_is_won(lc: dict[str, Any]) -> bool:
    if lc.get("contract_id"):
        return True
    stg = str(lc.get("stage") or "lead")
    status = str(lc.get("status") or "draft")
    return stage_index(stg) >= stage_index("onboard") and status in ("active", "closed")


def _lifecycle_is_won(conn: sqlite3.Connection, lifecycle_id: int) -> bool:
    row = conn.execute(
        "SELECT stage, status, contract_id FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if row is None:
        return False
    return _lifecycle_row_is_won(dict(row))


def is_lead_qualified(conn: sqlite3.Connection, lead_id: int) -> bool:
    row = conn.execute(
        "SELECT id, status, is_duplicate FROM crm_leads WHERE id = ?",
        (int(lead_id),),
    ).fetchone()
    if row is None:
        return False
    if _lead_row_excluded(dict(row)):
        return False
    return bool(_fetch_lead_signals(conn, int(lead_id))["qualified"])


def is_lead_won(conn: sqlite3.Connection, lead_id: int) -> bool:
    return bool(_fetch_lead_signals(conn, int(lead_id))["won"])


def get_staff_close_rate_pct(conn: sqlite3.Connection, staff_id: int) -> float:
    """Close rate all-time theo owner — dùng auto-assign & competency."""
    summary = get_unified_lead_kpi_summary(
        conn, staff_id=int(staff_id), period_cohort=False
    )
    return float(summary["close_rate_pct"])


def get_unified_lead_kpi_summary(
    conn: sqlite3.Connection,
    *,
    year: int | None = None,
    month: int | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    staff_id: int | None = None,
    period_cohort: bool = True,
) -> dict[str, Any]:
    """
    KPI Lead đủ chuẩn + close rate.

    - qualified: intake Go OR presales OR lifecycle consult+
    - close_rate_pct: won / qualified
    - close_rate_decided_pct: won / (won + lost) — chỉ lead qualified đã quyết định
    - period_cohort=True + year/month: cohort tháng
    - period_cohort=True + period_start/end: cohort tuần (hoặc khoảng tùy ý)
    """
    params: list[Any] = []
    where = ["COALESCE(l.is_duplicate, 0) = 0"]
    excl = sorted(LEAD_EXCLUDE_STATUSES)
    where.append(
        "l.status NOT IN ({})".format(",".join("?" * len(excl)))
    )
    params.extend(excl)
    if staff_id is not None:
        where.append("l.owner_id = ?")
        params.append(int(staff_id))

    rows = conn.execute(
        f"""
        SELECT l.id, l.owner_id, l.status, COALESCE(l.is_duplicate, 0) AS is_duplicate
        FROM crm_leads l
        WHERE {' AND '.join(where)}
        ORDER BY l.id
        """,
        params,
    ).fetchall()

    cohort_start = cohort_end = None
    if period_start is not None and period_end is not None and period_cohort:
        cohort_start, cohort_end = period_start, period_end
    elif year is not None and month is not None and period_cohort:
        cohort_start, cohort_end = _month_bounds(year, month)

    qualified_total = won_total = lost_qualified = 0
    qualified_in_cohort = won_cohort = lost_cohort = decided_cohort = 0

    for row in rows:
        lead_id = int(row["id"])
        sig = _fetch_lead_signals(conn, lead_id)
        if not sig["qualified"]:
            continue

        qualified_total += 1
        if sig["won"]:
            won_total += 1
        if sig["lost"]:
            lost_qualified += 1

        if cohort_start is None or cohort_end is None:
            continue
        if not _in_period(sig.get("qualified_at"), cohort_start, cohort_end):
            continue
        qualified_in_cohort += 1
        if sig["won"]:
            won_cohort += 1
        if sig["lost"]:
            lost_cohort += 1
        if sig["won"] or sig["lost"]:
            decided_cohort += 1

    close_rate_pct = round(won_total / qualified_total * 100, 1) if qualified_total else 0.0
    close_rate_decided_pct = (
        round(won_total / (won_total + lost_qualified) * 100, 1)
        if (won_total + lost_qualified) > 0
        else 0.0
    )

    cohort_close_rate_pct = (
        round(won_cohort / qualified_in_cohort * 100, 1) if qualified_in_cohort else 0.0
    )
    cohort_close_decided_pct = (
        round(won_cohort / decided_cohort * 100, 1) if decided_cohort else 0.0
    )

    return {
        "year": int(year) if year is not None else None,
        "month": int(month) if month is not None else None,
        "staff_id": int(staff_id) if staff_id is not None else None,
        "period_start": cohort_start.isoformat() if cohort_start else None,
        "period_end": cohort_end.isoformat() if cohort_end else None,
        "qualified_leads": qualified_total,
        "won_leads": won_total,
        "lost_qualified_leads": lost_qualified,
        "close_rate_pct": close_rate_pct,
        "close_rate_decided_pct": close_rate_decided_pct,
        "qualified_in_cohort": qualified_in_cohort,
        "qualified_in_month": qualified_in_cohort,
        "won_from_month_cohort": won_cohort,
        "lost_from_month_cohort": lost_cohort,
        "cohort_close_rate_pct": cohort_close_rate_pct,
        "cohort_close_rate_decided_pct": cohort_close_decided_pct,
        "definitions": {
            "qualified": "Intake Go OR presales OR lifecycle consult+ OR legacy qualified+",
            "won": "post_sale/won OR lifecycle onboard+ OR HĐ signed/active",
            "close_rate": "won / qualified",
            "close_rate_decided": "won / (won + lost) trong qualified",
        },
    }


def summarize_leads_kpi(
    conn: sqlite3.Connection, lead_ids: list[int]
) -> dict[str, Any]:
    """Tổng hợp qualified/won/close rate trên tập lead_id."""
    qualified = won = lost_qualified = 0
    for lid in lead_ids:
        row = conn.execute(
            "SELECT status, is_duplicate FROM crm_leads WHERE id = ?",
            (int(lid),),
        ).fetchone()
        if row is None or _lead_row_excluded(dict(row)):
            continue
        sig = _fetch_lead_signals(conn, int(lid))
        if not sig["qualified"]:
            continue
        qualified += 1
        if sig["won"]:
            won += 1
        if sig["lost"]:
            lost_qualified += 1
    close_rate_pct = round(won / qualified * 100, 1) if qualified else 0.0
    close_rate_decided_pct = (
        round(won / (won + lost_qualified) * 100, 1)
        if (won + lost_qualified) > 0
        else 0.0
    )
    return {
        "qualified_leads": qualified,
        "won_leads": won,
        "lost_qualified_leads": lost_qualified,
        "close_rate_pct": close_rate_pct,
        "close_rate_decided_pct": close_rate_decided_pct,
    }


def count_qualified_leads_in_month(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    re_project_id: int | None = None,
    owner_id: int | None = None,
) -> int:
    """Lead đủ chuẩn trong tháng — thay RE_LEADS_NEW đếm mọi lead."""
    params: list[Any] = list(sorted(LEAD_EXCLUDE_STATUSES))
    where = [
        "COALESCE(l.is_duplicate, 0) = 0",
        "l.status NOT IN ({})".format(",".join("?" * len(LEAD_EXCLUDE_STATUSES))),
    ]
    if re_project_id is not None:
        where.append("l.re_project_id = ?")
        params.append(int(re_project_id))
    if owner_id is not None:
        where.append("l.owner_id = ?")
        params.append(int(owner_id))

    period_start, period_end = _month_bounds(year, month)
    count = 0
    rows = conn.execute(
        f"SELECT l.id FROM crm_leads l WHERE {' AND '.join(where)}",
        params,
    ).fetchall()
    for row in rows:
        sig = _fetch_lead_signals(conn, int(row["id"]))
        if not sig["qualified"]:
            continue
        if _in_period(sig.get("qualified_at"), period_start, period_end):
            count += 1
    return count


def count_qualified_leads_in_period(
    conn: sqlite3.Connection,
    *,
    period_start: date,
    period_end: date,
    re_project_id: int | None = None,
    owner_id: int | None = None,
) -> int:
    """Lead đủ chuẩn trong khoảng ngày — dùng cho dashboard tuần."""
    params: list[Any] = list(sorted(LEAD_EXCLUDE_STATUSES))
    where = [
        "COALESCE(l.is_duplicate, 0) = 0",
        "l.status NOT IN ({})".format(",".join("?" * len(LEAD_EXCLUDE_STATUSES))),
    ]
    if re_project_id is not None:
        where.append("l.re_project_id = ?")
        params.append(int(re_project_id))
    if owner_id is not None:
        where.append("l.owner_id = ?")
        params.append(int(owner_id))

    count = 0
    rows = conn.execute(
        f"SELECT l.id FROM crm_leads l WHERE {' AND '.join(where)}",
        params,
    ).fetchall()
    for row in rows:
        sig = _fetch_lead_signals(conn, int(row["id"]))
        if not sig["qualified"]:
            continue
        if _in_period(sig.get("qualified_at"), period_start, period_end):
            count += 1
    return count
