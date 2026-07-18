"""Đồng bộ Service Delivery (7 stage) ↔ pipeline chăm sóc lead (8 bước)."""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from crm_lead_care_pipeline import (
    CARE_STAGE_KEYS,
    care_stage_index,
    parse_stages_done_json,
    serialize_stages_done,
)
from crm_service_lifecycle import VALID_STAGES, advance_stage, get_by_lead, stage_index

logger = logging.getLogger(__name__)

# Giai đoạn Service Delivery → bước chăm sóc lead tương ứng
SVC_TO_CARE_STAGE: dict[str, str] = {
    "lead": "first_contact",
    "consult": "qualify",
    "proposal": "advise",
    "onboard": "closing",
    "deliver": "post_sale",
    "handover": "post_sale",
    "retain": "post_sale",
}

# Bước chăm sóc lead → giai đoạn Service Delivery (mốc tối thiểu)
CARE_TO_SVC_STAGE: dict[str, str] = {
    "intake": "lead",
    "first_contact": "lead",
    "qualify": "consult",
    "advise": "proposal",
    "nurture": "proposal",
    "negotiate": "proposal",
    "closing": "onboard",
    "post_sale": "deliver",
}


def sync_lead_from_lifecycle_stage(
    conn: sqlite3.Connection,
    *,
    lifecycle_id: int,
    to_stage: str,
    ts: str,
    actor: str,
) -> None:
    """Lifecycle chuyển stage → cập nhật pipeline chăm sóc lead liên kết."""
    row = conn.execute(
        "SELECT lead_id FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
    ).fetchone()
    if row is None or not row["lead_id"]:
        return
    lead_id = int(row["lead_id"])
    care_target = SVC_TO_CARE_STAGE.get(to_stage)
    if not care_target or care_target not in CARE_STAGE_KEYS:
        return

    lead = conn.execute(
        """
        SELECT id, status, care_stage_current, care_stages_done_json
        FROM crm_leads WHERE id = ?
        """,
        (lead_id,),
    ).fetchone()
    if lead is None:
        return

    target_idx = care_stage_index(care_target)
    done = parse_stages_done_json(str(lead["care_stages_done_json"] or ""))
    for i in range(target_idx):
        key = CARE_STAGE_KEYS[i]
        if key not in done:
            done[key] = ts

    conn.execute(
        """
        UPDATE crm_leads
        SET care_stage_current = ?,
            care_stages_done_json = ?,
            status = ?,
            status_entered_at = ?,
            updated_at = ?,
            updated_by = ?
        WHERE id = ?
        """,
        (
            care_target,
            serialize_stages_done(done),
            care_target,
            ts,
            ts,
            actor[:120],
            lead_id,
        ),
    )


def sync_lifecycle_from_lead_care_stage(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    care_stage_key: str,
    ts: str,
    actor: str,
) -> None:
    """Lead hoàn thành bước chăm sóc → đẩy lifecycle liên kết (nếu đang tụt hậu)."""
    target_svc = CARE_TO_SVC_STAGE.get(str(care_stage_key or "").strip())
    if not target_svc:
        return
    lc = get_by_lead(conn, lead_id)
    if lc is None:
        return

    lifecycle_id = int(lc["id"])
    current = str(lc["stage"] or "lead")
    if current not in VALID_STAGES:
        current = "lead"

    target_idx = stage_index(target_svc)
    current_idx = stage_index(current)
    if target_idx <= current_idx:
        return

    from crm_svc_tasks import complete_all_stage_tasks

    while stage_index(current) < target_idx:
        complete_all_stage_tasks(conn, lifecycle_id, current, done_by=None)
        next_stage = VALID_STAGES[stage_index(current) + 1]
        advance_stage(
            conn,
            lifecycle_id,
            next_stage,
            actor_type="sync",
            notes=f"Đồng bộ từ lead chăm sóc → {care_stage_key}",
            skip_validation=True,
            sync_lead=False,
        )
        current = next_stage
