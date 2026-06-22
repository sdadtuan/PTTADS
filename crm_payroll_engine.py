"""Chính sách chấm công / lương theo giờ — PTT CRM."""
from __future__ import annotations

import json
import re
import sqlite3
from calendar import monthrange
from datetime import datetime
from typing import Any

DEFAULT_POLICY: dict[str, Any] = {
    "work_weekdays": "0,1,2,3,4",
    "shift_start": "08:30",
    "shift_end": "17:30",
    "break_minutes_default": 60,
    "late_grace_minutes": 5,
    "late_penalty_vnd_per_min": 5000,
    "late_penalty_max_vnd": 200_000,
    "standard_hours_per_day": 8.0,
    "bonus_mode": "attendance",
    "bonus_pct": 5.0,
    "bonus_min_days": 20,
    "overtime_multiplier": 1.5,
    "weekday_shifts": "",
}

WEEKDAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def _hhmm_to_minutes(s: str) -> int | None:
    m = re.match(r"^(\d{1,2}):(\d{2})$", (s or "").strip())
    if not m:
        return None
    h, mm = int(m.group(1)), int(m.group(2))
    if h > 23 or mm > 59:
        return None
    return h * 60 + mm


def parse_work_weekdays(raw: str | None) -> set[int]:
    """Python weekday: 0=Thứ 2 … 6=Chủ nhật."""
    if not raw or not str(raw).strip():
        return {0, 1, 2, 3, 4}
    out: set[int] = set()
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            d = int(part)
        except ValueError:
            continue
        if 0 <= d <= 6:
            out.add(d)
    return out or {0, 1, 2, 3, 4}


def default_weekday_shifts(
    *,
    work_weekdays: set[int] | None = None,
    shift_start: str = "08:30",
    shift_end: str = "17:30",
    break_minutes: int = 60,
    standard_hours: float = 8.0,
) -> list[dict[str, Any]]:
    work = work_weekdays if work_weekdays is not None else {0, 1, 2, 3, 4}
    return [
        {
            "weekday": wd,
            "label": WEEKDAY_LABELS[wd],
            "work": wd in work,
            "shift_start": shift_start,
            "shift_end": shift_end,
            "break_minutes": break_minutes,
            "standard_hours": standard_hours,
        }
        for wd in range(7)
    ]


def normalize_weekday_shifts(items: list[Any]) -> list[dict[str, Any]]:
    defaults = default_weekday_shifts()
    default_map = {d["weekday"]: d for d in defaults}
    by_wd: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            wd = int(item.get("weekday", -1))
        except (TypeError, ValueError):
            continue
        if wd < 0 or wd > 6:
            continue
        base = default_map[wd]
        try:
            brk = int(item.get("break_minutes", base["break_minutes"]))
        except (TypeError, ValueError):
            brk = int(base["break_minutes"])
        try:
            std_h = float(item.get("standard_hours", base["standard_hours"]))
        except (TypeError, ValueError):
            std_h = float(base["standard_hours"])
        by_wd[wd] = {
            "weekday": wd,
            "label": WEEKDAY_LABELS[wd],
            "work": bool(item.get("work", base["work"])),
            "shift_start": str(item.get("shift_start") or base["shift_start"]).strip()[:5],
            "shift_end": str(item.get("shift_end") or base["shift_end"]).strip()[:5],
            "break_minutes": max(0, min(brk, 24 * 60)),
            "standard_hours": max(0.5, min(std_h, 24.0)),
        }
    return [by_wd.get(wd, default_map[wd]) for wd in range(7)]


def parse_weekday_shifts(policy: dict[str, Any]) -> list[dict[str, Any]]:
    raw = policy.get("weekday_shifts")
    data: list[Any] | None = None
    if isinstance(raw, list):
        data = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                data = parsed
        except json.JSONDecodeError:
            data = None
    if data:
        return normalize_weekday_shifts(data)
    work = parse_work_weekdays(str(policy.get("work_weekdays") or ""))
    return default_weekday_shifts(
        work_weekdays=work,
        shift_start=str(policy.get("shift_start") or "08:30"),
        shift_end=str(policy.get("shift_end") or "17:30"),
        break_minutes=int(policy.get("break_minutes_default") or 60),
        standard_hours=float(policy.get("standard_hours_per_day") or 8),
    )


def weekday_shifts_json(shifts: list[dict[str, Any]]) -> str:
    compact = [
        {
            "weekday": s["weekday"],
            "work": bool(s.get("work")),
            "shift_start": str(s.get("shift_start") or "08:30"),
            "shift_end": str(s.get("shift_end") or "17:30"),
            "break_minutes": int(s.get("break_minutes") or 0),
            "standard_hours": float(s.get("standard_hours") or 8),
        }
        for s in shifts
    ]
    return json.dumps(compact, ensure_ascii=False)


def work_weekdays_from_shifts(shifts: list[dict[str, Any]]) -> str:
    days = [str(int(s["weekday"])) for s in shifts if s.get("work")]
    return ",".join(days) if days else "0,1,2,3,4"


def shift_for_weekday(policy: dict[str, Any], weekday: int) -> dict[str, Any]:
    for s in parse_weekday_shifts(policy):
        if int(s["weekday"]) == weekday:
            return s
    defaults = default_weekday_shifts()
    return defaults[weekday % 7]


def expected_standard_hours_in_month(year: int, month: int, policy: dict[str, Any]) -> float:
    shift_map = {int(s["weekday"]): s for s in parse_weekday_shifts(policy)}
    _, last = monthrange(year, month)
    total = 0.0
    for d in range(1, last + 1):
        wd = datetime(year, month, d).weekday()
        s = shift_map.get(wd)
        if s and s.get("work"):
            total += float(s.get("standard_hours") or 8)
    return max(total, 0.5)


def count_workdays_in_month(year: int, month: int, weekdays: set[int]) -> int:
    _, last = monthrange(year, month)
    n = 0
    for d in range(1, last + 1):
        if datetime(year, month, d).weekday() in weekdays:
            n += 1
    return max(n, 1)


def ensure_payroll_policy_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_payroll_policy (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            work_weekdays TEXT NOT NULL DEFAULT '0,1,2,3,4',
            shift_start TEXT NOT NULL DEFAULT '08:30',
            shift_end TEXT NOT NULL DEFAULT '17:30',
            break_minutes_default INTEGER NOT NULL DEFAULT 60,
            late_grace_minutes INTEGER NOT NULL DEFAULT 5,
            late_penalty_vnd_per_min INTEGER NOT NULL DEFAULT 5000,
            late_penalty_max_vnd INTEGER NOT NULL DEFAULT 200000,
            standard_hours_per_day REAL NOT NULL DEFAULT 8,
            bonus_mode TEXT NOT NULL DEFAULT 'attendance',
            bonus_pct REAL NOT NULL DEFAULT 5,
            bonus_min_days INTEGER NOT NULL DEFAULT 20,
            overtime_multiplier REAL NOT NULL DEFAULT 1.5,
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    row = conn.execute("SELECT id FROM crm_payroll_policy WHERE id = 1").fetchone()
    if not row:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        p = DEFAULT_POLICY
        conn.execute(
            """
            INSERT INTO crm_payroll_policy (
                id, work_weekdays, shift_start, shift_end, break_minutes_default,
                late_grace_minutes, late_penalty_vnd_per_min, late_penalty_max_vnd,
                standard_hours_per_day, bonus_mode, bonus_pct, bonus_min_days,
                overtime_multiplier, updated_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p["work_weekdays"],
                p["shift_start"],
                p["shift_end"],
                p["break_minutes_default"],
                p["late_grace_minutes"],
                p["late_penalty_vnd_per_min"],
                p["late_penalty_max_vnd"],
                p["standard_hours_per_day"],
                p["bonus_mode"],
                p["bonus_pct"],
                p["bonus_min_days"],
                p["overtime_multiplier"],
                ts,
            ),
        )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_position_payroll (
            position_id INTEGER PRIMARY KEY REFERENCES crm_positions(id) ON DELETE CASCADE,
            rank_level INTEGER NOT NULL DEFAULT 1,
            allowance_vnd INTEGER NOT NULL DEFAULT 0,
            bonus_pct REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )

    pl_cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_payroll_line)")}
    for col, ddl in (
        ("hours_worked_total", "REAL NOT NULL DEFAULT 0"),
        ("late_minutes_total", "INTEGER NOT NULL DEFAULT 0"),
        ("late_deduction_vnd", "INTEGER NOT NULL DEFAULT 0"),
        ("position_allowance_vnd", "INTEGER NOT NULL DEFAULT 0"),
        ("bonus_vnd", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if col not in pl_cols:
            try:
                conn.execute(f"ALTER TABLE crm_payroll_line ADD COLUMN {col} {ddl}")
            except sqlite3.Error:
                pass

    _seed_position_payroll_defaults(conn)
    _migrate_weekday_shifts_column(conn)


def _migrate_weekday_shifts_column(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_payroll_policy)")}
    if "weekday_shifts" not in cols:
        try:
            conn.execute(
                "ALTER TABLE crm_payroll_policy ADD COLUMN weekday_shifts TEXT NOT NULL DEFAULT ''"
            )
        except sqlite3.Error:
            pass
    row = conn.execute(
        "SELECT work_weekdays, shift_start, shift_end, break_minutes_default, "
        "standard_hours_per_day, weekday_shifts FROM crm_payroll_policy WHERE id = 1"
    ).fetchone()
    if row is None:
        return
    existing = str(row["weekday_shifts"] or "").strip()
    if existing:
        return
    policy = dict(row)
    shifts = parse_weekday_shifts(policy)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE crm_payroll_policy SET weekday_shifts = ?, updated_at = ? WHERE id = 1",
        (weekday_shifts_json(shifts), ts),
    )


def _seed_position_payroll_defaults(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT id, code, sort_order FROM crm_positions WHERE active = 1 ORDER BY sort_order"
    ).fetchall()
    if not rows:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    defaults_by_code = {
        "CSKH-01": (1, 500_000, 0.0),
        "KD-01": (2, 1_000_000, 5.0),
        "VH-01": (3, 1_500_000, 8.0),
    }
    for i, r in enumerate(rows):
        pid = int(r["id"])
        exists = conn.execute(
            "SELECT 1 FROM crm_position_payroll WHERE position_id = ?", (pid,)
        ).fetchone()
        if exists:
            continue
        code = str(r["code"] or "")
        if code in defaults_by_code:
            rank, allow, bp = defaults_by_code[code]
        else:
            rank, allow, bp = i + 1, max(0, (4 - i) * 300_000), 0.0
        conn.execute(
            """
            INSERT INTO crm_position_payroll (position_id, rank_level, allowance_vnd, bonus_pct, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (pid, rank, allow, bp, ts),
        )


def load_policy(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_payroll_policy_schema(conn)
    row = conn.execute("SELECT * FROM crm_payroll_policy WHERE id = 1").fetchone()
    if not row:
        return dict(DEFAULT_POLICY)
    return dict(row)


def load_position_payroll_map(conn: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    ensure_payroll_policy_schema(conn)
    rows = conn.execute(
        """
        SELECT pp.*, p.code AS position_code, p.name AS position_name
        FROM crm_position_payroll pp
        JOIN crm_positions p ON p.id = pp.position_id
        WHERE p.active = 1
        ORDER BY pp.rank_level ASC, p.sort_order ASC
        """
    ).fetchall()
    return {int(r["position_id"]): dict(r) for r in rows}


def policy_for_api(policy: dict[str, Any]) -> dict[str, Any]:
    shifts = parse_weekday_shifts(policy)
    weekdays = {int(s["weekday"]) for s in shifts if s.get("work")}
    labels = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return {
        **policy,
        "weekday_shifts": shifts,
        "work_weekdays": work_weekdays_from_shifts(shifts),
        "work_weekday_labels": [labels[d] for d in sorted(weekdays)],
    }


def analyze_attendance_day(
    *,
    work_date: str,
    check_in: str,
    check_out: str,
    break_minutes: int,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Phân tích một ngày: giờ làm, đi trễ, phạt."""
    try:
        y, mo, d = [int(x) for x in work_date.split("-")]
        wd = datetime(y, mo, d).weekday()
    except (ValueError, AttributeError):
        wd = 0

    shift_cfg = shift_for_weekday(policy, wd)
    is_scheduled = bool(shift_cfg.get("work"))

    shift_start = str(shift_cfg.get("shift_start") or policy.get("shift_start") or "08:30")
    shift_end = str(shift_cfg.get("shift_end") or policy.get("shift_end") or "17:30")
    grace = max(0, int(policy.get("late_grace_minutes") or 0))
    pen_per = max(0, int(policy.get("late_penalty_vnd_per_min") or 0))
    pen_max = max(0, int(policy.get("late_penalty_max_vnd") or 0))
    std_hours = max(0.5, float(shift_cfg.get("standard_hours") or policy.get("standard_hours_per_day") or 8))
    break_default = max(0, int(shift_cfg.get("break_minutes") or policy.get("break_minutes_default") or 0))

    ci = _hhmm_to_minutes(str(check_in or "").strip())
    co = _hhmm_to_minutes(str(check_out or "").strip())
    ss = _hhmm_to_minutes(shift_start)
    se = _hhmm_to_minutes(shift_end)

    worked_minutes = 0
    late_minutes = 0
    if ci is not None and co is not None and co > ci:
        brk = max(0, min(int(break_minutes or 0), co - ci))
        worked_minutes = max(0, co - ci - brk)

    if is_scheduled and ci is not None and ss is not None and ci > ss + grace:
        late_minutes = ci - ss - grace

    late_penalty = min(late_minutes * pen_per, pen_max) if late_minutes > 0 else 0
    worked_hours = round(worked_minutes / 60.0, 2)

    shift_span = 0
    if ss is not None and se is not None and se > ss:
        shift_span = se - ss - break_default
    expected_hours = round(max(shift_span, int(std_hours * 60)) / 60.0, 2)

    return {
        "is_scheduled_workday": is_scheduled,
        "worked_minutes": worked_minutes,
        "worked_hours": worked_hours,
        "expected_hours": expected_hours,
        "late_minutes": late_minutes,
        "late_penalty_vnd": late_penalty,
        "has_full_punch": ci is not None and co is not None,
        "shift_start": shift_start,
        "shift_end": shift_end,
        "weekday_label": WEEKDAY_LABELS[wd] if 0 <= wd <= 6 else "",
    }


def hourly_rate_vnd(base_salary_vnd: int, year: int, month: int, policy: dict[str, Any]) -> float:
    denom = expected_standard_hours_in_month(year, month, policy)
    if base_salary_vnd <= 0 or denom <= 0:
        return 0.0
    return base_salary_vnd / denom


def compute_staff_payroll(
    conn: sqlite3.Connection,
    *,
    staff_id: int,
    base_salary_vnd: int,
    position_id: int | None,
    year: int,
    month: int,
    policy: dict[str, Any],
    position_map: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    d0 = f"{year:04d}-{month:02d}-01"
    _, last = monthrange(year, month)
    d1 = f"{year:04d}-{month:02d}-{last:02d}"

    rows = conn.execute(
        """
        SELECT work_date, check_in, check_out, break_minutes
        FROM crm_attendance
        WHERE staff_id = ? AND work_date >= ? AND work_date <= ?
        ORDER BY work_date ASC
        """,
        (staff_id, d0, d1),
    ).fetchall()

    rate = hourly_rate_vnd(base_salary_vnd, year, month, policy)
    total_hours = 0.0
    late_minutes_total = 0
    late_deduction = 0
    days_present = 0

    for r in rows:
        day = analyze_attendance_day(
            work_date=str(r["work_date"]),
            check_in=str(r["check_in"] or ""),
            check_out=str(r["check_out"] or ""),
            break_minutes=int(r["break_minutes"] or 0),
            policy=policy,
        )
        if not day["has_full_punch"]:
            continue
        days_present += 1
        total_hours += day["worked_hours"]
        late_minutes_total += day["late_minutes"]
        late_deduction += day["late_penalty_vnd"]

    salary_from_hours = round(total_hours * rate)

    pos = position_map.get(int(position_id)) if position_id else None
    position_allowance = int(pos["allowance_vnd"]) if pos else 0
    pos_bonus_pct = float(pos["bonus_pct"]) if pos else 0.0

    bonus_vnd = 0
    bonus_mode = str(policy.get("bonus_mode") or "none").strip().lower()
    policy_bonus_pct = float(policy.get("bonus_pct") or 0)
    bonus_min_days = int(policy.get("bonus_min_days") or 0)

    if bonus_mode != "none" and days_present >= bonus_min_days and base_salary_vnd > 0:
        pct = policy_bonus_pct + pos_bonus_pct
        bonus_vnd = round(base_salary_vnd * pct / 100.0)

    manual_allow = 0
    manual_ded = 0
    return {
        "days_present": days_present,
        "hours_worked_total": round(total_hours, 2),
        "late_minutes_total": late_minutes_total,
        "late_deduction_vnd": late_deduction,
        "hourly_rate_vnd": round(rate),
        "salary_from_attendance_vnd": salary_from_hours,
        "position_allowance_vnd": position_allowance,
        "bonus_vnd": bonus_vnd,
        "allowances_vnd": position_allowance + bonus_vnd + manual_allow,
        "deductions_vnd": late_deduction + manual_ded,
        "net_salary_vnd": salary_from_hours + position_allowance + bonus_vnd - late_deduction,
    }


def enrich_attendance_row(row: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    day = analyze_attendance_day(
        work_date=str(row.get("work_date") or ""),
        check_in=str(row.get("check_in") or ""),
        check_out=str(row.get("check_out") or ""),
        break_minutes=int(row.get("break_minutes") or 0),
        policy=policy,
    )
    out = dict(row)
    out.update(day)
    return out


def dashboard_summary(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    policy: dict[str, Any],
) -> dict[str, Any]:
    d0 = f"{year:04d}-{month:02d}-01"
    _, last = monthrange(year, month)
    d1 = f"{year:04d}-{month:02d}-{last:02d}"
    today = datetime.now().strftime("%Y-%m-%d")

    staff_n = conn.execute("SELECT COUNT(*) AS n FROM crm_staff WHERE active = 1").fetchone()
    att_month = conn.execute(
        """
        SELECT COUNT(*) AS n FROM crm_attendance
        WHERE work_date >= ? AND work_date <= ?
          AND trim(check_in) != '' AND trim(check_out) != ''
        """,
        (d0, d1),
    ).fetchone()
    att_today = conn.execute(
        """
        SELECT COUNT(*) AS n FROM crm_attendance
        WHERE work_date = ? AND trim(check_in) != ''
        """,
        (today,),
    ).fetchone()

    late_count = 0
    total_hours = 0.0
    rows = conn.execute(
        """
        SELECT work_date, check_in, check_out, break_minutes
        FROM crm_attendance WHERE work_date >= ? AND work_date <= ?
        """,
        (d0, d1),
    ).fetchall()
    for r in rows:
        day = analyze_attendance_day(
            work_date=str(r["work_date"]),
            check_in=str(r["check_in"] or ""),
            check_out=str(r["check_out"] or ""),
            break_minutes=int(r["break_minutes"] or 0),
            policy=policy,
        )
        if day["late_minutes"] > 0:
            late_count += 1
        total_hours += day["worked_hours"]

    weekdays = parse_work_weekdays(work_weekdays_from_shifts(parse_weekday_shifts(policy)))
    std_days = count_workdays_in_month(year, month, weekdays)
    std_hours_month = expected_standard_hours_in_month(year, month, policy)

    return {
        "year": year,
        "month": month,
        "staff_active": int(staff_n["n"]) if staff_n else 0,
        "attendance_records_month": int(att_month["n"]) if att_month else 0,
        "checked_in_today": int(att_today["n"]) if att_today else 0,
        "late_incidents_month": late_count,
        "total_hours_month": round(total_hours, 1),
        "workdays_standard": std_days,
        "standard_hours_month": round(std_hours_month, 1),
        "policy": policy_for_api(policy),
    }
