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
