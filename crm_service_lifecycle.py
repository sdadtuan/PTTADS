# crm_service_lifecycle.py
"""Service Lifecycle — orchestration layer kết nối 12 dịch vụ PTTP theo chu trình thống nhất."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

VALID_STAGES: tuple[str, ...] = (
    "lead", "consult", "proposal", "onboard", "deliver", "handover", "retain"
)
VALID_STATUSES: tuple[str, ...] = ("draft", "active", "closed", "lost")


class StageAdvanceError(ValueError):
    """Không thể chuyển giai đoạn Service Delivery."""


def stage_index(stage: str) -> int:
    key = str(stage or "").strip()
    try:
        return VALID_STAGES.index(key)
    except ValueError:
        return 0


def next_stage(stage: str) -> str | None:
    idx = stage_index(stage)
    if idx < 0 or idx >= len(VALID_STAGES) - 1:
        return None
    return VALID_STAGES[idx + 1]


def is_stage_tasks_complete(
    conn: sqlite3.Connection, lifecycle_id: int, stage: str
) -> bool:
    from crm_svc_tasks import is_stage_complete

    return is_stage_complete(conn, lifecycle_id, stage)


def validate_stage_advance(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    from_stage: str,
    to_stage: str,
) -> None:
    """Chỉ cho phép lùi tự do; tiến lên phải tuần tự và hoàn thành task giai đoạn hiện tại."""
    if to_stage not in VALID_STAGES:
        raise StageAdvanceError(f"Stage không hợp lệ: {to_stage}")
    from_idx = stage_index(from_stage)
    to_idx = stage_index(to_stage)
    if to_idx == from_idx:
        return
    if to_idx < from_idx:
        return
    if to_idx != from_idx + 1:
        raise StageAdvanceError(
            "Chỉ được chuyển sang bước kế tiếp. Hoàn thành từng giai đoạn theo thứ tự."
        )
    if not is_stage_tasks_complete(conn, lifecycle_id, from_stage):
        raise StageAdvanceError(
            "Hoàn thành tất cả task của giai đoạn hiện tại trước khi chuyển bước."
        )
    if to_stage == "deliver" and from_stage == "onboard":
        try:
            from crm_lead_presales_marketing_plan import validate_lifecycle_deliver_advance

            tmmt_gate = validate_lifecycle_deliver_advance(conn, lifecycle_id)
            if not tmmt_gate.get("ok"):
                raise StageAdvanceError(
                    (tmmt_gate.get("messages") or ["TMMT chưa đủ"])[0]
                )
        except StageAdvanceError:
            raise
        except Exception as exc:
            raise StageAdvanceError(str(exc) or "Không kiểm tra được TMMT.") from exc


def get_stage_advance_info(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT stage FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
    ).fetchone()
    if row is None:
        return {}
    current = str(row["stage"] or "lead")
    nxt = next_stage(current)
    complete = is_stage_tasks_complete(conn, lifecycle_id, current)
    from crm_svc_tasks import get_progress

    prog = get_progress(conn, lifecycle_id).get(current, {})
    block_reason = ""
    can_forward = False
    if nxt is None:
        block_reason = "Đã ở giai đoạn cuối."
    elif not complete:
        block_reason = "Hoàn thành tất cả task giai đoạn hiện tại trước khi chuyển bước."
    elif nxt == "deliver" and current == "onboard":
        try:
            from crm_lead_presales_marketing_plan import validate_lifecycle_deliver_advance

            tmmt_gate = validate_lifecycle_deliver_advance(conn, lifecycle_id)
            if not tmmt_gate.get("ok"):
                block_reason = (tmmt_gate.get("messages") or ["TMMT chưa đủ"])[0]
            else:
                can_forward = True
        except Exception as exc:
            block_reason = str(exc) or "Không kiểm tra được TMMT."
    else:
        can_forward = True
    return {
        "current_stage": current,
        "next_stage": nxt,
        "can_advance_forward": can_forward,
        "block_reason": block_reason,
        "current_complete": complete,
        "current_done": prog.get("done", 0),
        "current_total": prog.get("total", 0),
    }

VALID_SLUGS: frozenset[str] = frozenset({
    "dich-vu-aeo", "dich-vu-seo-tong-the", "dich-vu-seo-local",
    "dich-vu-seo-audit", "dich-vu-quan-tri-website",
    "thiet-ke-website", "thiet-ke-website-tron-goi", "thiet-ke-landing-page",
    "quang-cao-facebook", "quang-cao-google", "thue-tai-khoan-quang-cao",
    "tiep-thi-noi-dung",
})


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Tạo 2 bảng + migration crm_contracts.service_slug. Gọi lúc app init."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id          INTEGER REFERENCES crm_leads(id) ON DELETE SET NULL,
            customer_id      INTEGER REFERENCES crm_customers(id) ON DELETE SET NULL,
            contract_id      INTEGER REFERENCES crm_contracts(id) ON DELETE SET NULL,
            service_slug     TEXT NOT NULL DEFAULT '',
            stage            TEXT NOT NULL DEFAULT 'lead',
            status           TEXT NOT NULL DEFAULT 'draft',
            assigned_am      INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            assigned_sp      INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            stage_entered_at TEXT NOT NULL DEFAULT '',
            notes            TEXT NOT NULL DEFAULT '',
            created_at       TEXT NOT NULL DEFAULT '',
            updated_at       TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svclife_lead ON crm_service_lifecycle(lead_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svclife_customer ON crm_service_lifecycle(customer_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svclife_contract ON crm_service_lifecycle(contract_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svclife_status ON crm_service_lifecycle(status, stage)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            from_stage   TEXT,
            to_stage     TEXT NOT NULL,
            actor_id     INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            actor_type   TEXT NOT NULL DEFAULT 'human',
            notes        TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svclife_events_lc ON crm_service_lifecycle_events(lifecycle_id)"
    )
    # Migration: thêm service_slug vào crm_contracts nếu chưa có
    try:
        conn.execute(
            "ALTER TABLE crm_contracts ADD COLUMN service_slug TEXT NOT NULL DEFAULT ''"
        )
    except Exception:
        pass  # Column đã tồn tại
    _lc_cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_service_lifecycle)")}
    if "marketing_plan_id" not in _lc_cols:
        try:
            conn.execute(
                "ALTER TABLE crm_service_lifecycle ADD COLUMN marketing_plan_id INTEGER"
            )
        except Exception:
            pass
    try:
        backfill_assigned_am_from_leads(conn)
    except Exception as exc:
        logger.warning("backfill_assigned_am_from_leads: %s", exc)
    conn.commit()


def lead_owner_staff_id(conn: sqlite3.Connection, lead_id: int | None) -> int | None:
    """Map crm_leads.owner_id → crm_staff.id (chỉ NV active)."""
    if not lead_id:
        return None
    try:
        row = conn.execute(
            "SELECT owner_id FROM crm_leads WHERE id = ?",
            (int(lead_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None or not row["owner_id"]:
        return None
    sid = int(row["owner_id"])
    staff = conn.execute(
        "SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1",
        (sid,),
    ).fetchone()
    return sid if staff else None


def sync_assigned_am_from_lead(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    *,
    overwrite: bool = False,
) -> bool:
    """Gán assigned_am từ owner lead liên kết. Trả True nếu đã cập nhật."""
    row = conn.execute(
        "SELECT lead_id, assigned_am FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if row is None:
        return False
    owner_id = lead_owner_staff_id(conn, int(row["lead_id"]) if row["lead_id"] else None)
    if owner_id is None:
        return False
    if not overwrite and row["assigned_am"] is not None:
        return False
    if int(row["assigned_am"] or 0) == owner_id:
        return False
    ts = _ts()
    conn.execute(
        """
        UPDATE crm_service_lifecycle
        SET assigned_am = ?, updated_at = ?
        WHERE id = ?
        """,
        (owner_id, ts, int(lifecycle_id)),
    )
    conn.commit()
    return True


def sync_assigned_am_for_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    overwrite: bool = False,
) -> int:
    """Đồng bộ assigned_am cho mọi lifecycle của lead. Trả số bản ghi đã cập nhật."""
    rows = conn.execute(
        "SELECT id FROM crm_service_lifecycle WHERE lead_id = ?",
        (int(lead_id),),
    ).fetchall()
    updated = 0
    for row in rows:
        if sync_assigned_am_from_lead(conn, int(row["id"]), overwrite=overwrite):
            updated += 1
    return updated


def backfill_assigned_am_from_leads(conn: sqlite3.Connection) -> int:
    """Idempotent: lifecycle có lead owner nhưng chưa assigned_am → gán AM."""
    rows = conn.execute(
        """
        SELECT id FROM crm_service_lifecycle
        WHERE lead_id IS NOT NULL AND assigned_am IS NULL
        """
    ).fetchall()
    updated = 0
    for row in rows:
        if sync_assigned_am_from_lead(conn, int(row["id"]), overwrite=False):
            updated += 1
    return updated


def backfill_assigned_am_for_staff(
    conn: sqlite3.Connection, staff_id: int
) -> dict[str, int]:
    """Backfill toàn cục + đồng bộ lifecycle của mọi lead thuộc staff (idempotent)."""
    global_updated = backfill_assigned_am_from_leads(conn)
    staff_updated = 0
    rows = conn.execute(
        "SELECT id FROM crm_leads WHERE owner_id = ?",
        (int(staff_id),),
    ).fetchall()
    for row in rows:
        staff_updated += sync_assigned_am_for_lead(
            conn, int(row["id"]), overwrite=False
        )
    return {
        "global_updated": global_updated,
        "staff_updated": staff_updated,
        "total_updated": global_updated + staff_updated,
    }


def resolve_staff_id_by_name(conn: sqlite3.Connection, name: str) -> int | None:
    """Khớp tên NV active — dùng sync SP từ task form field text."""
    text = str(name or "").strip()
    if not text or text.isdigit():
        if text.isdigit():
            row = conn.execute(
                "SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1",
                (int(text),),
            ).fetchone()
            return int(row["id"]) if row else None
        return None
    row = conn.execute(
        """
        SELECT id FROM crm_staff
        WHERE COALESCE(active, 1) = 1 AND trim(name) = ?
        LIMIT 1
        """,
        (text,),
    ).fetchone()
    if row is not None:
        return int(row["id"])
    row = conn.execute(
        """
        SELECT id FROM crm_staff
        WHERE COALESCE(active, 1) = 1 AND lower(trim(name)) = lower(?)
        LIMIT 1
        """,
        (text,),
    ).fetchone()
    return int(row["id"]) if row else None


def set_assigned_sp(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    staff_id: int | None,
    *,
    overwrite: bool = True,
) -> bool:
    """Gán hoặc gỡ Specialist trên lifecycle. Trả True nếu đã cập nhật."""
    row = conn.execute(
        "SELECT assigned_sp FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if row is None:
        raise ValueError("Không tìm thấy lifecycle.")
    current = row["assigned_sp"]
    if staff_id is not None:
        staff = conn.execute(
            "SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1",
            (int(staff_id),),
        ).fetchone()
        if staff is None:
            raise ValueError("Nhân viên SP không hợp lệ hoặc không active.")
        new_id = int(staff_id)
    else:
        new_id = None
    if not overwrite and current is not None:
        return False
    if (current is None and new_id is None) or (
        current is not None and new_id is not None and int(current) == new_id
    ):
        return False
    ts = _ts()
    conn.execute(
        """
        UPDATE crm_service_lifecycle
        SET assigned_sp = ?, updated_at = ?
        WHERE id = ?
        """,
        (new_id, ts, int(lifecycle_id)),
    )
    conn.commit()
    return True


def suggest_sp_from_tasks(conn: sqlite3.Connection, lifecycle_id: int) -> int | None:
    """Đọc field assigned_sp trong task Lead/Onboard — khớp tên crm_staff."""
    rows = conn.execute(
        """
        SELECT form_data FROM crm_svc_tasks
        WHERE lifecycle_id = ? AND stage IN ('lead', 'onboard')
        ORDER BY CASE stage WHEN 'lead' THEN 0 ELSE 1 END, step_index, id
        """,
        (int(lifecycle_id),),
    ).fetchall()
    for row in rows:
        try:
            form_data = json.loads(str(row["form_data"] or "{}"))
        except json.JSONDecodeError:
            continue
        if not isinstance(form_data, dict):
            continue
        for key in ("assigned_sp", "seo_specialist", "content_specialist"):
            sid = resolve_staff_id_by_name(conn, str(form_data.get(key) or ""))
            if sid is not None:
                return sid
    return None


def sync_assigned_sp_from_tasks(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    *,
    overwrite: bool = False,
) -> bool:
    """Gán assigned_sp từ task nếu lifecycle chưa có SP (hoặc overwrite)."""
    if not overwrite:
        row = conn.execute(
            "SELECT assigned_sp FROM crm_service_lifecycle WHERE id = ?",
            (int(lifecycle_id),),
        ).fetchone()
        if row is None or row["assigned_sp"] is not None:
            return False
    suggested = suggest_sp_from_tasks(conn, lifecycle_id)
    if suggested is None:
        return False
    return set_assigned_sp(conn, lifecycle_id, suggested, overwrite=True)


def create_draft_lifecycle(
    conn: sqlite3.Connection,
    lead_id: int | None,
    service_slug: str,
    suggested_by: str = "ai",
    *,
    customer_id: int | None = None,
) -> int:
    """Tạo lifecycle status=draft, stage=lead. Trả về id mới."""
    ts = _ts()
    owner_id = lead_owner_staff_id(conn, lead_id)
    cur = conn.execute(
        """
        INSERT INTO crm_service_lifecycle
            (lead_id, customer_id, service_slug, stage, status,
             assigned_am, stage_entered_at, created_at, updated_at)
        VALUES (?, ?, ?, 'lead', 'draft', ?, ?, ?, ?)
        """,
        (lead_id, customer_id, service_slug, owner_id, ts, ts, ts),
    )
    lid = int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle_events
            (lifecycle_id, from_stage, to_stage, actor_type, notes, created_at)
        VALUES (?, NULL, 'lead', ?, ?, ?)
        """,
        (lid, suggested_by, f"Draft tạo bởi {suggested_by}", ts),
    )
    conn.commit()
    return lid


def activate_lifecycle(conn: sqlite3.Connection, contract_id: int) -> bool:
    """Khi contract ký: tìm draft lifecycle theo customer_id → set active, stage=onboard.
    Trả False nếu không tìm thấy."""
    contract = conn.execute(
        "SELECT customer_id, service_slug FROM crm_contracts WHERE id = ?",
        (contract_id,),
    ).fetchone()
    if contract is None:
        return False
    customer_id = contract["customer_id"]
    lc = conn.execute(
        """
        SELECT id FROM crm_service_lifecycle
        WHERE customer_id = ? AND status = 'draft'
        ORDER BY updated_at DESC LIMIT 1
        """,
        (customer_id,),
    ).fetchone()
    if lc is None:
        return False
    lid = lc["id"]
    ts = _ts()
    old = conn.execute(
        "SELECT stage FROM crm_service_lifecycle WHERE id = ?", (lid,)
    ).fetchone()
    from_stage = old["stage"] if old else "lead"
    from crm_svc_tasks import complete_all_stage_tasks

    for pre_stage in ("lead", "consult", "proposal"):
        if stage_index(pre_stage) < stage_index("onboard"):
            complete_all_stage_tasks(conn, lid, pre_stage, done_by=None)
    conn.execute(
        """
        UPDATE crm_service_lifecycle
        SET status = 'active', stage = 'onboard', contract_id = ?,
            stage_entered_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (contract_id, ts, ts, lid),
    )
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle_events
            (lifecycle_id, from_stage, to_stage, actor_type, notes, created_at)
        VALUES (?, ?, 'onboard', 'ai', 'Contract ký — tự động activate', ?)
        """,
        (lid, from_stage, ts),
    )
    conn.commit()
    try:
        from crm_svc_lead_sync import sync_lead_from_lifecycle_stage

        sync_lead_from_lifecycle_stage(
            conn,
            lifecycle_id=lid,
            to_stage="onboard",
            ts=ts,
            actor="system",
        )
        conn.commit()
    except Exception as exc:
        logger.warning("activate_lifecycle sync lead lỗi lifecycle_id=%s: %s", lid, exc)
    return True


def advance_stage(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    to_stage: str,
    actor_id: int | None = None,
    actor_type: str = "human",
    notes: str = "",
    *,
    skip_validation: bool = False,
    sync_lead: bool = True,
) -> None:
    """Chuyển stage, ghi event vào lifecycle_events."""
    if to_stage not in VALID_STAGES:
        raise StageAdvanceError(f"Stage không hợp lệ: {to_stage}")
    ts = _ts()
    old = conn.execute(
        "SELECT stage FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
    ).fetchone()
    from_stage = str(old["stage"] if old else "lead")
    if not skip_validation:
        validate_stage_advance(conn, lifecycle_id, from_stage, to_stage)
    conn.execute(
        """
        UPDATE crm_service_lifecycle
        SET stage = ?, stage_entered_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (to_stage, ts, ts, lifecycle_id),
    )
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle_events
            (lifecycle_id, from_stage, to_stage, actor_id, actor_type, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (lifecycle_id, from_stage, to_stage, actor_id, actor_type, notes, ts),
    )
    conn.commit()
    if to_stage == "consult":
        try:
            from crm_svc_consult_bridge import prefill_consult_task

            prefill_consult_task(conn, lifecycle_id)
            conn.commit()
        except Exception as exc:
            logger.warning(
                "prefill_consult_task lỗi lifecycle_id=%s: %s", lifecycle_id, exc
            )
    if sync_lead and actor_type != "sync":
        try:
            from crm_svc_lead_sync import sync_lead_from_lifecycle_stage

            sync_lead_from_lifecycle_stage(
                conn,
                lifecycle_id=lifecycle_id,
                to_stage=to_stage,
                ts=ts,
                actor=str(actor_id or actor_type or "system"),
            )
            conn.commit()
        except Exception as exc:
            logger.warning(
                "advance_stage sync lead lỗi lifecycle_id=%s: %s", lifecycle_id, exc
            )


def get_by_lead(conn: sqlite3.Connection, lead_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM crm_service_lifecycle WHERE lead_id = ? ORDER BY id DESC LIMIT 1",
        (lead_id,),
    ).fetchone()
    return dict(row) if row else None


def get_by_contract(conn: sqlite3.Connection, contract_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM crm_service_lifecycle WHERE contract_id = ? ORDER BY id DESC LIMIT 1",
        (contract_id,),
    ).fetchone()
    return dict(row) if row else None


def get_stage_context(
    conn: sqlite3.Connection, customer_id: int
) -> dict[str, Any] | None:
    """Trả về {service_slug, stage, stage_days} cho crm_care dùng làm AI context."""
    row = conn.execute(
        """
        SELECT service_slug, stage, stage_entered_at
        FROM crm_service_lifecycle
        WHERE customer_id = ? AND status = 'active'
        ORDER BY updated_at DESC LIMIT 1
        """,
        (customer_id,),
    ).fetchone()
    if row is None:
        return None
    stage_days = 0
    try:
        entered = datetime.strptime(row["stage_entered_at"], "%Y-%m-%d %H:%M:%S")
        stage_days = (datetime.utcnow() - entered).days
    except Exception:
        pass
    return {
        "service_slug": row["service_slug"],
        "stage": row["stage"],
        "stage_days": stage_days,
    }


def list_active(
    conn: sqlite3.Connection,
    service_slug: str | None = None,
    am_id: int | None = None,
    include_draft: bool = False,
) -> list[dict[str, Any]]:
    """Dashboard kanban: trả về lifecycles active (và draft nếu include_draft=True)."""
    conditions = []
    params: list[Any] = []
    if include_draft:
        conditions.append("status IN ('active', 'draft')")
    else:
        conditions.append("status = 'active'")
    if service_slug:
        conditions.append("service_slug = ?")
        params.append(service_slug)
    if am_id:
        conditions.append("assigned_am = ?")
        params.append(am_id)
    where = " AND ".join(conditions)
    rows = conn.execute(
        f"SELECT * FROM crm_service_lifecycle WHERE {where} ORDER BY updated_at DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


# ── AI helpers (internal) ──────────────────────────────────────────────────

_HAIKU = "claude-haiku-4-5-20251001"

_SLUG_LIST = "\n".join(f"- {s}" for s in sorted(VALID_SLUGS))

_SUGGEST_SYSTEM = f"""Bạn là trợ lý phân loại dịch vụ marketing cho agency PTT.
Dựa vào thông tin lead, chọn service_slug phù hợp nhất trong danh sách sau:
{_SLUG_LIST}

Trả về JSON: {{"service_slug": "...", "confidence": 0.0-1.0, "reason": "1 câu"}}
Nếu không xác định được, trả về service_slug rỗng: {{"service_slug": "", "confidence": 0.0, "reason": "..."}}"""


import threading


# KPI targets tham chiếu từ service specs (ngưỡng tối thiểu)
_KPI_TARGETS: dict[str, dict] = {
    "dich-vu-seo-tong-the": {"organic_traffic_growth_pct": 20, "keywords_top10_pct": 50},
    "dich-vu-seo-local": {"gbp_views_growth_pct": 30, "local_pack_pct": 50},
    "quang-cao-facebook": {"ctr_min": 1.5, "cpl_on_target_pct": 70},
    "quang-cao-google": {"impression_share_min": 60, "cpa_on_target_pct": 70},
}

_KPI_ALERT_SYSTEM = """Bạn là trợ lý phân tích KPI cho agency marketing PTT.
Dựa vào số liệu thực tế so với mục tiêu, đánh giá mức độ cảnh báo.
Trả về JSON: {"severity": "ok|warn|critical", "message": "1-2 câu cho AM", "suggested_action": "hành động gợi ý"}
- ok: đạt ≥ 90% mục tiêu
- warn: đạt 70–89%
- critical: dưới 70%"""


def check_kpi_alert_async(
    lifecycle_id: int,
    db_path: str,
    kpi_actual: dict | None = None,
) -> threading.Thread:
    """Chạy KPI alert trong background thread. Ghi severity vào lifecycle.notes."""

    def _run() -> None:
        import json
        import os
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            lc = conn.execute(
                "SELECT * FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
            ).fetchone()
            if lc is None:
                return
            slug = lc["service_slug"]
            targets = _KPI_TARGETS.get(slug, {})
            if not targets or not kpi_actual:
                return
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            prompt = (
                f"Dịch vụ: {slug}\n"
                f"Mục tiêu: {json.dumps(targets, ensure_ascii=False)}\n"
                f"Thực tế: {json.dumps(kpi_actual, ensure_ascii=False)}"
            )
            response = client.messages.create(
                model=_HAIKU,
                max_tokens=300,
                system=_KPI_ALERT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            alert = json.loads(raw)
            severity = str(alert.get("severity", "ok"))
            message = str(alert.get("message", ""))
            ts = _ts()
            conn.execute(
                """
                UPDATE crm_service_lifecycle
                SET notes = notes || ?, updated_at = ?
                WHERE id = ?
                """,
                (f"\n[KPI {severity.upper()} {ts[:10]}] {message}", ts, lifecycle_id),
            )
            conn.commit()
            logger.info("KPI alert lifecycle_id=%s severity=%s", lifecycle_id, severity)
        except Exception as exc:
            logger.warning("check_kpi_alert_async lỗi lifecycle_id=%s: %s", lifecycle_id, exc)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    t = threading.Thread(target=_run, daemon=True, name=f"kpi-alert-{lifecycle_id}")
    t.start()
    return t


def _suggest_service_slug(
    *,
    niche: str = "",
    pain_points: str = "",
    lead_message: str = "",
) -> str:
    """Gọi Claude Haiku để gợi ý service_slug. Trả về slug hợp lệ hoặc '' nếu fail."""
    import json
    import os
    try:
        import anthropic
    except ImportError:
        return ""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = f"Ngách: {niche}\nVấn đề: {pain_points}\nNhắn: {lead_message[:500]}"
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=200,
            system=_SUGGEST_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        slug = str(data.get("service_slug", "")).strip()
        return slug if slug in VALID_SLUGS else ""
    except Exception as exc:
        logger.warning("_suggest_service_slug lỗi: %s", exc)
        return ""
