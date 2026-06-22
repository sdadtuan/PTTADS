"""Quy tắc nghiệp vụ Lead — dedup, merge, chuyển trạng thái, cấu hình phân lead."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from crm_lead_store import (
    LEAD_LEVELS,
    LEAD_SOURCE_LABELS,
    LEAD_STATUS_LABELS,
    LEAD_STATUSES,
    TERMINAL_STATUSES,
    assign_lead_owner,
    fetch_lead_by_id,
    find_duplicate_leads,
    lead_needs_cleanup,
    log_assignment,
    log_lead_activity,
    log_status_change,
    normalize_level,
    normalize_source,
    normalize_status,
)

DUPLICATE_POLICIES: tuple[str, ...] = ("flag", "reject", "merge")
INACTIVE_FALLBACK_MODES: tuple[str, ...] = ("round_robin", "min_workload")

DEFAULT_LEAD_CONFIG: dict[str, Any] = {
    "duplicate_policy": "flag",
    "hot_priority_assign": True,
    "inactive_owner_fallback": "round_robin",
    "activity_sla_enabled": True,
    "scoring_rules": None,
    "scoring_rubric": None,
    "scoring_mode": "rubric",
    "level_tiers": [],
    "assign_config": None,
    "facebook_config": None,
}

from crm_lead_care_pipeline import CARE_STATUS_TRANSITIONS

# §11 Allowed transitions — 8 bước chăm sóc (+ lost / pending_cleanup)
LEAD_STATUS_TRANSITIONS: dict[str, frozenset[str]] = CARE_STATUS_TRANSITIONS


def ensure_lead_settings_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_lead_settings (
            config_key TEXT PRIMARY KEY,
            config_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT ''
        )
        """
    )


def _parse_ts(ts: str | None) -> datetime | None:
    raw = str(ts or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")[:19])
    except ValueError:
        return None


def fetch_lead_config(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_lead_settings_schema(conn)
    row = conn.execute(
        "SELECT config_json FROM crm_lead_settings WHERE config_key = 'global'"
    ).fetchone()
    cfg = dict(DEFAULT_LEAD_CONFIG)
    if row:
        try:
            raw = json.loads(str(row["config_json"] or "{}"))
            if isinstance(raw, dict):
                cfg.update(raw)
        except json.JSONDecodeError:
            pass
    dp = str(cfg.get("duplicate_policy") or "flag").strip().lower()
    cfg["duplicate_policy"] = dp if dp in DUPLICATE_POLICIES else "flag"
    fb = str(cfg.get("inactive_owner_fallback") or "round_robin").strip().lower()
    cfg["inactive_owner_fallback"] = fb if fb in INACTIVE_FALLBACK_MODES else "round_robin"
    cfg["hot_priority_assign"] = bool(cfg.get("hot_priority_assign", True))
    cfg["activity_sla_enabled"] = bool(cfg.get("activity_sla_enabled", True))
    from crm_lead_scoring import merge_scoring_rules

    cfg["scoring_rules"] = merge_scoring_rules(cfg.get("scoring_rules"))
    from crm_lead_scoring_rubric import merge_scoring_rubric

    stored_rubric = cfg.get("scoring_rubric")
    if isinstance(stored_rubric, dict):
        cfg["scoring_rubric"] = merge_scoring_rubric(stored_rubric)
    else:
        cfg["scoring_rubric"] = merge_scoring_rubric(None)
    mode = str(cfg.get("scoring_mode") or "rubric").strip().lower()
    cfg["scoring_mode"] = mode if mode in ("rubric", "legacy_rules") else "rubric"
    stored_tiers = cfg.get("level_tiers")
    from crm_lead_tiers import merge_level_tiers

    if isinstance(stored_tiers, list) and stored_tiers:
        try:
            cfg["level_tiers"] = merge_level_tiers(stored_tiers)
        except ValueError:
            cfg["level_tiers"] = merge_level_tiers(None)
    else:
        cfg["level_tiers"] = merge_level_tiers(None)
    from crm_lead_auto_assign import merge_assign_config

    cfg["assign_config"] = merge_assign_config(cfg.get("assign_config"))
    from crm_facebook_config import merge_facebook_config

    cfg["facebook_config"] = merge_facebook_config(cfg.get("facebook_config"))
    return cfg


def save_lead_config(
    conn: sqlite3.Connection,
    *,
    config: dict[str, Any],
    updated_by: str,
    ts: str,
) -> dict[str, Any]:
    ensure_lead_settings_schema(conn)
    merged = fetch_lead_config(conn)
    if "duplicate_policy" in config:
        dp = str(config["duplicate_policy"] or "").strip().lower()
        if dp not in DUPLICATE_POLICIES:
            raise ValueError("duplicate_policy không hợp lệ (flag | reject | merge).")
        merged["duplicate_policy"] = dp
    if "inactive_owner_fallback" in config:
        fb = str(config["inactive_owner_fallback"] or "").strip().lower()
        if fb not in INACTIVE_FALLBACK_MODES:
            raise ValueError("inactive_owner_fallback không hợp lệ.")
        merged["inactive_owner_fallback"] = fb
    if "hot_priority_assign" in config:
        merged["hot_priority_assign"] = bool(config["hot_priority_assign"])
    if "activity_sla_enabled" in config:
        merged["activity_sla_enabled"] = bool(config["activity_sla_enabled"])
    if "scoring_rules" in config:
        from crm_lead_scoring import normalize_scoring_rules

        merged["scoring_rules"] = normalize_scoring_rules(config["scoring_rules"])
    if "scoring_rubric" in config:
        from crm_lead_scoring_rubric import normalize_scoring_rubric

        merged["scoring_rubric"] = normalize_scoring_rubric(config["scoring_rubric"])
    if "scoring_mode" in config:
        mode = str(config["scoring_mode"] or "rubric").strip().lower()
        merged["scoring_mode"] = mode if mode in ("rubric", "legacy_rules") else "rubric"
    if "level_tiers" in config:
        from crm_lead_tiers import normalize_level_tiers

        merged["level_tiers"] = normalize_level_tiers(config["level_tiers"])
    if "assign_config" in config:
        from crm_lead_auto_assign import normalize_assign_config

        merged["assign_config"] = normalize_assign_config(config["assign_config"])
    if "facebook_config" in config:
        from crm_facebook_config import normalize_facebook_config

        merged["facebook_config"] = normalize_facebook_config(config["facebook_config"])
    conn.execute(
        """
        INSERT INTO crm_lead_settings (config_key, config_json, updated_at, updated_by)
        VALUES ('global', ?, ?, ?)
        ON CONFLICT(config_key) DO UPDATE SET
            config_json = excluded.config_json,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (json.dumps(merged, ensure_ascii=False), ts, updated_by[:120]),
    )
    conn.commit()
    return fetch_lead_config(conn)


def allowed_next_statuses(current: str) -> list[str]:
    st = normalize_status(current)
    nxt = LEAD_STATUS_TRANSITIONS.get(st, frozenset())
    return sorted(nxt)


def is_status_transition_allowed(old_status: str, new_status: str) -> bool:
    old = normalize_status(old_status)
    new = normalize_status(new_status)
    if old == new:
        return True
    return new in LEAD_STATUS_TRANSITIONS.get(old, frozenset())


def validate_status_transition(
    old_status: str,
    new_status: str,
    *,
    needs_cleanup: bool,
    allow_override: bool = False,
) -> None:
    """§11 — Kiểm tra chuyển trạng thái hợp lệ và dữ liệu bắt buộc."""
    old = normalize_status(old_status)
    new = normalize_status(new_status)
    if old == new:
        return
    if not is_status_transition_allowed(old, new):
        raise ValueError(
            f"Không được chuyển từ «{LEAD_STATUS_LABELS.get(old, old)}» "
            f"sang «{LEAD_STATUS_LABELS.get(new, new)}»."
        )
    if needs_cleanup and new not in TERMINAL_STATUSES and not allow_override:
        if new not in ("pending_cleanup", "lost"):
            raise ValueError(
                "Lead thiếu dữ liệu bắt buộc — hoàn thiện thông tin hoặc dùng quyền override."
            )


def resolve_duplicate_policy(conn: sqlite3.Connection, explicit: str | None = None) -> str:
    if explicit and str(explicit).strip().lower() in DUPLICATE_POLICIES:
        return str(explicit).strip().lower()
    return str(fetch_lead_config(conn).get("duplicate_policy") or "flag")


def fetch_lead_duplicates(
    conn: sqlite3.Connection, lead_id: int, *, limit: int = 20
) -> list[sqlite3.Row]:
    """Lead trùng phone/email hoặc bản ghi đánh dấu duplicate_of lead này."""
    row = fetch_lead_by_id(conn, lead_id)
    if row is None:
        return []
    d = dict(row)
    lim = max(1, min(int(limit), 100))
    by_ref = conn.execute(
        """
        SELECT l.*, s.name AS owner_name, s.internal_code AS owner_code,
               0 AS activity_count, '' AS last_activity_at
        FROM crm_leads l
        LEFT JOIN crm_staff s ON s.id = l.owner_id
        WHERE l.duplicate_of_id = ? AND l.id != ?
        ORDER BY l.id ASC
        LIMIT ?
        """,
        (int(lead_id), int(lead_id), lim),
    ).fetchall()
    by_match = find_duplicate_leads(
        conn,
        phone=str(d.get("phone") or ""),
        email=str(d.get("email") or ""),
        exclude_id=int(lead_id),
    )
    seen = {int(lead_id)}
    out: list[sqlite3.Row] = []
    for r in list(by_ref) + list(by_match):
        rid = int(r["id"])
        if rid in seen:
            continue
        seen.add(rid)
        out.append(r)
        if len(out) >= lim:
            break
    return out


def _merge_field(primary: str, secondary: str) -> str:
    p = str(primary or "").strip()
    s = str(secondary or "").strip()
    return p if p else s


def merge_incoming_into_primary(
    conn: sqlite3.Connection,
    primary_id: int,
    *,
    full_name: str = "",
    phone: str = "",
    email: str = "",
    source: str = "",
    region: str = "",
    product_interest: str = "",
    need: str = "",
    utm_campaign: str = "",
    merged_by: str,
    ts: str,
    note: str = "",
) -> sqlite3.Row:
    """Gộp dữ liệu lead mới vào lead chính (policy merge khi tạo)."""
    primary = fetch_lead_by_id(conn, primary_id)
    if primary is None:
        raise ValueError("Lead chính không tồn tại.")
    pd = dict(primary)
    if int(pd.get("is_duplicate") or 0):
        raise ValueError("Không thể gộp vào bản ghi duplicate.")
    nm = _merge_field(pd["full_name"], full_name)[:240]
    ph = _merge_field(pd["phone"], phone)[:80]
    em = _merge_field(pd["email"], email)[:240]
    src = normalize_source(source if source else pd["source"])
    reg = _merge_field(pd["region"], region)[:120]
    prod = _merge_field(pd["product_interest"], product_interest)[:300]
    nd = _merge_field(pd["need"], need)[:2000]
    utm = _merge_field(pd["utm_campaign"], utm_campaign)[:200]
    from crm_lead_store import apply_lead_score, normalize_email, normalize_phone

    act_count = int(pd.get("activity_count") or 0)
    conn.execute(
        """
        UPDATE crm_leads SET
            full_name = ?, phone = ?, phone_norm = ?, email = ?, email_norm = ?,
            source = ?, region = ?, product_interest = ?, need = ?,
            utm_campaign = ?,
            updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (
            nm,
            ph,
            normalize_phone(ph),
            em,
            normalize_email(em),
            src,
            reg,
            prod,
            nd,
            utm,
            ts,
            merged_by[:120],
            int(primary_id),
        ),
    )
    apply_lead_score(conn, int(primary_id), updated_by=merged_by, ts=ts)
    log_lead_activity(
        conn,
        lead_id=int(primary_id),
        activity_type="system",
        content=note or f"Dữ liệu trùng được gộp vào lead #{primary_id} (policy merge).",
        created_by=merged_by,
        ts=ts,
    )
    row = fetch_lead_by_id(conn, primary_id)
    assert row is not None
    return row


def merge_leads(
    conn: sqlite3.Connection,
    primary_id: int,
    duplicate_ids: list[int],
    *,
    merged_by: str,
    ts: str,
    reason: str = "",
) -> sqlite3.Row:
    """Gộp các lead trùng vào lead chính — chuyển activity, đánh dấu duplicate."""
    primary = fetch_lead_by_id(conn, primary_id)
    if primary is None:
        raise ValueError("Lead chính không tồn tại.")
    if int(primary["is_duplicate"] or 0):
        raise ValueError("Lead chính không được là bản ghi duplicate.")
    pd = dict(primary)
    dup_ids = sorted({int(x) for x in duplicate_ids if int(x) != int(primary_id)})
    if not dup_ids:
        raise ValueError("Chọn ít nhất một lead trùng để gộp.")

    for did in dup_ids:
        dup = fetch_lead_by_id(conn, did)
        if dup is None:
            raise ValueError(f"Lead #{did} không tồn tại.")
        dd = dict(dup)
        nm = _merge_field(pd["full_name"], dd["full_name"])
        ph = _merge_field(pd["phone"], dd["phone"])
        em = _merge_field(pd["email"], dd["email"])
        reg = _merge_field(pd["region"], dd["region"])
        prod = _merge_field(pd["product_interest"], dd["product_interest"])
        nd = _merge_field(pd["need"], dd["need"])
        pd["full_name"] = nm
        pd["phone"] = ph
        pd["email"] = em
        pd["region"] = reg
        pd["product_interest"] = prod
        pd["need"] = nd
        if not pd.get("owner_id") and dd.get("owner_id"):
            pd["owner_id"] = int(dd["owner_id"])

        conn.execute(
            "UPDATE crm_lead_activities SET lead_id = ? WHERE lead_id = ?",
            (int(primary_id), did),
        )
        conn.execute(
            """
            UPDATE crm_leads SET
                is_duplicate = 1,
                duplicate_of_id = ?,
                status = 'lost',
                updated_at = ?,
                updated_by = ?
            WHERE id = ?
            """,
            (int(primary_id), ts, merged_by[:120], did),
        )
        log_status_change(
            conn,
            lead_id=did,
            old_status=str(dd["status"]),
            new_status="lost",
            changed_by=merged_by,
            note=f"Gộp vào lead #{primary_id}",
            ts=ts,
        )
        log_lead_activity(
            conn,
            lead_id=did,
            activity_type="system",
            content=f"Lead được gộp vào #{primary_id}. {reason}".strip(),
            created_by=merged_by,
            ts=ts,
        )

    from crm_lead_store import apply_lead_score, normalize_email, normalize_phone

    conn.execute(
        """
        UPDATE crm_leads SET
            full_name = ?, phone = ?, phone_norm = ?, email = ?, email_norm = ?,
            region = ?, product_interest = ?, need = ?,
            owner_id = ?,
            updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (
            str(pd["full_name"]).strip()[:240],
            str(pd["phone"]).strip()[:80],
            normalize_phone(pd["phone"]),
            str(pd["email"]).strip()[:240],
            normalize_email(pd["email"]),
            str(pd["region"]).strip()[:120],
            str(pd["product_interest"]).strip()[:300],
            str(pd["need"]).strip()[:2000],
            pd.get("owner_id"),
            ts,
            merged_by[:120],
            int(primary_id),
        ),
    )
    apply_lead_score(conn, int(primary_id), updated_by=merged_by, ts=ts)
    log_lead_activity(
        conn,
        lead_id=int(primary_id),
        activity_type="system",
        content=f"Gộp {len(dup_ids)} lead trùng (#{', #'.join(str(x) for x in dup_ids)}). {reason}".strip(),
        created_by=merged_by,
        ts=ts,
    )
    row = fetch_lead_by_id(conn, primary_id)
    assert row is not None
    return row


def last_user_activity_at(conn: sqlite3.Connection, lead_id: int) -> str | None:
    row = conn.execute(
        """
        SELECT MAX(created_at) AS ts FROM crm_lead_activities
        WHERE lead_id = ? AND activity_type != 'system'
        """,
        (int(lead_id),),
    ).fetchone()
    if row and row["ts"]:
        return str(row["ts"])
    return None


def is_no_activity_sla_overdue(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    status: str,
    status_entered_at: str | None,
    created_at: str | None,
    now: datetime | None = None,
) -> bool:
    from crm_lead_store import STATUS_SLA_HOURS

    st = normalize_status(status)
    sla = STATUS_SLA_HOURS.get(st, 0)
    if sla <= 0 or st in TERMINAL_STATUSES:
        return False
    last_act = last_user_activity_at(conn, lead_id)
    ref_raw = last_act or str(status_entered_at or created_at or "")
    entered = _parse_ts(ref_raw)
    if entered is None:
        return False
    ref = now or datetime.now()
    hours = (ref - entered).total_seconds() / 3600.0
    return hours > sla


def transitions_for_ui() -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for st in LEAD_STATUSES:
        nxt = allowed_next_statuses(st)
        out[st] = [
            {"id": s, "label": LEAD_STATUS_LABELS.get(s, s)} for s in nxt
        ]
    return out
