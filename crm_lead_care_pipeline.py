"""Pipeline chăm sóc lead 8 bước — tiến độ lưu DB, đồng bộ trạng thái CRM."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

# key, label (UI), hint, statuses (map status→bước hiện tại), status_on_complete (khi hoàn thành bước)
CARE_PIPELINE_STAGES: tuple[dict[str, Any], ...] = (
    {
        "key": "intake",
        "label": "Tiếp nhận & phân loại",
        "hint": "Nhận lead từ quảng cáo, website, hotline, giới thiệu. Phân loại nóng/ấm/lạnh và xác định ngách (shophouse_sme / doi_nha / da_the_he / viet_kieu / legacy). SLA: 8h.",
        "statuses": ("new", "pending_cleanup", "hot", "warm", "cold"),
        "status_on_complete": None,
    },
    {
        "key": "first_contact",
        "label": "Liên hệ lần đầu",
        "hint": "Liên hệ trong 48h — xác nhận nhu cầu, hỏi 5 câu qualify (ngân sách, loại sản phẩm, mục đích, thời điểm, quyết định). Ghi chú ngách khách hàng và gửi bộ tài liệu phù hợp.",
        "statuses": ("contacted",),
        "status_on_complete": "contacted",
    },
    {
        "key": "qualify",
        "label": "Khai thác nhu cầu",
        "hint": "Qualify sâu trong 7 ngày: năng lực tài chính, thời điểm mua, người ra quyết định, dự án đã xem. Xác nhận ngách (shophouse / biệt thự / liền kề đổi nhà / đa thế hệ / Việt kiều). Score lead và gán nhóm chăm sóc phù hợp.",
        "statuses": ("qualified",),
        "status_on_complete": "qualified",
    },
    {
        "key": "advise",
        "label": "Tư vấn & thông tin",
        "hint": "Tư vấn chuyên sâu 14 ngày: gửi tài liệu RSES theo ngách (case study SME / so sánh khu vực đổi nhà / planning đa thế hệ / hướng dẫn Việt kiều mua nhà). Mời tham quan thực tế hoặc buổi tư vấn 1-1.",
        "statuses": ("proposal_sent",),
        "status_on_complete": "proposal_sent",
    },
    {
        "key": "nurture",
        "label": "Nuôi dưỡng",
        "hint": "Nuôi dưỡng 30 ngày (chu kỳ Phase 2: 30–90 ngày): drip data mỗi 5–7 ngày qua Zalo/Email. Xoay nội dung theo ngách — tin thị trường BĐS Hóc Môn, tiến độ dự án, video khách hàng, event mở bán. Không push sale, giữ kết nối bền vững.",
        "statuses": ("nurturing",),
        "status_on_complete": "nurturing",
    },
    {
        "key": "negotiate",
        "label": "Phản đối & đàm phán",
        "hint": "Xử lý 3 phản đối chính Phase 2 trong 21 ngày: (1) Giá cao — so sánh giá/m² với khu vực, dòng tiền cho thuê shophouse; (2) Vị trí — data hạ tầng Vành đai 3, Metro số 2, quy hoạch Hóc Môn; (3) Thị trường yếu — luận điểm end-user, không phụ thuộc đầu cơ. Đề xuất chính sách thanh toán linh hoạt.",
        "statuses": ("negotiation", "lost"),
        "status_on_complete": "negotiation",
    },
    {
        "key": "closing",
        "label": "Chốt giao dịch",
        "hint": "Hỗ trợ 14 ngày: đặt cọc → ký HĐMB → thanh toán đợt 1 → hỗ trợ vay ngân hàng (gói ưu đãi Vinhomes). Với shophouse SME: tư vấn hợp đồng thuê lại. Với liền kề đổi nhà: kết nối đối tác thu mua nhà cũ.",
        "statuses": (),
        "status_on_complete": None,
    },
    {
        "key": "post_sale",
        "label": "Chăm sóc sau bán",
        "hint": "Hỗ trợ bàn giao, xử lý phát sinh, duy trì quan hệ — tái mua hoặc giới thiệu khách mới.",
        "statuses": ("won",),
        "status_on_complete": "won",
    },
)

CARE_STAGE_KEYS: tuple[str, ...] = tuple(s["key"] for s in CARE_PIPELINE_STAGES)

CARE_PIPELINE_STAGES_PUBLIC: list[dict[str, str]] = [
    {"key": s["key"], "label": s["label"], "hint": s["hint"]} for s in CARE_PIPELINE_STAGES
]

CARE_STAGE_STATUS_LABELS: dict[str, str] = {
    str(s["key"]): str(s["label"]) for s in CARE_PIPELINE_STAGES
}

# Trạng thái CRM cũ → bước pipeline (migrate / normalize)
LEGACY_STATUS_TO_CARE_STAGE: dict[str, str] = {
    "new": "intake",
    "pending_cleanup": "intake",
    "hot": "intake",
    "warm": "intake",
    "cold": "intake",
    "contacted": "first_contact",
    "qualified": "qualify",
    "proposal_sent": "advise",
    "nurturing": "nurture",
    "negotiation": "negotiate",
    "won": "post_sale",
}

_STATUS_TO_STAGE: dict[str, str] = dict(LEGACY_STATUS_TO_CARE_STAGE)
for _st in CARE_PIPELINE_STAGES:
    _STATUS_TO_STAGE[str(_st["key"])] = _st["key"]
    for _code in _st.get("statuses") or ():
        _STATUS_TO_STAGE[str(_code)] = _st["key"]
_STATUS_TO_STAGE["won"] = "post_sale"
_STATUS_TO_STAGE["lost"] = "negotiate"


def build_care_status_transitions() -> dict[str, frozenset[str]]:
    """Chuyển trạng thái theo pipeline 8 bước (+ lost / pending_cleanup)."""
    trans: dict[str, set[str]] = {k: set() for k in CARE_STAGE_KEYS}
    for i, key in enumerate(CARE_STAGE_KEYS):
        if i > 0:
            trans[key].add(CARE_STAGE_KEYS[i - 1])
        if i < len(CARE_STAGE_KEYS) - 1:
            trans[key].add(CARE_STAGE_KEYS[i + 1])
        trans[key].add("lost")
    trans["intake"].add("pending_cleanup")
    trans["pending_cleanup"] = {"intake", "first_contact", "lost"}
    trans["lost"] = {CARE_STAGE_KEYS[0], "nurture"}
    return {k: frozenset(v) for k, v in trans.items()}


CARE_STATUS_TRANSITIONS: dict[str, frozenset[str]] = build_care_status_transitions()


def legacy_status_to_care_stage(status: str) -> str:
    s = str(status or "").strip().lower().replace(" ", "_")
    if s in CARE_STAGE_KEYS:
        return s
    return LEGACY_STATUS_TO_CARE_STAGE.get(s, "intake")


def sync_lead_status_to_care_stage(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    stage_key: str | None = None,
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
    return _STATUS_TO_STAGE.get(st, "intake")


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
        if sk in CARE_STAGE_KEYS and v:
            out[sk] = str(v)
    return out


def serialize_stages_done(done: dict[str, str]) -> str:
    clean = {k: done[k] for k in CARE_STAGE_KEYS if k in done and done[k]}
    return json.dumps(clean, ensure_ascii=False)


def care_pipeline_state(
    *,
    status: str,
    care_stage_current: str | None,
    care_stages_done_json: str | None,
) -> dict[str, Any]:
    current = str(care_stage_current or "").strip()
    if current not in CARE_STAGE_KEYS:
        current = care_stage_for_status(status)
    done = parse_stages_done_json(care_stages_done_json)
    cur_idx = care_stage_index(current)
    stages_ui = []
    for i, st in enumerate(CARE_PIPELINE_STAGES):
        key = st["key"]
        completed_at = done.get(key) or ""
        is_done = bool(completed_at) or i < cur_idx
        is_current = key == current
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
    current_meta = CARE_PIPELINE_STAGES[cur_idx] if 0 <= cur_idx < len(CARE_PIPELINE_STAGES) else CARE_PIPELINE_STAGES[0]
    return {
        "current_stage_key": current,
        "current_stage_label": current_meta["label"],
        "current_stage_hint": current_meta["hint"],
        "current_stage_index": cur_idx,
        "stages_done": done,
        "stages": stages_ui,
        "all_complete": cur_idx >= len(CARE_PIPELINE_STAGES) - 1 and bool(done.get(CARE_STAGE_KEYS[-1])),
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
    done = parse_stages_done_json(str(lead["care_stages_done_json"] or ""))
    done[key] = ts
    stage_meta = CARE_PIPELINE_STAGES[care_stage_index(key)]
    label = stage_meta["label"]
    next_key = care_next_stage_key(key) or key
    activity_body = f"Hoàn thành bước {care_stage_index(key) + 1}: {label}."
    if note.strip():
        activity_body += f" {note.strip()}"
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
        created_by=created_by,
        ts=ts,
        note=f"Hoàn thành bước: {label}",
    )
    row = fetch_lead_by_id(conn, lead_id)
    assert row is not None
    return row
