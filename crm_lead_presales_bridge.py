"""Adapter Consult Brief / gate / prefill cho pre-sales trên Lead (không lifecycle)."""
from __future__ import annotations

import sqlite3
from typing import Any

from crm_lead_intake import list_sessions
from crm_lead_intake_definitions import GO_THRESHOLDS
from crm_lead_presales import (
    get_by_lead,
    is_presales_stage_complete,
    list_presales_tasks,
    update_presales_task,
)
from crm_svc_consult_bridge import (
    DECISION_LABELS,
    TEMPERATURE_LABELS,
    _append_note_lines,
    _build_highlights,
    _build_latest_intake_summary,
    _build_recommended_actions,
    _collect_source_values,
    _consult_gate_level,
    _extract_intake_keyword_hints,
    _extract_red_flags,
    _field_empty,
    _format_mapped_value,
    _has_completed_mode,
    _latest_completed,
    get_lead_to_consult_field_map,
)


def _load_presales_task(
    conn: sqlite3.Connection, presales_id: int, stage: str
) -> dict[str, Any] | None:
    tasks = list_presales_tasks(conn, presales_id).get(stage) or []
    if not tasks:
        return None
    task = tasks[0]
    return {
        "task_id": int(task["id"]),
        "form_data": task.get("form_data") or {},
        "notes": str(task.get("notes") or ""),
        "is_done": bool(task.get("is_done")),
    }


def get_presales_brief(conn: sqlite3.Connection, lead_id: int) -> dict[str, Any] | None:
    ps = get_by_lead(conn, int(lead_id))
    if ps is None:
        return None

    presales_id = int(ps["id"])
    slug = str(ps.get("service_slug") or "")
    lead_task = _load_presales_task(conn, presales_id, "lead")

    raw_sessions = list_sessions(conn, lead_id=int(lead_id), limit=20)
    intake_sessions: list[dict[str, Any]] = []
    for s in raw_sessions:
        intake_sessions.append({
            "id": int(s["id"]),
            "mode": str(s.get("mode") or ""),
            "status": str(s.get("status") or ""),
            "bant_total": int(s.get("bant_total") or 0),
            "decision": str(s.get("decision") or ""),
            "decision_reason": str(s.get("decision_reason") or ""),
            "ai_summary": str(s.get("ai_summary") or ""),
            "next_meeting_at": str(s.get("next_meeting_at") or ""),
            "proposal_date": str(s.get("proposal_date") or ""),
            "completed_at": str(s.get("completed_at") or ""),
            "lead_temperature": str(s.get("lead_temperature") or ""),
        })

    latest_raw = _latest_completed(list(raw_sessions))
    latest_public = None
    stakeholders: list[Any] = []
    commitments: list[Any] = []
    red_flags: list[str] = []

    if latest_raw:
        latest_public = next(
            (s for s in intake_sessions if s["id"] == int(latest_raw["id"])),
            intake_sessions[0] if intake_sessions else None,
        )
        stakeholders = latest_raw.get("stakeholders_json") or []
        if not isinstance(stakeholders, list):
            stakeholders = []
        commitments = latest_raw.get("commitments_json") or []
        if not isinstance(commitments, list):
            commitments = []
        red_flags = _extract_red_flags(latest_raw)

    decision = str((latest_public or {}).get("decision") or "")
    bant_total = int((latest_public or {}).get("bant_total") or 0)
    lead_task_done = is_presales_stage_complete(conn, presales_id, "lead")
    gate_level = _consult_gate_level(decision, bant_total)

    from crm_svc_tasks import SERVICE_LABELS

    readiness = {
        "lead_task_done": lead_task_done,
        "has_any_intake": any(s.get("status") == "completed" for s in intake_sessions),
        "has_intake_phone": _has_completed_mode(intake_sessions, "phone"),
        "has_intake_in_person": _has_completed_mode(intake_sessions, "in_person"),
        "decision": decision,
        "decision_label": DECISION_LABELS.get(decision, decision or "—"),
        "bant_total": bant_total,
        "lead_temperature": str((latest_public or {}).get("lead_temperature") or ""),
        "temperature_label": TEMPERATURE_LABELS.get(
            str((latest_public or {}).get("lead_temperature") or ""), "—"
        ),
        "can_advance_from_lead": lead_task_done and decision == "go",
        "consult_gate_level": gate_level,
    }

    brief: dict[str, Any] = {
        "presales_id": presales_id,
        "lead_id": int(lead_id),
        "service_slug": slug,
        "service_label": SERVICE_LABELS.get(slug, slug),
        "presales_stage": str(ps.get("stage") or "lead"),
        "readiness": readiness,
        "highlights": _build_highlights(lead_task, latest_raw),
        "lead_task": lead_task,
        "intake_sessions": intake_sessions,
        "stakeholders": stakeholders,
        "commitments": commitments,
        "red_flags": red_flags,
        "recommended_actions": [],
        "latest_intake_summary": _build_latest_intake_summary(latest_raw),
    }
    brief["recommended_actions"] = _build_recommended_actions(brief)
    return brief


def validate_presales_consult_advance(
    conn: sqlite3.Connection,
    presales_id: int,
    *,
    override_reason: str = "",
    allow_override: bool = False,
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT lead_id FROM crm_lead_presales WHERE id = ?", (int(presales_id),)
    ).fetchone()
    if row is None:
        return {
            "ok": False,
            "level": "block",
            "messages": ["Không tìm thấy pre-sales"],
            "requires_confirm": False,
            "requires_override": False,
        }
    brief = get_presales_brief(conn, int(row["lead_id"]))
    if brief is None:
        return {
            "ok": False,
            "level": "block",
            "messages": ["Không tìm thấy brief"],
            "requires_confirm": False,
            "requires_override": False,
        }

    readiness = brief.get("readiness") or {}
    decision = str(readiness.get("decision") or "")
    bant_total = int(readiness.get("bant_total") or 0)
    messages: list[str] = []

    if not readiness.get("lead_task_done"):
        messages.append("Hoàn thành task Lead trước khi chuyển Tư vấn")
        return {
            "ok": False,
            "level": "block",
            "messages": messages,
            "decision": decision,
            "bant_total": bant_total,
            "requires_confirm": False,
            "requires_override": False,
        }

    if not readiness.get("has_any_intake"):
        messages.append("Hoàn thành Lead Intake trước khi chuyển Tư vấn")
        return {
            "ok": False,
            "level": "block",
            "messages": messages,
            "decision": decision,
            "bant_total": bant_total,
            "requires_confirm": False,
            "requires_override": False,
        }

    if decision == "no_go":
        reason = str(override_reason or "").strip()
        if not reason:
            messages.append("Intake No-Go — không chuyển Consult (Director override + lý do)")
            return {
                "ok": False,
                "level": "block",
                "messages": messages,
                "decision": decision,
                "bant_total": bant_total,
                "requires_confirm": False,
                "requires_override": True,
            }
        if not allow_override:
            messages.append("Cần quyền Director để override No-Go → Consult")
            return {
                "ok": False,
                "level": "block",
                "messages": messages,
                "decision": decision,
                "bant_total": bant_total,
                "requires_confirm": False,
                "requires_override": True,
            }
        messages.append(f"Director override No-Go: {reason[:500]}")
        return {
            "ok": True,
            "level": "warn",
            "messages": messages,
            "decision": decision,
            "bant_total": bant_total,
            "requires_confirm": True,
            "requires_override": True,
        }

    if decision == "nurture":
        messages.append("Nurture — cân nhắc trước khi chuyển Consult sâu")
        return {
            "ok": True,
            "level": "warn",
            "messages": messages,
            "decision": decision,
            "bant_total": bant_total,
            "requires_confirm": True,
            "requires_override": False,
        }

    if decision == "go" and bant_total < GO_THRESHOLDS["nurture_min"]:
        messages.append(
            f"BANT {bant_total}/30 — dưới ngưỡng Nurture ({GO_THRESHOLDS['nurture_min']})"
        )
        return {
            "ok": True,
            "level": "warn",
            "messages": messages,
            "decision": decision,
            "bant_total": bant_total,
            "requires_confirm": True,
            "requires_override": False,
        }

    if decision == "go" and bant_total < GO_THRESHOLDS["go"]:
        messages.append(
            f"BANT {bant_total}/30 — dưới ngưỡng Go ({GO_THRESHOLDS['go']})"
        )
        return {
            "ok": True,
            "level": "warn",
            "messages": messages,
            "decision": decision,
            "bant_total": bant_total,
            "requires_confirm": True,
            "requires_override": False,
        }

    messages.append("Sẵn sàng chuyển Tư vấn")
    return {
        "ok": True,
        "level": "ok",
        "messages": messages,
        "decision": decision,
        "bant_total": bant_total,
        "requires_confirm": False,
        "requires_override": False,
    }


def prefill_presales_consult_task(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    ps = get_by_lead(conn, int(lead_id))
    if ps is None:
        raise ValueError("Chưa có pre-sales")

    presales_id = int(ps["id"])
    slug = str(ps.get("service_slug") or "")
    field_map = get_lead_to_consult_field_map(slug)

    lead_task = _load_presales_task(conn, presales_id, "lead")
    consult_task = _load_presales_task(conn, presales_id, "consult")
    if consult_task is None:
        raise ValueError("Chưa có task Consult")

    sessions = list_sessions(conn, lead_id=int(lead_id), limit=10)
    latest = _latest_completed(sessions)
    sources = _collect_source_values(
        (lead_task or {}).get("form_data") or {},
        latest,
    )

    form_data = dict(consult_task["form_data"])
    filled: list[str] = []
    skipped: list[str] = []

    for source_key, target_key in field_map.items():
        new_val = _format_mapped_value(
            source_key, sources.get(source_key), target_key
        )
        if _field_empty(new_val):
            continue
        existing = form_data.get(target_key)
        if not _field_empty(existing) and not overwrite:
            skipped.append(target_key)
            continue
        form_data[target_key] = new_val
        filled.append(target_key)

    pain = sources.get("_pain_summary") or sources.get("need")
    if pain and (_field_empty(form_data.get("current_status")) or overwrite):
        merged = _format_mapped_value("need", pain, "current_status")
        if merged:
            form_data["current_status"] = merged
            filled.append("current_status")

    kw_hints = _extract_intake_keyword_hints(latest)
    if kw_hints and (_field_empty(form_data.get("local_keywords")) or overwrite):
        form_data["local_keywords"] = kw_hints[:4000]
        filled.append("local_keywords")

    note_lines: list[str] = []
    if latest and latest.get("decision"):
        note_lines.append(
            f"Intake #{latest.get('id')}: {latest.get('decision')} "
            f"BANT {latest.get('bant_total')}/30"
        )

    notes = _append_note_lines(consult_task["notes"], note_lines)
    update_presales_task(
        conn,
        int(consult_task["task_id"]),
        form_data=form_data,
        notes=notes if notes != consult_task["notes"] else None,
    )
    return {
        "task_id": int(consult_task["task_id"]),
        "filled": len(set(filled)),
        "fields": sorted(set(filled)),
        "skipped_existing": sorted(set(skipped)),
    }
