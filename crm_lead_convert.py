"""Chuyển Lead → Khách hàng + Case CSKH."""
from __future__ import annotations

import sqlite3
from typing import Any

from crm_lead_store import (
    LEAD_SOURCE_LABELS,
    LEAD_STATUS_LABELS,
    fetch_lead_activities,
    fetch_lead_by_id,
    log_lead_activity,
    normalize_phone,
    normalize_source,
    normalize_status,
)
from crm_sales_pipeline import (
    legacy_status_for_stage,
    normalize_pipeline_stage,
    on_case_created,
    pipeline_stage_label,
)

# Lead status → pipeline stage
LEAD_STATUS_TO_PIPELINE: dict[str, str] = {
    "new": "moi",
    "pending_cleanup": "moi",
    "contacted": "dang_lien_he",
    "qualified": "mql",
    "hot": "mql",
    "warm": "dang_lien_he",
    "cold": "moi",
    "proposal_sent": "bao_gia",
    "negotiation": "bao_gia",
    "won": "chot",
    "lost": "mat",
    "nurturing": "dang_lien_he",
}


def _find_customer(conn: sqlite3.Connection, phone: str, email: str) -> int | None:
    ph = normalize_phone(phone)
    if len(ph) >= 8:
        hit = conn.execute(
            """
            SELECT id FROM crm_customers
            WHERE REPLACE(REPLACE(REPLACE(COALESCE(phone,''),' ',''),'-',''),'.','') = ?
              AND COALESCE(is_placeholder, 0) = 0
            ORDER BY id ASC LIMIT 1
            """,
            (ph,),
        ).fetchone()
        if hit:
            return int(hit["id"])
    em = str(email or "").strip().lower()
    if em and "@" in em:
        hit = conn.execute(
            """
            SELECT id FROM crm_customers
            WHERE lower(trim(email)) = ? AND COALESCE(is_placeholder, 0) = 0
            ORDER BY id ASC LIMIT 1
            """,
            (em,),
        ).fetchone()
        if hit:
            return int(hit["id"])
    return None


def convert_lead_to_crm(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    case_title: str | None = None,
    actor: str = "",
    ts: str,
) -> dict[str, Any]:
    """
    Tạo hoặc liên kết crm_customers + crm_cases từ lead.
    Trả dict: customer_id, case_id, pipeline_stage, created_customer.
    """
    row = fetch_lead_by_id(conn, lead_id)
    if row is None:
        raise ValueError("Không tìm thấy lead.")
    ld = dict(row)
    if ld.get("converted_case_id"):
        return {
            "customer_id": int(ld["converted_customer_id"]) if ld.get("converted_customer_id") else None,
            "case_id": int(ld["converted_case_id"]),
            "already_converted": True,
        }

    name = str(ld.get("full_name") or "").strip()
    phone = str(ld.get("phone") or "").strip()
    email = str(ld.get("email") or "").strip()
    if not name:
        raise ValueError("Lead thiếu họ tên — không thể chuyển đổi.")

    ph_norm = normalize_phone(phone)
    cust_id = _find_customer(conn, phone, email)
    created_customer = False
    short_date = ts[:10] if len(ts) >= 10 else ts

    if cust_id is None:
        cur = conn.execute(
            """
            INSERT INTO crm_customers (name, phone, email, address, company, created_at)
            VALUES (?, ?, ?, '', '', ?)
            """,
            (name[:240], phone[:80], email[:240], short_date),
        )
        cust_id = int(cur.lastrowid)
        created_customer = True
        src = normalize_source(ld.get("source"))
        try:
            conn.execute(
                "UPDATE crm_customers SET lead_source = ?, lead_source_note = ? WHERE id = ?",
                (src, f"Chuyển từ Lead #{lead_id}", cust_id),
            )
        except sqlite3.OperationalError:
            pass
    else:
        ex = conn.execute("SELECT * FROM crm_customers WHERE id = ?", (cust_id,)).fetchone()
        if ex:
            exd = dict(ex)
            conn.execute(
                """
                UPDATE crm_customers
                SET name = COALESCE(NULLIF(?, ''), name),
                    phone = COALESCE(NULLIF(?, ''), phone),
                    email = COALESCE(NULLIF(?, ''), email)
                WHERE id = ?
                """,
                (name[:240], phone[:80], email[:240], cust_id),
            )

    st = normalize_status(ld.get("status"))
    pipeline = normalize_pipeline_stage(LEAD_STATUS_TO_PIPELINE.get(st, "moi"))
    title = (case_title or "").strip() or f"Lead #{lead_id} — {name}"
    if ld.get("product_interest"):
        title = f"{title} ({ld['product_interest']})"[:800]
    desc_parts = [
        f"Chuyển từ Lead #{lead_id}",
        f"Nguồn: {LEAD_SOURCE_LABELS.get(normalize_source(ld.get('source')), '—')}",
        f"Trạng thái lead: {LEAD_STATUS_LABELS.get(st, st)}",
        f"Điểm: {ld.get('lead_score', 0)}",
    ]
    if ld.get("need"):
        desc_parts.append(f"Nhu cầu: {ld['need']}")
    description = "\n".join(desc_parts)[:8000]

    owner_id = int(ld["owner_id"]) if ld.get("owner_id") else None
    owner_name = str(ld.get("owner_name") or "")
    channel = normalize_source(ld.get("source"))
    if channel == "website":
        channel = "web"
    elif channel in ("google_ads", "import", "api", "manual", "email"):
        channel = "khac"

    cur_case = conn.execute(
        """
        INSERT INTO crm_cases (
            customer_id, title, description, channel, priority, status,
            assigned_to, assigned_staff_id, assigned_at, created_at, updated_at,
            pipeline_stage, stage_entered_at, lead_source
        ) VALUES (?, ?, ?, ?, 'binh_thuong', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cust_id,
            title[:800],
            description,
            channel[:40],
            legacy_status_for_stage(pipeline),
            owner_name[:120],
            owner_id,
            ts if owner_id else "",
            ts,
            ts,
            pipeline,
            ts,
            normalize_source(ld.get("source"))[:120],
        ),
    )
    case_id = int(cur_case.lastrowid)

    on_case_created(
        conn,
        case_id,
        title=title,
        priority="cao" if str(ld.get("lead_level")) == "hot" else "binh_thuong",
        assigned_staff_id=owner_id,
        assigned_to=owner_name,
        lead_source=normalize_source(ld.get("source")),
        auto_assign=owner_id is None,
    )
    # Giữ pipeline theo trạng thái lead (on_case_created mặc định giai đoạn «moi»)
    conn.execute(
        """
        UPDATE crm_cases SET pipeline_stage = ?, stage_entered_at = ?, status = ?, updated_at = ?
        WHERE id = ?
        """,
        (pipeline, ts, legacy_status_for_stage(pipeline), ts, case_id),
    )

    # Copy activities → case events
    acts = fetch_lead_activities(conn, lead_id, limit=100)
    for act in reversed(list(acts)):
        ad = dict(act)
        body = f"[{ad.get('activity_type', 'note')}] {ad.get('content', '')}"
        if ad.get("result"):
            body += f"\nKết quả: {ad['result']}"
        if ad.get("next_action"):
            body += f"\nNext: {ad['next_action']}"
        conn.execute(
            "INSERT INTO crm_case_events (case_id, kind, body, created_at) VALUES (?, ?, ?, ?)",
            (case_id, "ghi_chu", body[:8000], str(ad.get("created_at") or ts)),
        )

    conn.execute(
        """
        UPDATE crm_leads SET
            converted_customer_id = ?,
            converted_case_id = ?,
            status = CASE WHEN status NOT IN ('won', 'lost') THEN 'qualified' ELSE status END,
            updated_at = ?,
            updated_by = ?
        WHERE id = ?
        """,
        (cust_id, case_id, ts, actor[:120], int(lead_id)),
    )

    log_lead_activity(
        conn,
        lead_id=lead_id,
        activity_type="system",
        content=(
            f"Đã chuyển thành KH #{cust_id} + Case #{case_id} "
            f"(pipeline: {pipeline_stage_label(pipeline)})."
        ),
        user_id=owner_id,
        created_by=actor,
        ts=ts,
    )

    return {
        "customer_id": cust_id,
        "case_id": case_id,
        "pipeline_stage": pipeline,
        "pipeline_label": pipeline_stage_label(pipeline),
        "created_customer": created_customer,
        "already_converted": False,
    }
