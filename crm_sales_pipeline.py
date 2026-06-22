"""Pipeline bán hàng thống nhất — giai đoạn, gán lead, tự động hóa, phễu."""
from __future__ import annotations

import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any

import sqlite3

# --- Giai đoạn phễu bán hàng (mọi sales làm theo cùng quy trình) ---
SALES_PIPELINE_STAGES: tuple[str, ...] = (
    "moi",
    "dang_lien_he",
    "mql",
    "sql",
    "bao_gia",
    "chot",
    "mat",
)

SALES_PIPELINE_LABELS_VI: dict[str, str] = {
    "moi": "Mới",
    "dang_lien_he": "Đang liên hệ",
    "mql": "MQL",
    "sql": "SQL",
    "bao_gia": "Báo giá",
    "chot": "Chốt",
    "mat": "Mất",
}

# SLA (giờ) — cảnh báo nếu lead ở giai đoạn quá lâu
STAGE_SLA_HOURS: dict[str, int] = {
    "moi": 4,
    "dang_lien_he": 24,
    "mql": 72,
    "sql": 120,
    "bao_gia": 168,
    "chot": 0,
    "mat": 0,
}

# Nhắc việc tự động sau khi vào giai đoạn (giờ)
STAGE_FOLLOWUP_HOURS: dict[str, int] = {
    "moi": 4,
    "dang_lien_he": 24,
    "mql": 48,
    "sql": 72,
    "bao_gia": 48,
    "chot": 0,
    "mat": 0,
}

# Vai trò phụ trách mặc định theo giai đoạn
STAGE_OWNER_ROLE: dict[str, str] = {
    "moi": "CSKH / ca trực",
    "dang_lien_he": "Sales",
    "mql": "Sales",
    "sql": "Sales",
    "bao_gia": "Sales",
    "chot": "Account / CS",
    "mat": "Sales",
}

# Đồng bộ cột Kanban CSKH cũ (backward compat)
PIPELINE_TO_LEGACY_STATUS: dict[str, str] = {
    "moi": "tiep_nhan",
    "dang_lien_he": "dang_xu_ly",
    "mql": "dang_xu_ly",
    "sql": "cho_khach",
    "bao_gia": "cho_khach",
    "chot": "da_giai_quyet",
    "mat": "dong",
}

LEGACY_STATUS_TO_PIPELINE: dict[str, str] = {
    "tiep_nhan": "moi",
    "dang_xu_ly": "dang_lien_he",
    "cho_khach": "sql",
    "da_giai_quyet": "chot",
    "dong": "mat",
}

TERMINAL_STAGES: frozenset[str] = frozenset({"chot", "mat"})

ASSIGNMENT_POOL_KD = "kd_round_robin"


def normalize_pipeline_stage(raw: str | None) -> str:
    s = str(raw or "moi").strip().lower()
    return s if s in SALES_PIPELINE_STAGES else "moi"


def legacy_status_for_stage(stage: str) -> str:
    return PIPELINE_TO_LEGACY_STATUS.get(normalize_pipeline_stage(stage), "tiep_nhan")


def pipeline_stage_label(stage: str) -> str:
    return SALES_PIPELINE_LABELS_VI.get(normalize_pipeline_stage(stage), stage)


def _parse_ts(ts: str | None) -> datetime | None:
    raw = str(ts or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[: len(fmt.replace("%", "0"))], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")[:19])
    except ValueError:
        return None


def hours_in_stage(stage_entered_at: str | None, *, now: datetime | None = None) -> float:
    entered = _parse_ts(stage_entered_at)
    if entered is None:
        return 0.0
    ref = now or datetime.now()
    return max(0.0, (ref - entered).total_seconds() / 3600.0)


def is_sla_overdue(stage: str, stage_entered_at: str | None, *, now: datetime | None = None) -> bool:
    st = normalize_pipeline_stage(stage)
    sla = STAGE_SLA_HOURS.get(st, 0)
    if sla <= 0 or st in TERMINAL_STAGES:
        return False
    return hours_in_stage(stage_entered_at, now=now) > sla


def _crm_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _short_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _remind_at_after_hours(hours: int) -> str:
    dt = datetime.now() + timedelta(hours=max(1, hours))
    return dt.strftime("%Y-%m-%d")


def ensure_pipeline_schema(conn: sqlite3.Connection) -> None:
    """Thêm cột pipeline + bảng round-robin nếu chưa có."""
    cc = {r[1] for r in conn.execute("PRAGMA table_info(crm_cases)")}
    alters = [
        ("pipeline_stage", "ALTER TABLE crm_cases ADD COLUMN pipeline_stage TEXT NOT NULL DEFAULT 'moi'"),
        ("stage_entered_at", "ALTER TABLE crm_cases ADD COLUMN stage_entered_at TEXT NOT NULL DEFAULT ''"),
        ("lead_source", "ALTER TABLE crm_cases ADD COLUMN lead_source TEXT NOT NULL DEFAULT ''"),
        ("deal_value_vnd", "ALTER TABLE crm_cases ADD COLUMN deal_value_vnd INTEGER"),
    ]
    for col, ddl in alters:
        if col not in cc:
            try:
                conn.execute(ddl)
            except sqlite3.Error:
                pass

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_assignment_state (
            pool_key TEXT PRIMARY KEY,
            last_staff_id INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_cases_pipeline ON crm_cases(pipeline_stage, stage_entered_at)"
    )

    # Backfill pipeline_stage từ status cũ
    try:
        conn.execute(
            """
            UPDATE crm_cases
            SET pipeline_stage = CASE status
                WHEN 'tiep_nhan' THEN 'moi'
                WHEN 'dang_xu_ly' THEN 'dang_lien_he'
                WHEN 'cho_khach' THEN 'sql'
                WHEN 'da_giai_quyet' THEN 'chot'
                WHEN 'dong' THEN 'mat'
                ELSE 'moi'
            END
            WHERE pipeline_stage IS NULL OR TRIM(pipeline_stage) = ''
            """
        )
        conn.execute(
            """
            UPDATE crm_cases
            SET stage_entered_at = COALESCE(NULLIF(TRIM(stage_entered_at), ''), updated_at, created_at)
            WHERE TRIM(COALESCE(stage_entered_at, '')) = ''
            """
        )
    except sqlite3.Error:
        pass


def _get_kd_staff_ids(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        """
        SELECT s.id FROM crm_staff s
        LEFT JOIN crm_departments d ON d.id = s.department_id
        WHERE s.active = 1
          AND (
            lower(trim(COALESCE(d.code, ''))) = 'kd'
            OR lower(trim(COALESCE(d.name, ''))) LIKE '%kinh doanh%'
          )
        ORDER BY s.id ASC
        """
    ).fetchall()
    ids = [int(r["id"]) for r in rows]
    if ids:
        return ids
    rows = conn.execute(
        "SELECT id FROM crm_staff WHERE active = 1 ORDER BY id ASC"
    ).fetchall()
    return [int(r["id"]) for r in rows]


def round_robin_assign(
    conn: sqlite3.Connection,
    *,
    pool_key: str = ASSIGNMENT_POOL_KD,
    prefer_staff_id: int | None = None,
) -> tuple[str, int | None]:
    """Gán lead theo round-robin trong pool KD (hoặc toàn bộ staff active)."""
    if prefer_staff_id:
        row = conn.execute(
            "SELECT name FROM crm_staff WHERE id = ? AND active = 1",
            (prefer_staff_id,),
        ).fetchone()
        if row:
            return str(row["name"]), prefer_staff_id

    staff_ids = _get_kd_staff_ids(conn)
    if not staff_ids:
        return "", None

    state = conn.execute(
        "SELECT last_staff_id FROM crm_assignment_state WHERE pool_key = ?",
        (pool_key,),
    ).fetchone()
    last_id = int(state["last_staff_id"]) if state else 0
    try:
        idx = staff_ids.index(last_id)
        next_id = staff_ids[(idx + 1) % len(staff_ids)]
    except ValueError:
        next_id = staff_ids[0]

    ts = _crm_ts()
    conn.execute(
        """
        INSERT INTO crm_assignment_state (pool_key, last_staff_id, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(pool_key) DO UPDATE SET
            last_staff_id = excluded.last_staff_id,
            updated_at = excluded.updated_at
        """,
        (pool_key, next_id, ts),
    )
    row = conn.execute("SELECT name FROM crm_staff WHERE id = ?", (next_id,)).fetchone()
    name = str(row["name"]) if row else ""
    return name, next_id


def _delete_stage_followups(conn: sqlite3.Connection, case_id: int) -> None:
    conn.execute(
        """
        DELETE FROM crm_reminders
        WHERE scope = 'case' AND ref_id = ? AND reminder_kind = 'status_followup'
          AND status = 'pending'
        """,
        (case_id,),
    )


def _create_stage_followup_reminder(
    conn: sqlite3.Connection,
    case_id: int,
    stage: str,
    staff_id: int | None,
    case_title: str,
) -> None:
    hours = STAGE_FOLLOWUP_HOURS.get(normalize_pipeline_stage(stage), 0)
    if hours <= 0 or stage in TERMINAL_STAGES:
        return
    label = pipeline_stage_label(stage)
    ts = _crm_ts()
    remind_at = _remind_at_after_hours(hours)
    conn.execute(
        """
        INSERT INTO crm_reminders (
            scope, ref_id, reminder_kind, title, body, remind_at,
            status, staff_id, meta_json, created_at, updated_at
        )
        VALUES ('case', ?, 'status_followup', ?, ?, ?, 'pending', ?, ?, ?, ?)
        """,
        (
            case_id,
            f"[Pipeline {label}] {case_title[:200]}",
            f"Theo dõi giai đoạn {label} — SLA {STAGE_SLA_HOURS.get(stage, 0)}h.",
            remind_at,
            staff_id,
            "{}",
            _short_date(),
            ts,
        ),
    )


def send_pipeline_notify_email(
    *,
    to_email: str,
    subject: str,
    body: str,
) -> bool:
    """Gửi email thông báo pipeline (best-effort, không raise)."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    sender = os.getenv("SMTP_FROM", smtp_username).strip()
    if not to_email or not smtp_username or not smtp_password or not sender:
        return False
    msg = EmailMessage()
    msg["Subject"] = subject[:200]
    msg["From"] = sender
    msg["To"] = to_email.strip()
    msg.set_content(body)
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        return True
    except OSError:
        return False


def notify_assignee_new_lead(
    conn: sqlite3.Connection,
    case_id: int,
    staff_id: int | None,
    title: str,
    stage: str,
) -> None:
    if not staff_id:
        return
    row = conn.execute(
        "SELECT name, email FROM crm_staff WHERE id = ? AND active = 1",
        (staff_id,),
    ).fetchone()
    if not row or not str(row["email"] or "").strip():
        return
    label = pipeline_stage_label(stage)
    body = (
        f"Bạn được gán phụ trách lead #{case_id}.\n\n"
        f"Tiêu đề: {title}\n"
        f"Giai đoạn: {label}\n"
        f"Vai trò: {STAGE_OWNER_ROLE.get(normalize_pipeline_stage(stage), 'Sales')}\n\n"
        "Vui lòng liên hệ khách trong SLA và cập nhật CRM."
    )
    send_pipeline_notify_email(
        to_email=str(row["email"]),
        subject=f"[CRM PTT] Lead mới #{case_id} — {label}",
        body=body,
    )


def notify_assignee_stage_change(
    conn: sqlite3.Connection,
    case_id: int,
    staff_id: int | None,
    title: str,
    old_stage: str,
    new_stage: str,
) -> None:
    if not staff_id:
        return
    row = conn.execute(
        "SELECT name, email FROM crm_staff WHERE id = ? AND active = 1",
        (staff_id,),
    ).fetchone()
    if not row or not str(row["email"] or "").strip():
        return
    old_l = pipeline_stage_label(old_stage)
    new_l = pipeline_stage_label(new_stage)
    body = (
        f"Lead #{case_id} chuyển giai đoạn: {old_l} → {new_l}.\n\n"
        f"Tiêu đề: {title}\n"
        f"Phụ trách: {STAGE_OWNER_ROLE.get(normalize_pipeline_stage(new_stage), 'Sales')}\n\n"
        "Kiểm tra nhắc việc và cập nhật timeline trên Bảng CSKH."
    )
    send_pipeline_notify_email(
        to_email=str(row["email"]),
        subject=f"[CRM PTT] #{case_id} → {new_l}",
        body=body,
    )


def on_case_created(
    conn: sqlite3.Connection,
    case_id: int,
    *,
    title: str,
    priority: str,
    assigned_staff_id: int | None,
    assigned_to: str,
    lead_source: str = "",
    auto_assign: bool = True,
) -> tuple[str, int | None]:
    """Khởi tạo pipeline + gán tự động nếu chưa có phụ trách."""
    ts = _crm_ts()
    stage = "moi"
    ato, aid = assigned_to, assigned_staff_id
    if auto_assign and not aid:
        ato, aid = round_robin_assign(conn)

    ls_val = lead_source[:120] if lead_source else ""
    conn.execute(
        """
        UPDATE crm_cases
        SET pipeline_stage = ?, stage_entered_at = ?, status = ?,
            lead_source = CASE WHEN ? != '' THEN ? ELSE lead_source END,
            assigned_to = ?, assigned_staff_id = ?,
            assigned_at = CASE WHEN ? IS NOT NULL THEN ? ELSE assigned_at END,
            updated_at = ?
        WHERE id = ?
        """,
        (
            stage,
            ts,
            legacy_status_for_stage(stage),
            ls_val,
            ls_val,
            ato,
            aid,
            aid,
            ts if aid else "",
            ts,
            case_id,
        ),
    )

    _delete_stage_followups(conn, case_id)
    followup_h = 1 if priority == "cao" else STAGE_FOLLOWUP_HOURS.get(stage, 4)
    remind_at = _remind_at_after_hours(followup_h)
    conn.execute(
        """
        INSERT INTO crm_reminders (
            scope, ref_id, reminder_kind, title, body, remind_at,
            status, staff_id, meta_json, created_at, updated_at
        )
        VALUES ('case', ?, 'status_followup', ?, ?, ?, 'pending', ?, ?, ?, ?)
        """,
        (
            case_id,
            f"[Liên hệ lần 1] {title[:200]}",
            "Lead mới — liên hệ khách trong SLA (≤15 phút nếu hot, ≤4h nếu thường).",
            remind_at,
            aid,
            "{}",
            _short_date(),
            ts,
        ),
    )

    if aid:
        notify_assignee_new_lead(conn, case_id, aid, title, stage)

    return ato, aid


def on_pipeline_stage_change(
    conn: sqlite3.Connection,
    case_id: int,
    *,
    old_stage: str,
    new_stage: str,
    title: str,
    assigned_staff_id: int | None,
    append_event: Any,
) -> None:
    """Cập nhật giai đoạn: đồng bộ status, nhắc việc, email."""
    ns = normalize_pipeline_stage(new_stage)
    os_ = normalize_pipeline_stage(old_stage)
    if ns == os_:
        return
    ts = _crm_ts()
    conn.execute(
        """
        UPDATE crm_cases
        SET pipeline_stage = ?, stage_entered_at = ?, status = ?, updated_at = ?
        WHERE id = ?
        """,
        (ns, ts, legacy_status_for_stage(ns), ts, case_id),
    )
    append_event(
        conn,
        case_id,
        "pipeline",
        f"Chuyển giai đoạn pipeline: {pipeline_stage_label(os_)} → {pipeline_stage_label(ns)}.",
    )
    _delete_stage_followups(conn, case_id)
    _create_stage_followup_reminder(conn, case_id, ns, assigned_staff_id, title)
    notify_assignee_stage_change(conn, case_id, assigned_staff_id, title, os_, ns)


def enrich_case_row(d: dict[str, Any]) -> dict[str, Any]:
    """Thêm nhãn pipeline + cờ SLA cho API response."""
    stage = normalize_pipeline_stage(d.get("pipeline_stage") or d.get("status"))
    d["pipeline_stage"] = stage
    d["pipeline_stage_label"] = pipeline_stage_label(stage)
    d["stage_owner_role"] = STAGE_OWNER_ROLE.get(stage, "Sales")
    d["stage_sla_hours"] = STAGE_SLA_HOURS.get(stage, 0)
    entered = d.get("stage_entered_at") or d.get("updated_at") or ""
    d["stage_hours"] = round(hours_in_stage(entered), 1)
    d["sla_overdue"] = is_sla_overdue(stage, entered)
    return d


def compute_funnel_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Phễu bán hàng + hiệu suất sales + điểm nghẽn."""
    now = datetime.now()
    rows = conn.execute(
        """
        SELECT c.id, c.pipeline_stage, c.stage_entered_at, c.status, c.channel,
               c.priority, c.assigned_staff_id, c.lead_source, c.deal_value_vnd,
               c.created_at, st.name AS staff_name
        FROM crm_cases c
        LEFT JOIN crm_staff st ON st.id = c.assigned_staff_id
        """
    ).fetchall()

    stage_counts: dict[str, int] = {s: 0 for s in SALES_PIPELINE_STAGES}
    stage_hours_sum: dict[str, float] = {s: 0.0 for s in SALES_PIPELINE_STAGES}
    stage_hours_n: dict[str, int] = {s: 0 for s in SALES_PIPELINE_STAGES}
    by_staff: dict[str, dict[str, Any]] = {}
    by_channel: dict[str, int] = {}
    unassigned = 0
    sla_overdue = 0
    open_pipeline = 0
    total_deal = 0

    for row in rows:
        d = dict(row)
        stage = normalize_pipeline_stage(d.get("pipeline_stage") or d.get("status"))
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        if stage not in TERMINAL_STAGES:
            open_pipeline += 1
        entered = d.get("stage_entered_at") or d.get("created_at") or ""
        hrs = hours_in_stage(entered, now=now)
        stage_hours_sum[stage] = stage_hours_sum.get(stage, 0.0) + hrs
        stage_hours_n[stage] = stage_hours_n.get(stage, 0) + 1
        if is_sla_overdue(stage, entered, now=now):
            sla_overdue += 1
        if not d.get("assigned_staff_id"):
            unassigned += 1

        ch = str(d.get("channel") or "khac")
        by_channel[ch] = by_channel.get(ch, 0) + 1

        staff_key = str(d.get("staff_name") or "— Chưa gán")
        if staff_key not in by_staff:
            by_staff[staff_key] = {"open": 0, "won": 0, "lost": 0, "overdue": 0}
        bucket = by_staff[staff_key]
        if stage == "chot":
            bucket["won"] += 1
        elif stage == "mat":
            bucket["lost"] += 1
        elif stage not in TERMINAL_STAGES:
            bucket["open"] += 1
        if is_sla_overdue(stage, entered, now=now):
            bucket["overdue"] += 1

        try:
            total_deal += int(d.get("deal_value_vnd") or 0)
        except (TypeError, ValueError):
            pass

    stages_out = []
    prev_count: int | None = None
    for st in SALES_PIPELINE_STAGES:
        cnt = stage_counts.get(st, 0)
        avg_h = (
            round(stage_hours_sum[st] / stage_hours_n[st], 1)
            if stage_hours_n.get(st, 0) > 0
            else 0.0
        )
        conv = None
        if prev_count is not None and prev_count > 0:
            conv = round(100.0 * cnt / prev_count, 1)
        stages_out.append(
            {
                "stage": st,
                "label": pipeline_stage_label(st),
                "count": cnt,
                "avg_hours": avg_h,
                "sla_hours": STAGE_SLA_HOURS.get(st, 0),
                "conversion_from_prev_pct": conv,
                "owner_role": STAGE_OWNER_ROLE.get(st, ""),
            }
        )
        if st not in TERMINAL_STAGES:
            prev_count = cnt

    # Điểm nghẽn: giai đoạn mở có nhiều lead + thời gian trung bình cao
    bottlenecks = []
    for item in stages_out:
        st = item["stage"]
        if st in TERMINAL_STAGES:
            continue
        score = item["count"] * (item["avg_hours"] / max(1, item["sla_hours"] or 1))
        if item["count"] >= 2 and (item["avg_hours"] > item["sla_hours"] or score >= 3):
            bottlenecks.append(
                {
                    "stage": st,
                    "label": item["label"],
                    "count": item["count"],
                    "avg_hours": item["avg_hours"],
                    "sla_hours": item["sla_hours"],
                    "severity": "high" if item["avg_hours"] > item["sla_hours"] else "medium",
                }
            )
    bottlenecks.sort(key=lambda x: (-x["count"], -x["avg_hours"]))

    total = len(rows)
    won = stage_counts.get("chot", 0)
    lost = stage_counts.get("mat", 0)
    closed = won + lost
    win_rate = round(100.0 * won / closed, 1) if closed > 0 else None

    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "totals": {
            "cases": total,
            "open_pipeline": open_pipeline,
            "unassigned": unassigned,
            "sla_overdue": sla_overdue,
            "won": won,
            "lost": lost,
            "win_rate_pct": win_rate,
            "pipeline_value_vnd": total_deal,
        },
        "stages": stages_out,
        "by_staff": by_staff,
        "by_channel": by_channel,
        "bottlenecks": bottlenecks[:5],
    }
