"""R5 — Kế hoạch MKT sơ bộ @ pre-sales Proposal; TMMT @ lifecycle Deliver."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

PLAN_KIND_PRELIMINARY = "preliminary"
PLAN_KIND_OFFICIAL = "official"
PLAN_KIND_STANDALONE = "standalone"

STRATEGY_FRAMEWORK_KEYS: tuple[str, ...] = (
    "target_market",
    "market_message",
    "media_reach",
    "retention_system",
    "nurture_system",
    "conversion_strategy",
    "world_class_experience",
    "lifecycle_extension",
    "referral_engine",
)

TARGET_MARKET_PROF_KEYS: tuple[str, ...] = (
    "market_context",
    "tam_sam_som",
    "geo_behavior",
    "segmentation_icp",
    "personas_roles",
    "jobs_to_be_done",
    "pains_desired_outcomes",
    "buy_triggers_obstacles",
    "criteria_vs_alternatives",
    "insights_evidence",
    "segment_priorities",
    "success_hypotheses_next",
)

PRELIMINARY_STRATEGY_KEYS: tuple[str, ...] = (
    "market_message",
    "media_reach",
    "conversion_strategy",
)

PRELIMINARY_SUMMARY_FIELDS: tuple[str, ...] = ("north_star", "objectives")

OFFICIAL_TMMT_CORE_KEYS: tuple[str, ...] = (
    "market_context",
    "segmentation_icp",
    "personas_roles",
    "pains_desired_outcomes",
)

OFFICIAL_TMMT_MIN_FILLED = 6


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _ensure_marketing_plans_table(conn: sqlite3.Connection) -> None:
    if _table_exists(conn, "crm_marketing_plans"):
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_marketing_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            priority TEXT NOT NULL DEFAULT 'normal',
            fiscal_year INTEGER NOT NULL DEFAULT 2026,
            period_label TEXT NOT NULL DEFAULT '',
            north_star TEXT NOT NULL DEFAULT '',
            objectives TEXT NOT NULL DEFAULT '',
            pillars_json TEXT NOT NULL DEFAULT '[]',
            audiences TEXT NOT NULL DEFAULT '',
            channels_focus_json TEXT NOT NULL DEFAULT '[]',
            budget_planned_vnd INTEGER NOT NULL DEFAULT 0,
            budget_actual_vnd INTEGER NOT NULL DEFAULT 0,
            success_metrics_json TEXT NOT NULL DEFAULT '[]',
            risks_notes TEXT NOT NULL DEFAULT '',
            owner_staff_id INTEGER,
            start_date TEXT NOT NULL DEFAULT '',
            end_date TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            strategy_framework_json TEXT NOT NULL DEFAULT '{}',
            target_market_prof_json TEXT NOT NULL DEFAULT '{}',
            target_market_steps4_json TEXT NOT NULL DEFAULT '{}',
            khtn_market_research_json TEXT NOT NULL DEFAULT '{}',
            plan_kind TEXT NOT NULL DEFAULT 'standalone',
            lead_id INTEGER,
            presales_id INTEGER,
            lifecycle_id INTEGER,
            source_plan_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, ddl: str
) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        except sqlite3.Error:
            pass


def ensure_r5_schema(conn: sqlite3.Connection) -> None:
    """Migration R5: liên kết KH MKT sơ bộ (presales) và TMMT chính thức (lifecycle)."""
    _ensure_marketing_plans_table(conn)
    for col, ddl in (
        ("plan_kind", "plan_kind TEXT NOT NULL DEFAULT 'standalone'"),
        ("lead_id", "lead_id INTEGER"),
        ("presales_id", "presales_id INTEGER"),
        ("lifecycle_id", "lifecycle_id INTEGER"),
        ("source_plan_id", "source_plan_id INTEGER"),
    ):
        _add_column_if_missing(conn, "crm_marketing_plans", col, ddl)

    if _table_exists(conn, "crm_lead_presales"):
        _add_column_if_missing(
            conn,
            "crm_lead_presales",
            "draft_marketing_plan_id",
            "draft_marketing_plan_id INTEGER",
        )

    if _table_exists(conn, "crm_service_lifecycle"):
        _add_column_if_missing(
            conn,
            "crm_service_lifecycle",
            "marketing_plan_id",
            "marketing_plan_id INTEGER",
        )


def _parse_json_obj(raw: Any, keys: tuple[str, ...]) -> dict[str, str]:
    default = {k: "" for k in keys}
    if raw is None:
        return default
    obj: dict[str, Any] = {}
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                obj = parsed
        except (json.JSONDecodeError, TypeError, ValueError):
            return default
    elif isinstance(raw, dict):
        obj = raw
    else:
        return default
    out = default.copy()
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str):
            out[k] = v.strip()
        elif v is not None:
            out[k] = str(v).strip()
    return out


def _plan_content_dict(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(plan.get("name") or "").strip(),
        "north_star": str(plan.get("north_star") or "").strip(),
        "objectives": str(plan.get("objectives") or "").strip(),
        "strategy_framework": _parse_json_obj(
            plan.get("strategy_framework_json"), STRATEGY_FRAMEWORK_KEYS
        ),
        "target_market_prof": _parse_json_obj(
            plan.get("target_market_prof_json"), TARGET_MARKET_PROF_KEYS
        ),
    }


def validate_preliminary_plan(plan: dict[str, Any] | None) -> dict[str, Any]:
    """Gate consult → proposal: KH MKT sơ bộ tối thiểu."""
    if not plan:
        return {
            "ok": False,
            "complete": False,
            "messages": ["Chưa có Kế hoạch MKT sơ bộ — điền form Báo giá."],
        }
    content = _plan_content_dict(plan)
    messages: list[str] = []
    if not content["name"]:
        messages.append("Nhập tên kế hoạch MKT sơ bộ.")
    if not any(content[f] for f in PRELIMINARY_SUMMARY_FIELDS):
        messages.append("Nhập North Star hoặc Mục tiêu chiến lược.")
    sf = content["strategy_framework"]
    for key in PRELIMINARY_STRATEGY_KEYS:
        if not sf.get(key):
            messages.append(f"Điền khối chiến lược: {key}.")
    ok = not messages
    return {"ok": ok, "complete": ok, "messages": messages}


def validate_official_tmmt(plan: dict[str, Any] | None) -> dict[str, Any]:
    """Gate onboard → deliver: TMMT chính thức trên KH MKT lifecycle."""
    if not plan:
        return {
            "ok": False,
            "complete": False,
            "messages": ["Chưa có Kế hoạch MKT chính thức trên lifecycle."],
        }
    content = _plan_content_dict(plan)
    messages: list[str] = []
    sf = content["strategy_framework"]
    if not sf.get("target_market"):
        messages.append("Điền TMMT tóm tắt (target_market) trong khung chiến lược.")
    prof = content["target_market_prof"]
    for key in OFFICIAL_TMMT_CORE_KEYS:
        if not prof.get(key):
            messages.append(f"Điền TMMT chi tiết: {key}.")
    filled = sum(1 for k in TARGET_MARKET_PROF_KEYS if prof.get(k))
    if filled < OFFICIAL_TMMT_MIN_FILLED:
        messages.append(
            f"TMMT chi tiết cần ít nhất {OFFICIAL_TMMT_MIN_FILLED} mục "
            f"(hiện {filled}/{len(TARGET_MARKET_PROF_KEYS)})."
        )
    ok = not messages
    return {"ok": ok, "complete": ok, "messages": messages}


def get_plan_by_id(conn: sqlite3.Connection, plan_id: int) -> dict[str, Any] | None:
    if not _table_exists(conn, "crm_marketing_plans"):
        return None
    row = conn.execute(
        "SELECT * FROM crm_marketing_plans WHERE id = ?", (int(plan_id),)
    ).fetchone()
    return _row_dict(row)


def get_preliminary_plan_for_presales(
    conn: sqlite3.Connection, presales_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT draft_marketing_plan_id FROM crm_lead_presales WHERE id = ?",
        (int(presales_id),),
    ).fetchone()
    if row is None or not row["draft_marketing_plan_id"]:
        return None
    return get_plan_by_id(conn, int(row["draft_marketing_plan_id"]))


def get_official_plan_for_lifecycle(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT marketing_plan_id FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if row is None or not row["marketing_plan_id"]:
        return None
    return get_plan_by_id(conn, int(row["marketing_plan_id"]))


def _default_strategy_json() -> str:
    return json.dumps({k: "" for k in STRATEGY_FRAMEWORK_KEYS}, ensure_ascii=False)


def _default_tmmt_json() -> str:
    return json.dumps({k: "" for k in TARGET_MARKET_PROF_KEYS}, ensure_ascii=False)


def get_or_create_preliminary_plan(
    conn: sqlite3.Connection,
    presales_id: int,
    *,
    lead_id: int | None = None,
    service_slug: str = "",
) -> dict[str, Any]:
    ensure_r5_schema(conn)
    existing = get_preliminary_plan_for_presales(conn, presales_id)
    if existing:
        return existing

    ps = conn.execute(
        "SELECT lead_id, service_slug FROM crm_lead_presales WHERE id = ?",
        (int(presales_id),),
    ).fetchone()
    if ps is None:
        raise ValueError("Không tìm thấy pre-sales")
    lid = int(lead_id if lead_id is not None else ps["lead_id"])
    slug = str(service_slug or ps["service_slug"] or "").strip()
    ts = _ts()
    name = f"KH MKT sơ bộ — Lead #{lid}"
    if slug:
        name = f"{name} ({slug})"
    cur = conn.execute(
        """
        INSERT INTO crm_marketing_plans (
            code, name, status, plan_kind, lead_id, presales_id,
            north_star, objectives, strategy_framework_json,
            target_market_prof_json, target_market_steps4_json,
            created_at, updated_at
        ) VALUES (?, ?, 'draft', ?, ?, ?, '', '', ?, ?, '{}', ?, ?)
        """,
        (
            f"PS-{presales_id}-DRAFT",
            name[:200],
            PLAN_KIND_PRELIMINARY,
            lid,
            int(presales_id),
            _default_strategy_json(),
            _default_tmmt_json(),
            ts,
            ts,
        ),
    )
    plan_id = int(cur.lastrowid)
    conn.execute(
        """
        UPDATE crm_lead_presales
        SET draft_marketing_plan_id = ?, updated_at = ?
        WHERE id = ?
        """,
        (plan_id, ts, int(presales_id)),
    )
    conn.commit()
    plan = get_plan_by_id(conn, plan_id)
    assert plan is not None
    return plan


def update_preliminary_plan(
    conn: sqlite3.Connection,
    presales_id: int,
    patch: dict[str, Any],
) -> dict[str, Any]:
    plan = get_or_create_preliminary_plan(conn, presales_id)
    plan_id = int(plan["id"])
    ts = _ts()

    sets: list[str] = ["updated_at = ?"]
    params: list[Any] = [ts]

    for field in ("name", "north_star", "objectives", "notes"):
        if field in patch:
            sets.append(f"{field} = ?")
            params.append(str(patch[field] or "").strip()[:8000])

    if "strategy_framework" in patch and isinstance(patch["strategy_framework"], dict):
        current = _parse_json_obj(plan.get("strategy_framework_json"), STRATEGY_FRAMEWORK_KEYS)
        for k in STRATEGY_FRAMEWORK_KEYS:
            if k in patch["strategy_framework"]:
                current[k] = str(patch["strategy_framework"][k] or "").strip()[:12000]
        sets.append("strategy_framework_json = ?")
        params.append(json.dumps(current, ensure_ascii=False))

    params.append(plan_id)
    conn.execute(
        f"UPDATE crm_marketing_plans SET {', '.join(sets)} WHERE id = ?",
        params,
    )
    conn.commit()
    updated = get_plan_by_id(conn, plan_id)
    assert updated is not None
    return updated


def update_official_plan(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    patch: dict[str, Any],
) -> dict[str, Any]:
    plan = get_official_plan_for_lifecycle(conn, lifecycle_id)
    if plan is None:
        raise ValueError("Lifecycle chưa có Kế hoạch MKT chính thức")
    plan_id = int(plan["id"])
    ts = _ts()
    sets: list[str] = ["updated_at = ?"]
    params: list[Any] = [ts]

    if "strategy_framework" in patch and isinstance(patch["strategy_framework"], dict):
        current = _parse_json_obj(plan.get("strategy_framework_json"), STRATEGY_FRAMEWORK_KEYS)
        for k in STRATEGY_FRAMEWORK_KEYS:
            if k in patch["strategy_framework"]:
                current[k] = str(patch["strategy_framework"][k] or "").strip()[:12000]
        sets.append("strategy_framework_json = ?")
        params.append(json.dumps(current, ensure_ascii=False))

    if "target_market_prof" in patch and isinstance(patch["target_market_prof"], dict):
        current = _parse_json_obj(plan.get("target_market_prof_json"), TARGET_MARKET_PROF_KEYS)
        for k in TARGET_MARKET_PROF_KEYS:
            if k in patch["target_market_prof"]:
                current[k] = str(patch["target_market_prof"][k] or "").strip()[:8000]
        sets.append("target_market_prof_json = ?")
        params.append(json.dumps(current, ensure_ascii=False))

    params.append(plan_id)
    conn.execute(
        f"UPDATE crm_marketing_plans SET {', '.join(sets)} WHERE id = ?",
        params,
    )
    conn.commit()
    updated = get_plan_by_id(conn, plan_id)
    assert updated is not None
    return updated


def validate_presales_proposal_advance(
    conn: sqlite3.Connection, presales_id: int
) -> dict[str, Any]:
    plan = get_preliminary_plan_for_presales(conn, presales_id)
    if plan is None:
        plan = get_or_create_preliminary_plan(conn, presales_id)
    gate = validate_preliminary_plan(plan)
    return {
        **gate,
        "plan_id": int(plan["id"]) if plan else None,
        "plan_kind": PLAN_KIND_PRELIMINARY,
    }


def clone_preliminary_to_official(
    conn: sqlite3.Connection,
    presales_id: int,
    lifecycle_id: int,
) -> int:
    """Promote: nhân bản KH sơ bộ → KH chính thức gắn lifecycle."""
    ensure_r5_schema(conn)
    draft = get_preliminary_plan_for_presales(conn, presales_id)
    if draft is None:
        raise ValueError("Thiếu Kế hoạch MKT sơ bộ — không thể promote")
    gate = validate_preliminary_plan(draft)
    if not gate.get("ok"):
        raise ValueError(
            (gate.get("messages") or ["KH MKT sơ bộ chưa đủ"])[0]
        )

    lc = conn.execute(
        "SELECT lead_id, service_slug FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if lc is None:
        raise ValueError("Không tìm thấy lifecycle")

    ts = _ts()
    draft_id = int(draft["id"])
    name = str(draft.get("name") or "").strip()
    if not name.endswith("(chính thức)"):
        name = f"{name} (chính thức)"[:200]

    cur = conn.execute(
        """
        INSERT INTO crm_marketing_plans (
            code, name, status, plan_kind, lead_id, presales_id, lifecycle_id,
            source_plan_id, north_star, objectives, notes,
            strategy_framework_json, target_market_prof_json,
            target_market_steps4_json, khtn_market_research_json,
            pillars_json, channels_focus_json, success_metrics_json,
            audiences, fiscal_year, period_label, created_at, updated_at
        )
        SELECT
            ?, ?, 'draft', ?, lead_id, presales_id, ?,
            id, north_star, objectives, notes,
            strategy_framework_json, target_market_prof_json,
            target_market_steps4_json, khtn_market_research_json,
            pillars_json, channels_focus_json, success_metrics_json,
            audiences, fiscal_year, period_label, ?, ?
        FROM crm_marketing_plans WHERE id = ?
        """,
        (
            f"LC-{lifecycle_id}-OFFICIAL",
            name,
            PLAN_KIND_OFFICIAL,
            int(lifecycle_id),
            ts,
            ts,
            draft_id,
        ),
    )
    official_id = int(cur.lastrowid)
    conn.execute(
        """
        UPDATE crm_service_lifecycle
        SET marketing_plan_id = ?, updated_at = ?
        WHERE id = ?
        """,
        (official_id, ts, int(lifecycle_id)),
    )
    conn.commit()
    return official_id


def validate_lifecycle_deliver_advance(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, Any]:
    plan = get_official_plan_for_lifecycle(conn, lifecycle_id)
    gate = validate_official_tmmt(plan)
    return {
        **gate,
        "plan_id": int(plan["id"]) if plan else None,
        "plan_kind": PLAN_KIND_OFFICIAL,
    }


def preliminary_plan_payload(
    conn: sqlite3.Connection, presales_id: int
) -> dict[str, Any]:
    plan = get_or_create_preliminary_plan(conn, presales_id)
    content = _plan_content_dict(plan)
    validation = validate_preliminary_plan(plan)
    return {
        "plan": {
            "id": plan["id"],
            "name": content["name"],
            "north_star": content["north_star"],
            "objectives": content["objectives"],
            "strategy_framework": content["strategy_framework"],
            "plan_kind": plan.get("plan_kind") or PLAN_KIND_PRELIMINARY,
        },
        "validation": validation,
        "strategy_keys": list(PRELIMINARY_STRATEGY_KEYS),
        "summary_fields": list(PRELIMINARY_SUMMARY_FIELDS),
    }


def official_plan_payload(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, Any]:
    plan = get_official_plan_for_lifecycle(conn, lifecycle_id)
    if plan is None:
        return {"plan": None, "validation": validate_official_tmmt(None)}
    content = _plan_content_dict(plan)
    return {
        "plan": {
            "id": plan["id"],
            "name": content["name"],
            "strategy_framework": content["strategy_framework"],
            "target_market_prof": content["target_market_prof"],
            "plan_kind": plan.get("plan_kind") or PLAN_KIND_OFFICIAL,
        },
        "validation": validate_official_tmmt(plan),
        "tmmt_core_keys": list(OFFICIAL_TMMT_CORE_KEYS),
        "tmmt_min_filled": OFFICIAL_TMMT_MIN_FILLED,
    }
