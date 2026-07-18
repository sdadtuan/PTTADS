"""Pipeline chăm sóc lead — Product Model v1: B2 Liên hệ lần đầu → pre-sales."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

CONTACT_OK_CARE_STATUS = "da_lien_he_thanh_cong"

# Bước chăm sóc duy nhất trước pre-sales (B2).
CARE_PIPELINE_STAGES: tuple[dict[str, Any], ...] = (
    {
        "key": "first_contact",
        "label": "Liên hệ lần đầu",
        "hint": (
            "Liên hệ trong 48h — xác nhận nhu cầu dịch vụ marketing. "
            "Cập nhật trạng thái + báo cáo; 「Liên hệ OK」 (da_lien_he_thanh_cong) "
            "rồi hoàn thành B2 để mở pre-sales."
        ),
        "statuses": ("new", "pending_cleanup", "hot", "warm", "cold", "contacted"),
        "status_on_complete": "first_contact",
    },
)

CARE_STAGE_KEYS: tuple[str, ...] = tuple(s["key"] for s in CARE_PIPELINE_STAGES)

# Legacy keys (B1–B8 pilot / BĐS) — chỉ dùng migrate gate, không hiển thị pipeline.
LEGACY_CARE_STAGE_KEYS: frozenset[str] = frozenset(
    {
        "intake",
        "qualify",
        "advise",
        "nurture",
        "negotiate",
        "closing",
        "post_sale",
    }
)
LEGACY_PRESALES_CARE_STAGES: tuple[str, ...] = ("intake", "first_contact", "qualify")

PRESALES_REQUIRED_CARE_STAGES: tuple[str, ...] = ("first_contact",)

CARE_PIPELINE_STAGES_PUBLIC: list[dict[str, str]] = [
    {"key": s["key"], "label": s["label"], "hint": s["hint"]} for s in CARE_PIPELINE_STAGES
]

CARE_STAGE_STATUS_LABELS: dict[str, str] = {
    str(s["key"]): str(s["label"]) for s in CARE_PIPELINE_STAGES
}

# Trạng thái CRM cũ → bước pipeline (migrate / normalize)
LEGACY_STATUS_TO_CARE_STAGE: dict[str, str] = {
    "new": "first_contact",
    "pending_cleanup": "first_contact",
    "hot": "first_contact",
    "warm": "first_contact",
    "cold": "first_contact",
    "contacted": "first_contact",
    "qualified": "first_contact",
    "proposal_sent": "first_contact",
    "nurturing": "first_contact",
    "negotiation": "first_contact",
    "won": "first_contact",
    "intake": "first_contact",
    "qualify": "first_contact",
    "advise": "first_contact",
    "nurture": "first_contact",
    "negotiate": "first_contact",
    "closing": "first_contact",
    "post_sale": "first_contact",
}

_STATUS_TO_STAGE: dict[str, str] = dict(LEGACY_STATUS_TO_CARE_STAGE)
for _st in CARE_PIPELINE_STAGES:
    _STATUS_TO_STAGE[str(_st["key"])] = _st["key"]
    for _code in _st.get("statuses") or ():
        _STATUS_TO_STAGE[str(_code)] = _st["key"]
_STATUS_TO_STAGE["won"] = "first_contact"
_STATUS_TO_STAGE["lost"] = "first_contact"


def build_care_status_transitions() -> dict[str, frozenset[str]]:
    """Chuyển trạng thái pipeline B2 (+ lost / pending_cleanup)."""
    trans: dict[str, set[str]] = {k: set() for k in CARE_STAGE_KEYS}
    trans["first_contact"] = {"lost", "pending_cleanup"}
    trans["pending_cleanup"] = {"first_contact", "lost"}
    trans["lost"] = {"first_contact"}
    return {k: frozenset(v) for k, v in trans.items()}


CARE_STATUS_TRANSITIONS: dict[str, frozenset[str]] = build_care_status_transitions()


def legacy_status_to_care_stage(status: str) -> str:
    s = str(status or "").strip().lower().replace(" ", "_")
    if s in CARE_STAGE_KEYS:
        return s
    return LEGACY_STATUS_TO_CARE_STAGE.get(s, "first_contact")


def sync_lead_status_to_care_stage(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    stage_key: str | None = None,
    crm_status: str | None = None,
    created_by: str,
    ts: str,
    note: str = "",
) -> bool:
    """Đồng bộ cột status CRM với bước pipeline — hiển thị trên cột trạng thái lead."""
    from crm_lead_store import fetch_lead_by_id, log_status_change, normalize_status

    lead = fetch_lead_by_id(conn, lead_id)
    if lead is None:
        return False
    old_st = normalize_status(str(lead["status"]))
    if old_st == "lost":
        return False
    status_override = str(crm_status or "").strip()
    if status_override:
        new_st = normalize_status(status_override)
    else:
        target = str(stage_key or lead["care_stage_current"] or "").strip()
        if target not in CARE_STAGE_KEYS:
            target = care_stage_for_status(str(lead["status"]))
        new_st = normalize_status(target)
    if old_st == new_st:
        return False
    from crm_lead_rules import is_status_transition_allowed

    if not is_status_transition_allowed(old_st, new_st):
        return False
    stage_lbl = care_stage_label(new_st)
    log_status_change(
        conn,
        lead_id=lead_id,
        old_status=old_st,
        new_status=new_st,
        changed_by=created_by,
        note=note or f"Bước chăm sóc: {stage_lbl}",
        ts=ts,
    )
    conn.execute(
        """
        UPDATE crm_leads
        SET status = ?, status_entered_at = ?, updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (new_st, ts, ts, created_by[:120], int(lead_id)),
    )
    return True


def care_stage_index(stage_key: str) -> int:
    key = str(stage_key or "").strip()
    try:
        return CARE_STAGE_KEYS.index(key)
    except ValueError:
        return 0


def care_stage_label(stage_key: str) -> str:
    key = str(stage_key or "").strip()
    for st in CARE_PIPELINE_STAGES:
        if st["key"] == key:
            return str(st["label"])
    return key


def care_stage_for_status(status: str) -> str:
    st = str(status or "new").strip().lower()
    return _STATUS_TO_STAGE.get(st, "first_contact")


def care_next_stage_key(stage_key: str) -> str | None:
    idx = care_stage_index(stage_key)
    if idx < 0 or idx >= len(CARE_STAGE_KEYS) - 1:
        return None
    return CARE_STAGE_KEYS[idx + 1]


def parse_stages_done_json(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in data.items():
        sk = str(k or "").strip()
        if sk in CARE_STAGE_KEYS or sk in LEGACY_CARE_STAGE_KEYS or sk in LEGACY_PRESALES_CARE_STAGES:
            if v:
                out[sk] = str(v)
    return out


def legacy_presales_care_complete(done: dict[str, str]) -> bool:
    """Pilot cũ: đã done B1–B3 trước khi rút gọn pipeline."""
    return all(done.get(k) for k in LEGACY_PRESALES_CARE_STAGES)


def normalize_care_stage_current(
    *,
    care_stage_current: str | None,
    care_stages_done_json: str | None,
    status: str,
) -> str:
    done = parse_stages_done_json(care_stages_done_json)
    if done.get("first_contact") or legacy_presales_care_complete(done):
        return "first_contact"
    cur = str(care_stage_current or "").strip()
    if cur in CARE_STAGE_KEYS:
        return cur
    return care_stage_for_status(status)


def serialize_stages_done(done: dict[str, str]) -> str:
    clean = {k: done[k] for k in CARE_STAGE_KEYS if k in done and done[k]}
    return json.dumps(clean, ensure_ascii=False)


def care_pipeline_state(
    *,
    status: str,
    care_stage_current: str | None,
    care_stages_done_json: str | None,
) -> dict[str, Any]:
    done = parse_stages_done_json(care_stages_done_json)
    if legacy_presales_care_complete(done) and not done.get("first_contact"):
        done = {**done, "first_contact": done.get("qualify") or done.get("first_contact") or ""}
    current = normalize_care_stage_current(
        care_stage_current=care_stage_current,
        care_stages_done_json=care_stages_done_json,
        status=status,
    )
    cur_idx = care_stage_index(current)
    stages_ui = []
    for i, st in enumerate(CARE_PIPELINE_STAGES):
        key = st["key"]
        completed_at = done.get(key) or ""
        if legacy_presales_care_complete(done) and key == "first_contact" and not completed_at:
            completed_at = done.get("qualify") or done.get("first_contact") or ""
        is_done = bool(completed_at)
        is_current = key == current and not is_done
        stages_ui.append(
            {
                "key": key,
                "label": st["label"],
                "hint": st["hint"],
                "index": i,
                "done": is_done,
                "current": is_current,
                "completed_at": completed_at,
            }
        )
    if stages_ui and stages_ui[0]["done"]:
        stages_ui[0]["current"] = False
    current_meta = CARE_PIPELINE_STAGES[cur_idx] if 0 <= cur_idx < len(CARE_PIPELINE_STAGES) else CARE_PIPELINE_STAGES[0]
    b2_done = bool(stages_ui[0]["done"]) if stages_ui else False
    return {
        "current_stage_key": current,
        "current_stage_label": current_meta["label"],
        "current_stage_hint": current_meta["hint"],
        "current_stage_index": cur_idx,
        "stages_done": {k: done[k] for k in CARE_STAGE_KEYS if done.get(k)},
        "stages": stages_ui,
        "all_complete": b2_done,
    }


def ensure_lead_care_pipeline_schema(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_leads)").fetchall()}
    if "care_stage_current" not in cols:
        conn.execute(
            "ALTER TABLE crm_leads ADD COLUMN care_stage_current TEXT NOT NULL DEFAULT 'intake'"
        )
    if "care_stages_done_json" not in cols:
        conn.execute(
            "ALTER TABLE crm_leads ADD COLUMN care_stages_done_json TEXT NOT NULL DEFAULT '{}'"
        )
    migrate_lead_care_pipeline_bootstrap(conn)
    migrate_lead_care_pipeline_b2_only(conn)


def migrate_lead_care_pipeline_b2_only(conn: sqlite3.Connection) -> None:
    """Chuẩn hóa lead cũ: care_stage_current legacy → first_contact (B2-only)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'lead_care_pipeline_b2_only_v1'"
    ).fetchone()
    if row and str(row["value"]) == "1":
        return
    legacy_keys = tuple(LEGACY_CARE_STAGE_KEYS | frozenset({"intake", "qualify"}))
    placeholders = ",".join("?" for _ in legacy_keys)
    conn.execute(
        f"""
        UPDATE crm_leads
        SET care_stage_current = 'first_contact'
        WHERE trim(care_stage_current) IN ({placeholders})
          AND trim(COALESCE(json_extract(care_stages_done_json, '$.first_contact'), '')) = ''
          AND NOT (
            trim(COALESCE(json_extract(care_stages_done_json, '$.intake'), '')) != ''
            AND trim(COALESCE(json_extract(care_stages_done_json, '$.first_contact'), '')) != ''
            AND trim(COALESCE(json_extract(care_stages_done_json, '$.qualify'), '')) != ''
          )
        """,
        legacy_keys,
    )
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('lead_care_pipeline_b2_only_v1', '1')"
    )


def migrate_lead_care_pipeline_bootstrap(conn: sqlite3.Connection) -> None:
    """Lead cũ chưa có tiến độ — suy ra từ status một lần."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'lead_care_pipeline_bootstrap_v1'"
    ).fetchone()
    if row and str(row["value"]) == "1":
        return
    ts_row = conn.execute(
        "SELECT updated_at FROM crm_leads ORDER BY id DESC LIMIT 1"
    ).fetchone()
    fallback_ts = str(ts_row["updated_at"]) if ts_row else ""
    leads = conn.execute(
        """
        SELECT id, status, care_stage_current, care_stages_done_json, updated_at
        FROM crm_leads
        WHERE care_stages_done_json IS NULL
           OR trim(care_stages_done_json) IN ('', '{}')
        """
    ).fetchall()
    for lead in leads:
        st = str(lead["status"] or "new")
        current = care_stage_for_status(st)
        idx = care_stage_index(current)
        done: dict[str, str] = parse_stages_done_json(lead["care_stages_done_json"])
        ts_use = str(lead["updated_at"] or fallback_ts)
        for i in range(idx):
            k = CARE_STAGE_KEYS[i]
            if k not in done:
                done[k] = ts_use
        conn.execute(
            """
            UPDATE crm_leads
            SET care_stage_current = ?, care_stages_done_json = ?
            WHERE id = ?
            """,
            (current, serialize_stages_done(done), int(lead["id"])),
        )
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('lead_care_pipeline_bootstrap_v1', '1')"
    )
    migrate_lead_status_to_care_stages(conn)


def migrate_lead_status_to_care_stages(conn: sqlite3.Connection) -> None:
    """Đồng bộ cột status = bước pipeline hiện tại (một lần + lead mới sau migrate)."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'lead_status_care_stage_sync_v1'"
    ).fetchone()
    if row and str(row["value"]) == "1":
        return
    rows = conn.execute(
        "SELECT id, status, care_stage_current FROM crm_leads"
    ).fetchall()
    for lead in rows:
        st = str(lead["status"] or "").strip().lower()
        if st in ("lost", "pending_cleanup"):
            continue
        current = str(lead["care_stage_current"] or "").strip()
        if current not in CARE_STAGE_KEYS:
            current = care_stage_for_status(st)
        if current not in CARE_STAGE_KEYS:
            continue
        conn.execute(
            "UPDATE crm_leads SET status = ? WHERE id = ? AND status NOT IN ('lost', 'pending_cleanup')",
            (current, int(lead["id"])),
        )
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('lead_status_care_stage_sync_v1', '1')"
    )


CARE_STAGE_MIN_COMPLETION_NOTE_LEN = 3


def presales_care_gate_state(
    *,
    care_stage_current: str | None,
    care_stages_done_json: str | None,
) -> dict[str, Any]:
    """Trạng thái hoàn thành B2 — gate vào pre-sales."""
    done = parse_stages_done_json(care_stages_done_json)
    legacy_ok = legacy_presales_care_complete(done)
    stages_ui: list[dict[str, Any]] = []
    for key in PRESALES_REQUIRED_CARE_STAGES:
        meta = next((s for s in CARE_PIPELINE_STAGES if s["key"] == key), None)
        label = str(meta["label"]) if meta else key
        completed_at = done.get(key) or ""
        if key == "first_contact" and not completed_at and legacy_ok:
            completed_at = done.get("qualify") or done.get("first_contact") or ""
        stages_ui.append(
            {
                "key": key,
                "label": label,
                "index": 2,
                "done": bool(completed_at),
                "completed_at": completed_at,
            }
        )
    complete = legacy_ok or bool(stages_ui and stages_ui[0]["done"])
    if complete:
        message = "Đã hoàn thành B2 — có thể bắt đầu pre-sales."
    else:
        message = (
            "Hoàn thành B2 trước pre-sales: báo cáo trạng thái "
            "「Liên hệ OK」 + ghi chú hoàn thành bước."
        )
    missing = [s for s in stages_ui if not s["done"]]
    return {
        "complete": complete,
        "stages": stages_ui,
        "missing_keys": [s["key"] for s in missing],
        "missing_labels": [s["label"] for s in missing],
        "message": message,
        "current_stage_key": normalize_care_stage_current(
            care_stage_current=care_stage_current,
            care_stages_done_json=care_stages_done_json,
            status="",
        ),
    }


def assert_presales_care_gate(conn: sqlite3.Connection, lead_id: int) -> None:
    row = conn.execute(
        """
        SELECT care_stage_current, care_stages_done_json
        FROM crm_leads WHERE id = ?
        """,
        (int(lead_id),),
    ).fetchone()
    if row is None:
        raise ValueError("Không tìm thấy lead.")
    gate = presales_care_gate_state(
        care_stage_current=str(row["care_stage_current"] or ""),
        care_stages_done_json=str(row["care_stages_done_json"] or ""),
    )
    if not gate["complete"]:
        raise ValueError(str(gate["message"]))


def count_stage_care_reports(
    conn: sqlite3.Connection, *, lead_id: int, stage_key: str
) -> int:
    """Số báo cáo chăm sóc (activity có care_status/contact) gắn với một bước."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM crm_lead_activities
        WHERE lead_id = ?
          AND care_stage_key = ?
          AND activity_type != 'system'
          AND (
            trim(COALESCE(care_status, '')) != ''
            OR trim(COALESCE(care_contact_type, '')) != ''
          )
        """,
        (int(lead_id), str(stage_key)),
    ).fetchone()
    return int(row["c"] if row else 0)


def stage_has_contact_ok_report(
    conn: sqlite3.Connection, *, lead_id: int, stage_key: str
) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM crm_lead_activities
        WHERE lead_id = ?
          AND care_stage_key = ?
          AND activity_type != 'system'
          AND trim(COALESCE(care_status, '')) = ?
        LIMIT 1
        """,
        (int(lead_id), str(stage_key), CONTACT_OK_CARE_STATUS),
    ).fetchone()
    return row is not None


def complete_lead_care_stage(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    stage_key: str,
    note: str = "",
    created_by: str,
    ts: str,
) -> sqlite3.Row:
    from crm_lead_store import fetch_lead_by_id, log_lead_activity, normalize_status

    key = str(stage_key or "").strip()
    if key not in CARE_STAGE_KEYS:
        raise ValueError("Bước chăm sóc không hợp lệ.")
    lead = fetch_lead_by_id(conn, lead_id)
    if lead is None:
        raise ValueError("Không tìm thấy lead.")
    status = normalize_status(str(lead["status"]))
    current = str(lead["care_stage_current"] or "").strip()
    if current not in CARE_STAGE_KEYS:
        current = care_stage_for_status(status)
    if key != current:
        raise ValueError("Chỉ có thể hoàn thành bước đang thực hiện.")
    if count_stage_care_reports(conn, lead_id=lead_id, stage_key=key) < 1:
        raise ValueError(
            "Phải gửi ít nhất một báo cáo chăm sóc cho bước này trước khi hoàn thành."
        )
    if key == "first_contact" and not stage_has_contact_ok_report(
        conn, lead_id=int(lead_id), stage_key=key
    ):
        raise ValueError(
            "Phải có báo cáo trạng thái 「Liên hệ OK」 (da_lien_he_thanh_cong) "
            "trước khi hoàn thành B2."
        )
    note_clean = str(note or "").strip()
    if len(note_clean) < CARE_STAGE_MIN_COMPLETION_NOTE_LEN:
        raise ValueError(
            "Ghi chú hoàn thành bước là bắt buộc (tối thiểu "
            f"{CARE_STAGE_MIN_COMPLETION_NOTE_LEN} ký tự) — GDKD kiểm tra lịch sử chăm sóc."
        )
    done = parse_stages_done_json(str(lead["care_stages_done_json"] or ""))
    done[key] = ts
    stage_meta = CARE_PIPELINE_STAGES[care_stage_index(key)]
    label = stage_meta["label"]
    next_key = care_next_stage_key(key) or key
    activity_body = f"Hoàn thành bước {care_stage_index(key) + 1}: {label}. Ghi chú: {note_clean}"
    log_lead_activity(
        conn,
        lead_id=lead_id,
        activity_type="system",
        content=activity_body,
        created_by=created_by,
        ts=ts,
    )
    conn.execute(
        """
        UPDATE crm_leads
        SET care_stage_current = ?,
            care_stages_done_json = ?,
            updated_at = ?,
            updated_by = ?
        WHERE id = ?
        """,
        (
            next_key,
            serialize_stages_done(done),
            ts,
            created_by[:120],
            int(lead_id),
        ),
    )
    sync_lead_status_to_care_stage(
        conn,
        lead_id=lead_id,
        stage_key=next_key,
        crm_status=str(stage_meta.get("status_on_complete") or ""),
        created_by=created_by,
        ts=ts,
        note=f"Hoàn thành bước: {label}",
    )
    try:
        from crm_svc_lead_sync import sync_lifecycle_from_lead_care_stage

        sync_lifecycle_from_lead_care_stage(
            conn,
            lead_id=lead_id,
            care_stage_key=next_key,
            ts=ts,
            actor=created_by,
        )
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "complete_lead_care_stage sync lifecycle lead_id=%s: %s", lead_id, exc
        )
    row = fetch_lead_by_id(conn, lead_id)
    assert row is not None
    return row


def list_leads_needing_presales_care_backfill(
    conn: sqlite3.Connection,
    *,
    lead_id: int | None = None,
    limit: int | None = None,
    require_presales: bool = True,
) -> list[dict[str, Any]]:
    """Lead thiếu gate B1–B3 (tuỳ chọn: chỉ lead đã có pre-sales active)."""
    sql = """
        SELECT l.id, l.full_name, l.care_stage_current, l.care_stages_done_json,
               p.id AS presales_id, p.stage AS presales_stage, p.service_slug
        FROM crm_leads l
    """
    if require_presales:
        sql += """
        INNER JOIN crm_lead_presales p ON p.lead_id = l.id AND p.status = 'active'
        """
    else:
        sql += """
        LEFT JOIN crm_lead_presales p ON p.lead_id = l.id AND p.status = 'active'
        """
    sql += " WHERE 1=1"
    params: list[Any] = []
    if lead_id:
        sql += " AND l.id = ?"
        params.append(int(lead_id))
    sql += " ORDER BY l.id"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        gate = presales_care_gate_state(
            care_stage_current=str(row["care_stage_current"] or ""),
            care_stages_done_json=str(row["care_stages_done_json"] or ""),
        )
        if gate["complete"]:
            continue
        item = dict(row)
        item["gate"] = gate
        out.append(item)
    return out


def admin_backfill_presales_care_gate(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    created_by: str = "admin-backfill",
    ts: str | None = None,
    note: str = "Backfill gate B2 — lead đã vận hành pre-sales trước khi có gate",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Director/admin: đánh dấu B1–B3 done + báo cáo audit tối thiểu cho lead legacy."""
    from crm_lead_store import fetch_lead_by_id, log_lead_activity

    if ts is None:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    note_clean = str(note or "").strip()
    if len(note_clean) < CARE_STAGE_MIN_COMPLETION_NOTE_LEN:
        raise ValueError(
            f"Ghi chú backfill tối thiểu {CARE_STAGE_MIN_COMPLETION_NOTE_LEN} ký tự."
        )
    lead = fetch_lead_by_id(conn, int(lead_id))
    if lead is None:
        raise ValueError("Không tìm thấy lead.")
    gate_before = presales_care_gate_state(
        care_stage_current=str(lead["care_stage_current"] or ""),
        care_stages_done_json=str(lead["care_stages_done_json"] or ""),
    )
    if gate_before["complete"]:
        return {
            "lead_id": int(lead_id),
            "dry_run": dry_run,
            "skipped": True,
            "reason": "gate_already_complete",
        }

    done = parse_stages_done_json(str(lead["care_stages_done_json"] or ""))
    reports_added: list[str] = []
    stages_marked: list[str] = []
    base_dt = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")

    for offset, key in enumerate(PRESALES_REQUIRED_CARE_STAGES):
        stage_ts = (base_dt + timedelta(minutes=offset)).strftime("%Y-%m-%d %H:%M:%S")
        if count_stage_care_reports(conn, lead_id=int(lead_id), stage_key=key) < 1:
            reports_added.append(key)
            if not dry_run:
                log_lead_activity(
                    conn,
                    lead_id=int(lead_id),
                    activity_type="note",
                    content=f"[Backfill] Báo cáo chăm sóc {key} — {note_clean[:200]}",
                    care_contact_type="note",
                    care_status="da_lien_he_thanh_cong",
                    care_stage_key=key,
                    created_by=created_by[:120],
                    ts=stage_ts,
                )
        if not done.get(key):
            stages_marked.append(key)
            done[key] = stage_ts

    next_key = "first_contact"
    summary: dict[str, Any] = {
        "lead_id": int(lead_id),
        "dry_run": dry_run,
        "skipped": False,
        "reports_added": reports_added,
        "stages_marked": stages_marked,
        "care_stage_current_after": next_key,
        "note": note_clean,
    }
    if dry_run:
        return summary

    log_lead_activity(
        conn,
        lead_id=int(lead_id),
        activity_type="system",
        content=(
            "Admin backfill gate pre-sales B2. "
            f"Bước: {', '.join(stages_marked) or '—'}. Ghi chú: {note_clean}"
        ),
        created_by=created_by[:120],
        ts=ts,
    )
    conn.execute(
        """
        UPDATE crm_leads
        SET care_stage_current = ?,
            care_stages_done_json = ?,
            updated_at = ?,
            updated_by = ?
        WHERE id = ?
        """,
        (
            next_key,
            serialize_stages_done(done),
            ts,
            created_by[:120],
            int(lead_id),
        ),
    )
    conn.commit()
    gate_after = presales_care_gate_state(
        care_stage_current=next_key,
        care_stages_done_json=serialize_stages_done(done),
    )
    summary["gate_complete"] = gate_after["complete"]
    return summary
