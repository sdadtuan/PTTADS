"""Hợp đồng draft từ Lead pre-sales + kích hoạt lifecycle khi ký HĐ."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class PresalesContractError(ValueError):
    """Lỗi tạo / ký hợp đồng pre-sales."""


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_contract_schema(conn: sqlite3.Connection) -> None:
    """Migration: lead_id trên HĐ, placeholder trên KH."""
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "crm_contracts" in tables:
        ct_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(crm_contracts)").fetchall()
        }
        if "lead_id" not in ct_cols:
            conn.execute(
                "ALTER TABLE crm_contracts ADD COLUMN lead_id INTEGER REFERENCES crm_leads(id)"
            )
    if "crm_customers" in tables:
        cu_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(crm_customers)").fetchall()
        }
        if "is_placeholder" not in cu_cols:
            conn.execute(
                "ALTER TABLE crm_customers ADD COLUMN is_placeholder INTEGER NOT NULL DEFAULT 0"
            )
        if "placeholder_lead_id" not in cu_cols:
            conn.execute(
                "ALTER TABLE crm_customers ADD COLUMN placeholder_lead_id INTEGER "
                "REFERENCES crm_leads(id)"
            )
    if "crm_contracts" in tables:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_crm_contracts_lead ON crm_contracts(lead_id)"
        )
    from crm_svc_finance import migrate_contract_billing_type

    migrate_contract_billing_type(conn)
    conn.commit()


def _fetch_lead_for_contract(
    conn: sqlite3.Connection, lead_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, full_name, phone, email, owner_id, status
        FROM crm_leads WHERE id = ?
        """,
        (int(lead_id),),
    ).fetchone()
    return dict(row) if row else None


def placeholder_customer_name(lead_id: int, full_name: str) -> str:
    fn = str(full_name or "").strip() or "Lead"
    return f"[Lead #{int(lead_id)}] Chưa ký — {fn}"[:240]


def get_placeholder_for_lead(
    conn: sqlite3.Connection, lead_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM crm_customers
        WHERE placeholder_lead_id = ? AND COALESCE(is_placeholder, 0) = 1
        ORDER BY id DESC LIMIT 1
        """,
        (int(lead_id),),
    ).fetchone()
    return dict(row) if row else None


def create_placeholder_customer(
    conn: sqlite3.Connection, lead_id: int, *, ts: str | None = None
) -> int:
    """Tạo hoặc trả về KH placeholder cho lead (không ghi SĐT/email — tránh dedup)."""
    existing = get_placeholder_for_lead(conn, lead_id)
    if existing:
        return int(existing["id"])

    lead = _fetch_lead_for_contract(conn, int(lead_id))
    if lead is None:
        raise PresalesContractError("Không tìm thấy lead")
    ts_use = ts or _ts()
    short_date = ts_use[:10]
    name = placeholder_customer_name(int(lead_id), str(lead.get("full_name") or ""))
    cur = conn.execute(
        """
        INSERT INTO crm_customers (
            name, phone, email, address, company, created_at,
            is_placeholder, placeholder_lead_id
        ) VALUES (?, '', '', '', '', ?, 1, ?)
        """,
        (name, short_date, int(lead_id)),
    )
    return int(cur.lastrowid)


def get_draft_contract_for_lead(
    conn: sqlite3.Connection, lead_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM crm_contracts
        WHERE lead_id = ? AND status = 'draft'
        ORDER BY id DESC LIMIT 1
        """,
        (int(lead_id),),
    ).fetchone()
    return dict(row) if row else None


def get_contract_summary_for_lead(
    conn: sqlite3.Connection, lead_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, title, status, amount_vnd, customer_id, signed_on, created_at
        FROM crm_contracts
        WHERE lead_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (int(lead_id),),
    ).fetchone()
    return dict(row) if row else None


def create_draft_contract_from_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    title: str | None = None,
    amount_vnd: int = 0,
    notes: str = "",
    actor: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    """Tạo HĐ draft gắn lead + KH placeholder. Idempotent nếu đã có draft."""
    from crm_lead_presales import get_by_lead
    from crm_svc_tasks import SERVICE_LABELS

    ts_use = ts or _ts()
    lead = _fetch_lead_for_contract(conn, int(lead_id))
    if lead is None:
        raise PresalesContractError("Không tìm thấy lead")

    ps = get_by_lead(conn, int(lead_id))
    if ps is None:
        raise PresalesContractError("Chưa có pre-sales — chọn dịch vụ trước")
    if str(ps.get("status") or "") != "active":
        raise PresalesContractError("Pre-sales không còn active")

    existing = get_draft_contract_for_lead(conn, int(lead_id))
    if existing:
        return existing

    slug = str(ps.get("service_slug") or "").strip()
    if not slug:
        raise PresalesContractError("Pre-sales thiếu service_slug")

    from crm_svc_finance import infer_billing_type_from_service_slug

    billing_type = infer_billing_type_from_service_slug(slug)

    placeholder_id = create_placeholder_customer(conn, int(lead_id), ts=ts_use)
    svc_label = SERVICE_LABELS.get(slug, slug)
    lead_name = str(lead.get("full_name") or "").strip() or f"#{lead_id}"
    contract_title = (title or "").strip() or (
        f"{svc_label} — Lead #{lead_id} {lead_name}"
    )[:500]
    amount_vnd = max(0, min(int(amount_vnd or 0), 9_999_999_999_999))
    note_line = notes.strip()
    if actor and note_line:
        note_line = f"{note_line}\nTạo bởi {actor}"[:8000]
    elif actor:
        note_line = f"Tạo từ pre-sales bởi {actor}"[:8000]

    cur = conn.execute(
        """
        INSERT INTO crm_contracts (
            customer_id, lead_id, case_id, campaign_id, reference_code, title,
            status, signed_on, starts_on, ends_on, amount_vnd,
            renewal_reminder_days, notes, service_slug, billing_type, created_at, updated_at
        ) VALUES (?, ?, NULL, NULL, '', ?, 'draft', '', '', '', ?, 30, ?, ?, ?, ?, ?)
        """,
        (
            placeholder_id,
            int(lead_id),
            contract_title,
            amount_vnd,
            note_line,
            slug,
            billing_type,
            ts_use[:10],
            ts_use,
        ),
    )
    contract_id = int(cur.lastrowid)
    row = conn.execute(
        "SELECT * FROM crm_contracts WHERE id = ?", (contract_id,)
    ).fetchone()
    if row is None:
        raise PresalesContractError("Không tạo được hợp đồng")
    conn.commit()
    logger.info(
        "create_draft_contract_from_lead lead=%s contract=%s placeholder=%s",
        lead_id,
        contract_id,
        placeholder_id,
    )
    return dict(row)


def delete_placeholder_customer_if_orphan(
    conn: sqlite3.Connection, customer_id: int
) -> bool:
    """Xóa KH placeholder nếu không còn HĐ / case gắn."""
    row = conn.execute(
        "SELECT is_placeholder FROM crm_customers WHERE id = ?",
        (int(customer_id),),
    ).fetchone()
    if row is None or not int(row["is_placeholder"] or 0):
        return False
    n_ct = conn.execute(
        "SELECT COUNT(*) AS n FROM crm_contracts WHERE customer_id = ?",
        (int(customer_id),),
    ).fetchone()
    if n_ct and int(n_ct["n"] or 0) > 0:
        return False
    n_cs = conn.execute(
        "SELECT COUNT(*) AS n FROM crm_cases WHERE customer_id = ?",
        (int(customer_id),),
    ).fetchone()
    if n_cs and int(n_cs["n"] or 0) > 0:
        return False
    conn.execute("DELETE FROM crm_customers WHERE id = ?", (int(customer_id),))
    return True


def on_presales_contract_signed(
    conn: sqlite3.Connection,
    contract_id: int,
    *,
    actor: str = "system",
    ts: str | None = None,
) -> dict[str, Any]:
    """
    Khi HĐ active: convert lead → KH thật, cập nhật HĐ, promote pre-sales → lifecycle,
    xóa KH placeholder.
    """
    from crm_lead_convert import convert_lead_to_crm
    from crm_lead_presales import (
        PresalesPromoteError,
        get_by_lead,
        promote_presales_to_lifecycle,
    )

    ts_use = ts or _ts()
    contract = conn.execute(
        "SELECT * FROM crm_contracts WHERE id = ?", (int(contract_id),)
    ).fetchone()
    if contract is None:
        raise PresalesContractError("Không tìm thấy hợp đồng")
    ct = dict(contract)
    lead_id = ct.get("lead_id")
    if not lead_id:
        raise PresalesContractError("Hợp đồng không gắn lead_id")

    placeholder_id = int(ct["customer_id"])
    ps = get_by_lead(conn, int(lead_id))
    if ps is None:
        raise PresalesContractError("Lead chưa có pre-sales")

    conv = convert_lead_to_crm(
        conn,
        int(lead_id),
        actor=actor,
        ts=ts_use,
    )
    real_cid = conv.get("customer_id")
    if not real_cid:
        raise PresalesContractError("Không tạo được khách hàng từ lead")
    real_cid = int(real_cid)
    real_case = conv.get("case_id")

    conn.execute(
        """
        UPDATE crm_contracts
        SET customer_id = ?, case_id = COALESCE(?, case_id), updated_at = ?
        WHERE id = ?
        """,
        (real_cid, real_case, ts_use, int(contract_id)),
    )

    try:
        lifecycle_id = promote_presales_to_lifecycle(
            conn,
            int(ps["id"]),
            customer_id=real_cid,
            contract_id=int(contract_id),
            actor=actor,
        )
    except PresalesPromoteError as exc:
        raise PresalesContractError(str(exc)) from exc

    conn.execute(
        """
        UPDATE crm_leads
        SET status = 'won', updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (ts_use, str(actor or "")[:120], int(lead_id)),
    )

    if placeholder_id != real_cid:
        delete_placeholder_customer_if_orphan(conn, placeholder_id)

    conn.commit()
    return {
        "contract_id": int(contract_id),
        "lead_id": int(lead_id),
        "customer_id": real_cid,
        "case_id": real_case,
        "lifecycle_id": lifecycle_id,
        "convert": conv,
    }
