# crm_service_lifecycle.py
"""Service Lifecycle — orchestration layer kết nối 12 dịch vụ PTTP theo chu trình thống nhất."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

VALID_STAGES: tuple[str, ...] = (
    "lead", "consult", "proposal", "onboard", "deliver", "handover", "retain"
)
VALID_STATUSES: tuple[str, ...] = ("draft", "active", "closed", "lost")

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
    conn.commit()


def create_draft_lifecycle(
    conn: sqlite3.Connection,
    lead_id: int,
    service_slug: str,
    suggested_by: str = "ai",
) -> int:
    """Tạo lifecycle status=draft, stage=lead. Trả về id mới."""
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_service_lifecycle
            (lead_id, service_slug, stage, status, stage_entered_at, created_at, updated_at)
        VALUES (?, ?, 'lead', 'draft', ?, ?, ?)
        """,
        (lead_id, service_slug, ts, ts, ts),
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
        (lid, old["stage"] if old else None, ts),
    )
    conn.commit()
    return True


def advance_stage(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    to_stage: str,
    actor_id: int | None = None,
    actor_type: str = "human",
    notes: str = "",
) -> None:
    """Chuyển stage, ghi event vào lifecycle_events."""
    if to_stage not in VALID_STAGES:
        raise ValueError(f"Stage không hợp lệ: {to_stage}")
    ts = _ts()
    old = conn.execute(
        "SELECT stage FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
    ).fetchone()
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
        (lifecycle_id, old["stage"] if old else None, to_stage, actor_id, actor_type, notes, ts),
    )
    conn.commit()


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
