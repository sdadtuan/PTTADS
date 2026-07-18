"""CRM Lead Intake sessions — lưu form gọi/gặp KH, sync task Lead."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any

from crm_lead_intake_definitions import (
    BANT_KEYS,
    COMMON_FORM_SLUG,
    GO_THRESHOLDS,
    STAKEHOLDER_ROLES,
    is_common_slug,
    normalize_intake_slug,
)

logger = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5-20251001"

VALID_MODES = frozenset({"phone", "in_person"})
VALID_DECISIONS = frozenset({"go", "nurture", "no_go", ""})
VALID_TEMPERATURES = frozenset({"hot", "warm", "cold", ""})
VALID_STATUS = frozenset({"draft", "completed"})


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_lead_intake_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id         INTEGER,
            lifecycle_id    INTEGER,
            service_slug    TEXT NOT NULL DEFAULT '',
            mode            TEXT NOT NULL DEFAULT 'phone',
            status          TEXT NOT NULL DEFAULT 'draft',
            am_id           INTEGER,

            contact_name    TEXT NOT NULL DEFAULT '',
            contact_role    TEXT NOT NULL DEFAULT '',
            company_name    TEXT NOT NULL DEFAULT '',
            source          TEXT NOT NULL DEFAULT '',

            bant_json       TEXT NOT NULL DEFAULT '{}',
            bant_total      INTEGER NOT NULL DEFAULT 0,
            lead_temperature TEXT NOT NULL DEFAULT '',
            decision        TEXT NOT NULL DEFAULT '',
            decision_reason TEXT NOT NULL DEFAULT '',

            answers_json    TEXT NOT NULL DEFAULT '{}',
            stakeholders_json TEXT NOT NULL DEFAULT '[]',
            commitments_json  TEXT NOT NULL DEFAULT '[]',

            next_meeting_at   TEXT NOT NULL DEFAULT '',
            next_meeting_note TEXT NOT NULL DEFAULT '',
            proposal_date     TEXT NOT NULL DEFAULT '',

            ai_summary        TEXT NOT NULL DEFAULT '',
            ai_suggested_questions TEXT NOT NULL DEFAULT '',

            started_at      TEXT NOT NULL DEFAULT '',
            completed_at    TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT '',
            updated_at      TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_intake_lifecycle "
        "ON crm_lead_intake_sessions(lifecycle_id, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_intake_lead "
        "ON crm_lead_intake_sessions(lead_id, mode)"
    )
    cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(crm_lead_intake_sessions)").fetchall()
    }
    if "ai_suggested_questions" not in cols:
        conn.execute(
            "ALTER TABLE crm_lead_intake_sessions "
            "ADD COLUMN ai_suggested_questions TEXT NOT NULL DEFAULT ''"
        )
    conn.commit()


def _parse_json(raw: str, default: Any) -> Any:
    try:
        val = json.loads(raw or "")
        return val if val is not None else default
    except (json.JSONDecodeError, TypeError):
        return default


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["bant_json"] = _parse_json(str(d.get("bant_json") or ""), {})
    d["answers_json"] = _parse_json(str(d.get("answers_json") or ""), {})
    d["stakeholders_json"] = _parse_json(str(d.get("stakeholders_json") or ""), [])
    d["commitments_json"] = _parse_json(str(d.get("commitments_json") or ""), [])
    raw_q = str(d.get("ai_suggested_questions") or "").strip()
    if raw_q.startswith("["):
        d["ai_suggested_questions"] = _parse_json(raw_q, [])
    elif raw_q:
        d["ai_suggested_questions"] = [raw_q]
    else:
        d["ai_suggested_questions"] = []
    return d


def compute_bant_total(bant_json: dict[str, Any]) -> int:
    total = 0
    for key in BANT_KEYS:
        try:
            score = int(bant_json.get(key) or 0)
        except (TypeError, ValueError):
            score = 0
        if 1 <= score <= 5:
            total += score
    return total


def suggest_decision(bant_total: int, red_flag_count: int = 0) -> str:
    if red_flag_count >= 3:
        return "no_go"
    if bant_total >= GO_THRESHOLDS["go"]:
        return "go"
    if bant_total >= GO_THRESHOLDS["nurture_min"]:
        return "nurture"
    return "no_go"


def default_stakeholders() -> list[dict[str, str]]:
    return [
        {"role": role, "role_label": label, "name": "", "title": "", "influence": "", "notes": ""}
        for role, label in STAKEHOLDER_ROLES
    ]


def default_commitments() -> list[dict[str, str]]:
    return [
        {"label": "Cam kết 1 — Thông tin", "detail": "", "deadline": ""},
        {"label": "Cam kết 2 — Thời gian", "detail": "", "deadline": ""},
        {"label": "Cam kết 3 — Ngân sách / quyết định", "detail": "", "deadline": ""},
    ]


def _resolve_lead_id(
    conn: sqlite3.Connection,
    *,
    lifecycle_id: int | None = None,
    lead_id: int | None = None,
) -> int | None:
    if lead_id:
        return int(lead_id)
    if not lifecycle_id:
        return None
    row = conn.execute(
        "SELECT lead_id FROM crm_service_lifecycle WHERE id = ?",
        (lifecycle_id,),
    ).fetchone()
    if row and row["lead_id"]:
        return int(row["lead_id"])
    return None


def get_latest_completed_session(
    conn: sqlite3.Connection,
    *,
    lifecycle_id: int,
    mode: str = "phone",
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM crm_lead_intake_sessions
        WHERE lifecycle_id = ? AND mode = ? AND status = 'completed'
        ORDER BY completed_at DESC, id DESC
        LIMIT 1
        """,
        (lifecycle_id, mode),
    ).fetchone()
    return _row_to_dict(row) if row else None


def build_recap_from_session(phone_session: dict[str, Any]) -> str:
    """Tóm tắt buổi gọi cho prefill PHẦN B."""
    parts: list[str] = []
    if phone_session.get("contact_name"):
        parts.append(f"Liên hệ: {phone_session['contact_name']}")
    parts.append(f"BANT {phone_session.get('bant_total') or 0}/30")
    if phone_session.get("decision"):
        parts.append(f"Quyết định: {phone_session['decision']}")
    answers = phone_session.get("answers_json") or {}
    meta = answers.get("meta") if isinstance(answers.get("meta"), dict) else {}
    if meta.get("pain_summary"):
        parts.append(f"Pain: {meta['pain_summary']}")
    phone = answers.get("phone") if isinstance(answers.get("phone"), dict) else {}
    snippets: list[str] = []
    for key in sorted(phone.keys(), key=lambda k: int(k[1:]) if k.startswith("p") and k[1:].isdigit() else 999):
        val = str(phone.get(key) or "").strip()
        if val:
            plain = val.replace("<", " ").replace(">", " ")
            if len(plain) > 120:
                plain = plain[:117] + "…"
            snippets.append(plain)
        if len(snippets) >= 4:
            break
    if snippets:
        parts.append("Ghi chú gọi: " + " · ".join(snippets))
    return "\n".join(parts)[:4000]


def fetch_lead_prefill(conn: sqlite3.Connection, lead_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT full_name, need, source, meta_json
        FROM crm_leads WHERE id = ?
        """,
        (int(lead_id),),
    ).fetchone()
    if row is None:
        return {}
    try:
        meta = json.loads(str(row["meta_json"] or "{}"))
    except json.JSONDecodeError:
        meta = {}
    ai_brief = meta.get("ai_qualify_brief") if isinstance(meta.get("ai_qualify_brief"), dict) else {}
    pain = str(row["need"] or "").strip()
    if not pain and isinstance(ai_brief.get("summary"), str):
        pain = ai_brief["summary"].strip()
    from crm_lead_store import LEAD_SOURCE_LABELS, normalize_source

    src = normalize_source(row["source"])
    crm_fields: dict[str, str] = {}
    if row["need"]:
        crm_fields["need"] = str(row["need"])[:4000]
    meta_block: dict[str, Any] = {
        "pain_summary": pain[:4000],
        "ai_brief": str(ai_brief.get("summary") or "")[:4000],
    }
    if ai_brief.get("service_slug"):
        meta_block["qualify_service_slug"] = str(ai_brief["service_slug"])[:120]
    qualify_qs = ai_brief.get("qualify_questions")
    if isinstance(qualify_qs, list) and qualify_qs:
        meta_block["qualify_questions"] = [str(q)[:500] for q in qualify_qs[:8]]
    opening = ai_brief.get("opening_line")
    if opening:
        meta_block["opening_line"] = str(opening)[:1000]
    return {
        "contact_name": str(row["full_name"] or "")[:500],
        "source": str(LEAD_SOURCE_LABELS.get(src, src) or src)[:200],
        "answers_json": {
            "meta": meta_block,
            "crm_fields": crm_fields,
        },
    }


def prefill_session(
    conn: sqlite3.Connection,
    session_id: int,
    *,
    lifecycle_id: int | None = None,
    lead_id: int | None = None,
    mode: str = "phone",
) -> dict[str, Any] | None:
    """Prefill session mới từ lead + recap buổi gọi (in_person)."""
    session = get_session(conn, session_id)
    if session is None:
        return None
    payload: dict[str, Any] = {}
    lid = _resolve_lead_id(conn, lifecycle_id=lifecycle_id, lead_id=lead_id)
    if lid:
        payload.update(fetch_lead_prefill(conn, lid))

    lc_id = lifecycle_id or session.get("lifecycle_id")
    recap_meta: dict[str, Any] = {}
    phone_session: dict[str, Any] | None = None
    if mode == "in_person" and lc_id:
        phone_session = get_latest_completed_session(conn, lifecycle_id=int(lc_id), mode="phone")
        if phone_session:
            recap_text = build_recap_from_session(phone_session)
            recap_meta = {
                "phone_session_id": phone_session.get("id"),
                "phone_completed_at": phone_session.get("completed_at") or "",
                "recap": recap_text,
            }
            if phone_session.get("contact_name"):
                payload["contact_name"] = phone_session["contact_name"]
            if phone_session.get("company_name"):
                payload["company_name"] = phone_session["company_name"]
            if phone_session.get("bant_json") and not session.get("bant_total"):
                payload["bant_json"] = phone_session.get("bant_json")

    if recap_meta or payload.get("answers_json"):
        existing_answers = session.get("answers_json") or {}
        if not isinstance(existing_answers, dict):
            existing_answers = {}
        merged_answers = {**existing_answers}
        if payload.get("answers_json"):
            src = payload.pop("answers_json")
            merged_meta = dict(merged_answers.get("meta") or {})
            merged_meta.update(src.get("meta") or {})
            if recap_meta:
                merged_meta.update(recap_meta)
            merged_answers["meta"] = merged_meta
            merged_crm = dict(merged_answers.get("crm_fields") or {})
            merged_crm.update(src.get("crm_fields") or {})
            merged_answers["crm_fields"] = merged_crm
            if recap_meta.get("recap"):
                merged_answers["recap"] = recap_meta["recap"]
        elif recap_meta:
            merged_meta = dict(merged_answers.get("meta") or {})
            merged_meta.update(recap_meta)
            merged_answers["meta"] = merged_meta
            if recap_meta.get("recap"):
                merged_answers["recap"] = recap_meta["recap"]
        payload["answers_json"] = merged_answers

    if not payload:
        return session
    return update_session(conn, session_id, payload)


def resolve_intake_entry(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    mode: str = "phone",
    form: str = "",
) -> dict[str, Any]:
    from crm_service_lifecycle import get_by_lead

    mode = str(mode or "phone").strip()
    if mode not in VALID_MODES:
        mode = "phone"
    form_key = str(form or "").strip().lower()
    force_common = form_key in ("common", "_common", "1", "true", "yes", "chung")

    lc = get_by_lead(conn, lead_id)
    if force_common or lc is None:
        return {
            "ok": True,
            "lead_id": lead_id,
            "lifecycle_id": None,
            "service_slug": COMMON_FORM_SLUG,
            "is_common_form": True,
            "redirect_url": (
                f"/crm/intake?lead_id={lead_id}&mode={mode}"
                f"&service_slug={COMMON_FORM_SLUG}&auto_create=1"
            ),
        }

    lc = dict(lc)
    slug = str(lc.get("service_slug") or "").strip()
    from crm_lead_intake_definitions import resolve_definition_slug

    def_slug = resolve_definition_slug(slug)
    is_common = def_slug == COMMON_FORM_SLUG
    params = f"lifecycle_id={lc['id']}&mode={mode}&auto_create=1"
    if is_common:
        params += f"&service_slug={COMMON_FORM_SLUG}"
    return {
        "ok": True,
        "lifecycle_id": lc["id"],
        "lead_id": lead_id,
        "service_slug": COMMON_FORM_SLUG if is_common else slug,
        "is_common_form": is_common,
        "redirect_url": f"/crm/intake?{params}",
    }


def _log_intake_activity(
    conn: sqlite3.Connection,
    session: dict[str, Any],
    *,
    actor_id: int | None = None,
) -> None:
    lead_id = _resolve_lead_id(
        conn,
        lifecycle_id=session.get("lifecycle_id"),
        lead_id=session.get("lead_id"),
    )
    if not lead_id:
        return
    try:
        from crm_lead_store import log_lead_activity
    except Exception:
        return

    mode = session.get("mode") or "phone"
    mode_vi = "gọi điện" if mode == "phone" else "gặp trực tiếp"
    act_type = "call" if mode == "phone" else "meeting"
    content = (
        f"Lead Intake #{session.get('id')} ({mode_vi})"
        + (" · Form chung" if is_common_slug(str(session.get("service_slug") or "")) else "")
        + f" · BANT {session.get('bant_total') or 0}/30 · "
        f"{session.get('decision') or '—'}"
    )
    if session.get("decision_reason"):
        content += f" · {session['decision_reason'][:200]}"
    next_action = ""
    next_at = ""
    if mode == "phone" and session.get("decision") == "go":
        next_action = "Hẹn gặp KH (PHẦN B)"
        next_at = str(session.get("next_meeting_at") or "")[:40]
    try:
        log_lead_activity(
            conn,
            lead_id=int(lead_id),
            activity_type=act_type,
            content=content[:8000],
            result=str(session.get("decision") or "")[:500],
            next_action=next_action[:500],
            next_action_at=next_at,
            user_id=actor_id,
            ts=_ts(),
        )
    except Exception:
        conn.execute(
            """
            INSERT INTO crm_lead_activities (
                lead_id, activity_type, content, result,
                next_action, next_action_at, created_at, created_by,
                lead_status_at_log, care_stage_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '', 'new', 'intake')
            """,
            (
                int(lead_id),
                act_type,
                content[:8000],
                str(session.get("decision") or "")[:500],
                next_action[:500],
                next_at,
                _ts(),
            ),
        )
        conn.commit()

def create_session(
    conn: sqlite3.Connection,
    *,
    lifecycle_id: int | None = None,
    lead_id: int | None = None,
    service_slug: str,
    mode: str = "phone",
    am_id: int | None = None,
    contact_name: str = "",
    contact_role: str = "",
    company_name: str = "",
    source: str = "",
) -> int:
    if not lifecycle_id and not lead_id:
        raise ValueError("lifecycle_id hoặc lead_id bắt buộc")
    service_slug = normalize_intake_slug(service_slug) or COMMON_FORM_SLUG
    mode = str(mode or "phone").strip()
    if mode not in VALID_MODES:
        mode = "phone"
    if not lead_id and lifecycle_id:
        lead_id = _resolve_lead_id(conn, lifecycle_id=lifecycle_id)
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_lead_intake_sessions (
            lead_id, lifecycle_id, service_slug, mode, status, am_id,
            contact_name, contact_role, company_name, source,
            bant_json, bant_total, stakeholders_json, commitments_json,
            answers_json, started_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, '{}', 0, ?, ?, '{}', ?, ?, ?)
        """,
        (
            lead_id,
            lifecycle_id,
            str(service_slug or "").strip(),
            mode,
            am_id,
            str(contact_name or "")[:500],
            str(contact_role or "")[:200],
            str(company_name or "")[:500],
            str(source or "")[:200],
            json.dumps(default_stakeholders(), ensure_ascii=False),
            json.dumps(default_commitments(), ensure_ascii=False),
            ts,
            ts,
            ts,
        ),
    )
    conn.commit()
    sid = int(cur.lastrowid)
    prefill_session(
        conn,
        sid,
        lifecycle_id=lifecycle_id,
        lead_id=lead_id,
        mode=mode,
    )
    return sid


def get_session(conn: sqlite3.Connection, session_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM crm_lead_intake_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def list_sessions(
    conn: sqlite3.Connection,
    *,
    lifecycle_id: int | None = None,
    lead_id: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if lifecycle_id:
        rows = conn.execute(
            """
            SELECT * FROM crm_lead_intake_sessions
            WHERE lifecycle_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (lifecycle_id, limit),
        ).fetchall()
    elif lead_id:
        rows = conn.execute(
            """
            SELECT * FROM crm_lead_intake_sessions
            WHERE lead_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (lead_id, limit),
        ).fetchall()
    else:
        return []
    return [_row_to_dict(r) for r in rows]


def update_session(
    conn: sqlite3.Connection,
    session_id: int,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    prev = get_session(conn, session_id)
    if prev is None:
        return None
    if prev.get("status") == "completed" and payload.get("status") != "draft":
        pass  # allow edit completed — reopen as draft if explicitly requested

    merged: dict[str, Any] = dict(prev)
    scalar_fields = (
        "mode", "contact_name", "contact_role", "company_name", "source",
        "lead_temperature", "decision", "decision_reason",
        "next_meeting_at", "next_meeting_note", "proposal_date", "status",
    )
    for field in scalar_fields:
        if field in payload:
            val = payload[field]
            if field == "mode" and str(val) not in VALID_MODES:
                continue
            if field == "decision" and str(val) not in VALID_DECISIONS:
                continue
            if field == "lead_temperature" and str(val) not in VALID_TEMPERATURES:
                continue
            if field == "status" and str(val) not in VALID_STATUS:
                continue
            merged[field] = str(val or "")[:4000] if isinstance(val, str) else val

    if "bant_json" in payload and isinstance(payload["bant_json"], dict):
        merged["bant_json"] = payload["bant_json"]
    if "answers_json" in payload and isinstance(payload["answers_json"], dict):
        merged["answers_json"] = payload["answers_json"]
    if "stakeholders_json" in payload and isinstance(payload["stakeholders_json"], list):
        merged["stakeholders_json"] = payload["stakeholders_json"]
    if "commitments_json" in payload and isinstance(payload["commitments_json"], list):
        merged["commitments_json"] = payload["commitments_json"]

    merged["bant_total"] = compute_bant_total(merged.get("bant_json") or {})

    ts = _ts()
    conn.execute(
        """
        UPDATE crm_lead_intake_sessions SET
            mode = ?, contact_name = ?, contact_role = ?, company_name = ?, source = ?,
            bant_json = ?, bant_total = ?, lead_temperature = ?, decision = ?, decision_reason = ?,
            answers_json = ?, stakeholders_json = ?, commitments_json = ?,
            next_meeting_at = ?, next_meeting_note = ?, proposal_date = ?,
            status = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            merged.get("mode") or "phone",
            str(merged.get("contact_name") or "")[:500],
            str(merged.get("contact_role") or "")[:200],
            str(merged.get("company_name") or "")[:500],
            str(merged.get("source") or "")[:200],
            json.dumps(merged.get("bant_json") or {}, ensure_ascii=False),
            int(merged.get("bant_total") or 0),
            str(merged.get("lead_temperature") or "")[:20],
            str(merged.get("decision") or "")[:20],
            str(merged.get("decision_reason") or "")[:4000],
            json.dumps(merged.get("answers_json") or {}, ensure_ascii=False)[:500000],
            json.dumps(merged.get("stakeholders_json") or [], ensure_ascii=False)[:50000],
            json.dumps(merged.get("commitments_json") or [], ensure_ascii=False)[:50000],
            str(merged.get("next_meeting_at") or "")[:50],
            str(merged.get("next_meeting_note") or "")[:4000],
            str(merged.get("proposal_date") or "")[:50],
            str(merged.get("status") or "draft")[:20],
            ts,
            session_id,
        ),
    )
    conn.commit()
    return get_session(conn, session_id)


def _build_task_notes(session: dict[str, Any]) -> str:
    parts = [
        f"[Intake #{session.get('id')}] mode={session.get('mode')}",
        f"BANT={session.get('bant_total')}",
        f"decision={session.get('decision') or '-'}",
        f"temp={session.get('lead_temperature') or '-'}",
    ]
    if session.get("decision_reason"):
        parts.append(f"Lý do: {session['decision_reason']}")
    return " · ".join(parts)[:4000]


def _extract_crm_form_data(session: dict[str, Any]) -> dict[str, Any]:
    """Map intake → form_fields stage Lead (best effort + crm_fields trong answers)."""
    from crm_lead_intake_definitions import COMMON_CRM_FIELDS
    from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS

    answers = session.get("answers_json") or {}
    crm_fields = answers.get("crm_fields") if isinstance(answers.get("crm_fields"), dict) else {}
    slug = str(session.get("service_slug") or "")
    if is_common_slug(slug):
        allowed_keys = {f["key"] for f in COMMON_CRM_FIELDS}
    else:
        steps = SERVICE_WORKFLOW_STEPS.get(slug, {}).get("lead", [])
        allowed_keys = {f["key"] for f in (steps[0].get("form_fields") if steps else [])}

    out: dict[str, Any] = {}
    for key in allowed_keys:
        if key in crm_fields and crm_fields[key] not in (None, ""):
            out[key] = crm_fields[key]

    # Fallback từ meta
    meta = answers.get("meta") if isinstance(answers.get("meta"), dict) else {}
    if "need" in allowed_keys and not out.get("need"):
        pain = str(meta.get("pain_summary") or answers.get("recap") or "")[:4000]
        if pain:
            out["need"] = pain

    out["intake_session_id"] = session.get("id")
    out["bant_total"] = session.get("bant_total")
    out["decision"] = session.get("decision")
    out["lead_temperature"] = session.get("lead_temperature")
    return out


def _sync_common_intake_to_lead(conn: sqlite3.Connection, session: dict[str, Any]) -> None:
    """Ghi need / ghi chú từ form chung vào lead khi không có lifecycle task."""
    if not is_common_slug(str(session.get("service_slug") or "")):
        return
    if session.get("lifecycle_id"):
        return
    lead_id = _resolve_lead_id(
        conn,
        lifecycle_id=session.get("lifecycle_id"),
        lead_id=session.get("lead_id"),
    )
    if not lead_id:
        return
    answers = session.get("answers_json") or {}
    crm = answers.get("crm_fields") if isinstance(answers.get("crm_fields"), dict) else {}
    meta = answers.get("meta") if isinstance(answers.get("meta"), dict) else {}
    need = str(crm.get("need") or meta.get("pain_summary") or "").strip()
    if not need:
        return
    row = conn.execute(
        "SELECT need FROM crm_leads WHERE id = ?", (int(lead_id),)
    ).fetchone()
    if row is None:
        return
    prev_need = str(row["need"] or "").strip()
    if prev_need:
        return
    ts = _ts()
    conn.execute(
        "UPDATE crm_leads SET need = ?, updated_at = ? WHERE id = ?",
        (need[:4000], ts, int(lead_id)),
    )
    conn.commit()


def merge_to_lead_task(conn: sqlite3.Connection, session_id: int) -> bool:
    session = get_session(conn, session_id)
    if not session or not session.get("lifecycle_id"):
        return False
    from crm_svc_tasks import list_tasks, update_task

    tasks_by_stage = list_tasks(conn, int(session["lifecycle_id"]))
    lead_tasks = tasks_by_stage.get("lead") or []
    if not lead_tasks:
        return False
    task = lead_tasks[0]
    existing = task.get("form_data") or {}
    if not isinstance(existing, dict):
        existing = {}
    merged_form = {**existing, **_extract_crm_form_data(session)}
    notes = _build_task_notes(session)
    prev_notes = str(task.get("notes") or "").strip()
    if prev_notes and "[Intake #" not in prev_notes:
        notes = f"{prev_notes}\n\n{notes}"
    update_task(conn, int(task["id"]), form_data=merged_form, notes=notes[:4000])
    return True


def complete_session(
    conn: sqlite3.Connection,
    session_id: int,
    *,
    actor_id: int | None = None,
) -> dict[str, Any] | None:
    session = get_session(conn, session_id)
    if session is None:
        return None
    if not str(session.get("decision") or "").strip():
        raise ValueError("Cần chọn quyết định Go / Nurture / No-Go trước khi hoàn thành")

    ts = _ts()
    conn.execute(
        """
        UPDATE crm_lead_intake_sessions
        SET status = 'completed', completed_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (ts, ts, session_id),
    )
    conn.commit()
    merge_to_lead_task(conn, session_id)
    session = get_session(conn, session_id) or session
    _sync_common_intake_to_lead(conn, session)
    _log_intake_activity(conn, session, actor_id=actor_id)

    try:
        from crm_svc_consult_bridge import on_intake_completed

        on_intake_completed(conn, session_id, actor_id=actor_id)
    except Exception:
        pass

    lifecycle_id = session.get("lifecycle_id")
    if lifecycle_id:
        try:
            from crm_svc_lead_sync import sync_lead_from_lifecycle_stage
            sync_lead_from_lifecycle_stage(conn, int(lifecycle_id), "lead")
        except Exception:
            pass

    conn.commit()
    return get_session(conn, session_id)


def reopen_session(conn: sqlite3.Connection, session_id: int) -> dict[str, Any] | None:
    """Cho phép chỉnh sửa lại session đã complete."""
    ts = _ts()
    conn.execute(
        """
        UPDATE crm_lead_intake_sessions
        SET status = 'draft', completed_at = '', updated_at = ?
        WHERE id = ?
        """,
        (ts, session_id),
    )
    conn.commit()
    return get_session(conn, session_id)


def _anthropic_client():
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=key)
    except Exception as exc:
        logger.warning("Anthropic client init failed: %s", exc)
        return None


def _strip_html(text: str) -> str:
    return (
        str(text or "")
        .replace("<", " ")
        .replace(">", " ")
        .replace("&nbsp;", " ")
        .strip()
    )


def _answers_excerpt(session: dict[str, Any], *, limit: int = 3500) -> str:
    answers = session.get("answers_json") or {}
    lines: list[str] = []
    if isinstance(answers.get("meta"), dict):
        meta = answers["meta"]
        for key in ("pain_summary", "recap"):
            val = _strip_html(str(meta.get(key) or ""))
            if val:
                lines.append(f"{key}: {val[:400]}")
    for section in ("phone", "inperson"):
        block = answers.get(section)
        if not isinstance(block, dict):
            continue
        for qkey in sorted(
            block.keys(),
            key=lambda k: int(k[1:]) if k.startswith("p") and k[1:].isdigit() else 999,
        ):
            val = _strip_html(str(block.get(qkey) or ""))
            if val:
                lines.append(f"{section}.{qkey}: {val[:280]}")
            if sum(len(x) for x in lines) > limit:
                break
    crm = answers.get("crm_fields")
    if isinstance(crm, dict):
        for k, v in crm.items():
            val = str(v or "").strip()
            if val:
                lines.append(f"crm.{k}: {val[:200]}")
    text = "\n".join(lines)
    return text[:limit]


def generate_intake_summary(session: dict[str, Any]) -> dict[str, Any] | None:
    """Gọi Claude Haiku — trả dict summary/risks/missing_questions/recommended_next_step."""
    client = _anthropic_client()
    if client is None:
        return None

    from crm_svc_tasks import SERVICE_LABELS
    from crm_svc_workflow_steps import AI_PROMPT_TEMPLATES

    slug = str(session.get("service_slug") or "")
    service_name = SERVICE_LABELS.get(slug, slug or "Dịch vụ PTT")
    mode = session.get("mode") or "phone"
    mode_label = "gọi điện (PHẦN A)" if mode == "phone" else "gặp trực tiếp (PHẦN B)"
    answers = session.get("answers_json") or {}
    red_flags = answers.get("red_flags") if isinstance(answers.get("red_flags"), list) else []
    urgency = answers.get("urgency") if isinstance(answers.get("urgency"), list) else []

    template = AI_PROMPT_TEMPLATES.get("intake_summary", "")
    prompt = template.format(
        mode_label=mode_label,
        service_name=service_name,
        contact_name=str(session.get("contact_name") or "—")[:200],
        company_name=str(session.get("company_name") or "—")[:200],
        bant_total=session.get("bant_total") or 0,
        bant_json=json.dumps(session.get("bant_json") or {}, ensure_ascii=False),
        lead_temperature=str(session.get("lead_temperature") or "—"),
        decision=str(session.get("decision") or "—"),
        decision_reason=_strip_html(str(session.get("decision_reason") or ""))[:1500],
        red_flags=", ".join(str(x) for x in red_flags[:12]) or "—",
        urgency=", ".join(str(x) for x in urgency[:12]) or "—",
        answers_excerpt=_answers_excerpt(session),
    )

    try:
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=900,
            system="Bạn là AM PTT. Chỉ trả về JSON hợp lệ, không giải thích thêm.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        summary = str(data.get("summary") or "").strip()
        if not summary:
            return None
        risks = data.get("risks") if isinstance(data.get("risks"), list) else []
        missing = (
            data.get("missing_questions")
            if isinstance(data.get("missing_questions"), list)
            else []
        )
        next_step = str(data.get("recommended_next_step") or "").strip()
        questions = [str(q).strip() for q in missing if str(q).strip()]
        if next_step:
            questions.append(f"Bước tiếp: {next_step}")
        return {
            "summary": summary[:4000],
            "risks": [str(r)[:500] for r in risks[:8]],
            "missing_questions": questions[:10],
            "recommended_next_step": next_step[:1000],
            "generated_at": _ts(),
            "model": _HAIKU,
        }
    except json.JSONDecodeError as exc:
        logger.warning("intake summary JSON parse error: %s", exc)
        return None
    except Exception as exc:
        logger.warning("intake summary API error: %s", exc)
        return None


def save_intake_ai_result(
    conn: sqlite3.Connection,
    session_id: int,
    result: dict[str, Any],
) -> dict[str, Any] | None:
    ts = _ts()
    questions = result.get("missing_questions") or []
    risks = result.get("risks") or []
    summary = str(result.get("summary") or "").strip()
    if risks:
        risk_block = "Rủi ro: " + "; ".join(str(r) for r in risks[:5])
        summary = f"{summary}\n\n{risk_block}"[:4000]
    conn.execute(
        """
        UPDATE crm_lead_intake_sessions
        SET ai_summary = ?, ai_suggested_questions = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            summary,
            json.dumps(questions, ensure_ascii=False),
            ts,
            session_id,
        ),
    )
    conn.commit()
    return get_session(conn, session_id)


def trigger_intake_summary_async(session_id: int, *, db_path: str) -> None:
    """Chạy AI summary nền sau khi complete intake."""

    def _run() -> None:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            ensure_schema(conn)
            session = get_session(conn, session_id)
            if session is None:
                return
            result = generate_intake_summary(session)
            if result is None:
                return
            save_intake_ai_result(conn, session_id, result)
            logger.info("Intake AI summary saved: session_id=%s", session_id)
            conn.close()
        except Exception as exc:
            logger.warning("Intake AI summary failed: %s", exc)

    t = threading.Thread(
        target=_run,
        daemon=True,
        name=f"intake-ai-{session_id}",
    )
    t.start()


def _intake_presales_on_lead_enabled(conn: sqlite3.Connection) -> bool:
    try:
        from crm_lead_presales import presales_on_lead_enabled
    except ImportError:
        return False
    if not presales_on_lead_enabled():
        return False
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='crm_lead_presales'"
    ).fetchone()
    return row is not None


def _build_intake_stats_result(
    *,
    total_subjects: int,
    with_completed_intake: int,
    completed_sessions: int,
    avg_bant_by_slug: list[dict[str, Any]],
    subject_label: str = "lifecycle",
) -> dict[str, Any]:
    pct = (
        round(with_completed_intake / total_subjects * 100, 1)
        if total_subjects
        else 0.0
    )
    return {
        "total_lifecycles": total_subjects,
        "lifecycles_with_completed_intake": with_completed_intake,
        "completed_intake_sessions": completed_sessions,
        "intake_coverage_pct": pct,
        "avg_bant_by_slug": avg_bant_by_slug,
        "subject_label": subject_label,
    }


def _get_lifecycle_intake_stats(
    conn: sqlite3.Connection,
    *,
    am_id: int | None = None,
    exclude_presales_leads: bool = False,
) -> dict[str, Any]:
    lc_filter = "status IN ('active', 'draft')"
    lc_params: list[Any] = []
    if am_id is not None:
        lc_filter += " AND assigned_am = ?"
        lc_params.append(int(am_id))
    if exclude_presales_leads:
        lc_filter += """
            AND (
                crm_service_lifecycle.lead_id IS NULL
                OR NOT EXISTS (
                    SELECT 1 FROM crm_lead_presales ps_ex
                    WHERE ps_ex.lead_id = crm_service_lifecycle.lead_id
                )
            )
        """

    total_row = conn.execute(
        f"SELECT COUNT(*) AS n FROM crm_service_lifecycle WHERE {lc_filter}",
        lc_params,
    ).fetchone()
    total_lifecycles = int(total_row["n"] or 0) if total_row else 0

    intake_lc_filter = lc_filter.replace("status IN", "lc.status IN").replace(
        "crm_service_lifecycle.lead_id", "lc.lead_id"
    )
    with_intake_row = conn.execute(
        f"""
        SELECT COUNT(DISTINCT s.lifecycle_id) AS n
        FROM crm_lead_intake_sessions s
        INNER JOIN crm_service_lifecycle lc ON lc.id = s.lifecycle_id
        WHERE s.status = 'completed' AND s.lifecycle_id IS NOT NULL
          AND {intake_lc_filter}
        """,
        lc_params,
    ).fetchone()
    with_completed_intake = int(with_intake_row["n"] or 0) if with_intake_row else 0

    session_filter = "status = 'completed' AND lifecycle_id IS NOT NULL"
    session_params: list[Any] = []
    if am_id is not None:
        session_filter += (
            " AND lifecycle_id IN ("
            "SELECT id FROM crm_service_lifecycle WHERE assigned_am = ?"
            " AND status IN ('active', 'draft'))"
        )
        session_params.append(int(am_id))
    if exclude_presales_leads:
        session_filter += """
            AND lifecycle_id IN (
                SELECT id FROM crm_service_lifecycle
                WHERE status IN ('active', 'draft')
                  AND (
                    lead_id IS NULL
                    OR NOT EXISTS (
                        SELECT 1 FROM crm_lead_presales ps_ex
                        WHERE ps_ex.lead_id = crm_service_lifecycle.lead_id
                    )
                  )
            )
        """

    completed_sessions = conn.execute(
        f"SELECT COUNT(*) AS n FROM crm_lead_intake_sessions WHERE {session_filter}",
        session_params,
    ).fetchone()
    completed_count = int(completed_sessions["n"] or 0) if completed_sessions else 0

    slug_filter = session_filter + " AND service_slug != ''"
    by_slug_rows = conn.execute(
        f"""
        SELECT service_slug,
               ROUND(AVG(bant_total), 1) AS avg_bant,
               COUNT(*) AS session_count
        FROM crm_lead_intake_sessions
        WHERE {slug_filter}
        GROUP BY service_slug
        ORDER BY session_count DESC, service_slug
        """,
        session_params,
    ).fetchall()

    from crm_svc_tasks import SERVICE_LABELS

    by_slug = [
        {
            "service_slug": str(r["service_slug"]),
            "service_name": SERVICE_LABELS.get(
                str(r["service_slug"]), str(r["service_slug"])
            ),
            "avg_bant_total": float(r["avg_bant"] or 0),
            "session_count": int(r["session_count"] or 0),
        }
        for r in by_slug_rows
    ]
    return _build_intake_stats_result(
        total_subjects=total_lifecycles,
        with_completed_intake=with_completed_intake,
        completed_sessions=completed_count,
        avg_bant_by_slug=by_slug,
        subject_label="lifecycle",
    )


def _get_presales_intake_stats(
    conn: sqlite3.Connection,
    *,
    am_id: int | None = None,
) -> dict[str, Any]:
    where = ["ps.status IN ('active', 'converted')"]
    params: list[Any] = []
    if am_id is not None:
        where.append("COALESCE(ps.assigned_am, l.owner_id) = ?")
        params.append(int(am_id))

    total_row = conn.execute(
        f"""
        SELECT COUNT(*) AS n
        FROM crm_lead_presales ps
        INNER JOIN crm_leads l ON l.id = ps.lead_id
        WHERE {' AND '.join(where)}
        """,
        params,
    ).fetchone()
    total_presales = int(total_row["n"] or 0) if total_row else 0

    with_intake_row = conn.execute(
        f"""
        SELECT COUNT(DISTINCT ps.id) AS n
        FROM crm_lead_presales ps
        INNER JOIN crm_leads l ON l.id = ps.lead_id
        WHERE {' AND '.join(where)}
          AND EXISTS (
            SELECT 1 FROM crm_lead_intake_sessions s
            WHERE s.status = 'completed'
              AND s.lead_id = ps.lead_id
          )
        """,
        params,
    ).fetchone()
    with_completed_intake = int(with_intake_row["n"] or 0) if with_intake_row else 0

    session_where = ["s.status = 'completed'", "s.lead_id IS NOT NULL"]
    session_params: list[Any] = []
    if am_id is not None:
        session_where.append(
            """
            s.lead_id IN (
                SELECT ps.lead_id FROM crm_lead_presales ps
                INNER JOIN crm_leads l ON l.id = ps.lead_id
                WHERE ps.status IN ('active', 'converted')
                  AND COALESCE(ps.assigned_am, l.owner_id) = ?
            )
            """
        )
        session_params.append(int(am_id))
    session_filter = " AND ".join(session_where)

    completed_sessions = conn.execute(
        f"SELECT COUNT(*) AS n FROM crm_lead_intake_sessions s WHERE {session_filter}",
        session_params,
    ).fetchone()
    completed_count = int(completed_sessions["n"] or 0) if completed_sessions else 0

    slug_filter = session_filter + " AND s.service_slug != ''"
    by_slug_rows = conn.execute(
        f"""
        SELECT s.service_slug,
               ROUND(AVG(s.bant_total), 1) AS avg_bant,
               COUNT(*) AS session_count
        FROM crm_lead_intake_sessions s
        WHERE {slug_filter}
        GROUP BY s.service_slug
        ORDER BY session_count DESC, s.service_slug
        """,
        session_params,
    ).fetchall()

    from crm_svc_tasks import SERVICE_LABELS

    by_slug = [
        {
            "service_slug": str(r["service_slug"]),
            "service_name": SERVICE_LABELS.get(
                str(r["service_slug"]), str(r["service_slug"])
            ),
            "avg_bant_total": float(r["avg_bant"] or 0),
            "session_count": int(r["session_count"] or 0),
        }
        for r in by_slug_rows
    ]
    stats = _build_intake_stats_result(
        total_subjects=total_presales,
        with_completed_intake=with_completed_intake,
        completed_sessions=completed_count,
        avg_bant_by_slug=by_slug,
        subject_label="presales",
    )
    stats["total_presales"] = total_presales
    stats["presales_with_completed_intake"] = with_completed_intake
    return stats


def _merge_bant_by_slug(
    *groups: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for row in group:
            slug = str(row.get("service_slug") or "")
            if not slug:
                continue
            prev = merged.get(slug)
            if prev is None:
                merged[slug] = {
                    "service_slug": slug,
                    "service_name": row.get("service_name", slug),
                    "avg_bant_total": float(row.get("avg_bant_total") or 0),
                    "session_count": int(row.get("session_count") or 0),
                }
                continue
            prev_count = int(prev["session_count"])
            row_count = int(row.get("session_count") or 0)
            total_count = prev_count + row_count
            if total_count > 0:
                prev["avg_bant_total"] = round(
                    (
                        float(prev["avg_bant_total"]) * prev_count
                        + float(row.get("avg_bant_total") or 0) * row_count
                    )
                    / total_count,
                    1,
                )
            prev["session_count"] = total_count
    return sorted(
        merged.values(),
        key=lambda x: (-int(x["session_count"]), str(x["service_slug"])),
    )


def get_intake_stats(
    conn: sqlite3.Connection,
    *,
    am_id: int | None = None,
    by_am: bool = False,
) -> dict[str, Any]:
    """KPI intake: coverage + BANT TB; dual path khi PTT_PRESALES_ON_LEAD=1."""
    if _intake_presales_on_lead_enabled(conn):
        lifecycle = _get_lifecycle_intake_stats(
            conn, am_id=am_id, exclude_presales_leads=True
        )
        presales = _get_presales_intake_stats(conn, am_id=am_id)
        total_subjects = int(lifecycle["total_lifecycles"]) + int(
            presales["total_presales"]
        )
        with_intake = int(lifecycle["lifecycles_with_completed_intake"]) + int(
            presales["presales_with_completed_intake"]
        )
        combined_sessions = int(lifecycle["completed_intake_sessions"]) + int(
            presales["completed_intake_sessions"]
        )
        combined_pct = (
            round(with_intake / total_subjects * 100, 1) if total_subjects else 0.0
        )
        result: dict[str, Any] = {
            **presales,
            "dual_intake": True,
            "cohort_mode": "dual",
            "total_lifecycles": total_subjects,
            "lifecycles_with_completed_intake": with_intake,
            "completed_intake_sessions": combined_sessions,
            "intake_coverage_pct": combined_pct,
            "avg_bant_by_slug": _merge_bant_by_slug(
                lifecycle["avg_bant_by_slug"],
                presales["avg_bant_by_slug"],
            ),
            "presales_on_lead": presales,
            "lifecycle": lifecycle,
        }
    else:
        result = _get_lifecycle_intake_stats(conn, am_id=am_id)

    if am_id is not None:
        result["am_id"] = int(am_id)

    if by_am:
        if _intake_presales_on_lead_enabled(conn):
            by_am_rows = conn.execute(
                """
                SELECT staff_id, name,
                       SUM(lifecycle_count) AS lifecycle_count,
                       SUM(intake_completed) AS intake_completed,
                       ROUND(AVG(avg_bant), 1) AS avg_bant
                FROM (
                    SELECT lc.assigned_am AS staff_id,
                           st.name AS name,
                           COUNT(DISTINCT lc.id) AS lifecycle_count,
                           COUNT(DISTINCT CASE
                               WHEN s.status = 'completed' THEN lc.id
                           END) AS intake_completed,
                           AVG(CASE
                               WHEN s.status = 'completed' THEN s.bant_total
                           END) AS avg_bant
                    FROM crm_service_lifecycle lc
                    INNER JOIN crm_staff st ON st.id = lc.assigned_am
                    LEFT JOIN crm_lead_intake_sessions s
                        ON s.lifecycle_id = lc.id AND s.status = 'completed'
                    WHERE lc.status IN ('active', 'draft')
                      AND lc.assigned_am IS NOT NULL
                      AND (
                        lc.lead_id IS NULL
                        OR NOT EXISTS (
                            SELECT 1 FROM crm_lead_presales ps_ex
                            WHERE ps_ex.lead_id = lc.lead_id
                        )
                      )
                    GROUP BY lc.assigned_am, st.name
                    UNION ALL
                    SELECT COALESCE(ps.assigned_am, l.owner_id) AS staff_id,
                           st.name AS name,
                           COUNT(DISTINCT ps.id) AS lifecycle_count,
                           COUNT(DISTINCT CASE
                               WHEN s.status = 'completed' THEN ps.id
                           END) AS intake_completed,
                           AVG(CASE
                               WHEN s.status = 'completed' THEN s.bant_total
                           END) AS avg_bant
                    FROM crm_lead_presales ps
                    INNER JOIN crm_leads l ON l.id = ps.lead_id
                    INNER JOIN crm_staff st ON st.id = COALESCE(ps.assigned_am, l.owner_id)
                    LEFT JOIN crm_lead_intake_sessions s
                        ON s.lead_id = ps.lead_id AND s.status = 'completed'
                    WHERE ps.status IN ('active', 'converted')
                    GROUP BY COALESCE(ps.assigned_am, l.owner_id), st.name
                )
                GROUP BY staff_id, name
                ORDER BY intake_completed DESC, name
                """
            ).fetchall()
        else:
            by_am_rows = conn.execute(
                """
                SELECT lc.assigned_am AS staff_id,
                       st.name AS name,
                       COUNT(DISTINCT lc.id) AS lifecycle_count,
                       COUNT(DISTINCT CASE
                           WHEN s.status = 'completed' THEN lc.id
                       END) AS intake_completed,
                       ROUND(AVG(CASE
                           WHEN s.status = 'completed' THEN s.bant_total
                       END), 1) AS avg_bant
                FROM crm_service_lifecycle lc
                INNER JOIN crm_staff st ON st.id = lc.assigned_am
                LEFT JOIN crm_lead_intake_sessions s
                    ON s.lifecycle_id = lc.id AND s.status = 'completed'
                WHERE lc.status IN ('active', 'draft')
                  AND lc.assigned_am IS NOT NULL
                GROUP BY lc.assigned_am, st.name
                ORDER BY intake_completed DESC, st.name
                """
            ).fetchall()
        result["by_am"] = [
            {
                "staff_id": int(r["staff_id"]),
                "name": str(r["name"] or ""),
                "lifecycle_count": int(r["lifecycle_count"] or 0),
                "intake_completed": int(r["intake_completed"] or 0),
                "avg_bant": float(r["avg_bant"] or 0),
            }
            for r in by_am_rows
        ]

    return result
