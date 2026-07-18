"""Consult stage bridge — aggregate Lead output for Consult Brief (C1+)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from crm_lead_intake import build_recap_from_session, get_session, list_sessions
from crm_lead_intake_definitions import GO_THRESHOLDS
from crm_svc_tasks import SERVICE_LABELS, is_stage_complete, list_tasks, update_task

DECISION_LABELS: dict[str, str] = {
    "go": "GO",
    "nurture": "Nurture",
    "no_go": "No-Go",
    "": "—",
}

TEMPERATURE_LABELS: dict[str, str] = {
    "hot": "Hot",
    "warm": "Warm",
    "cold": "Cold",
    "": "—",
}

_SEO_SLUGS: frozenset[str] = frozenset({
    "dich-vu-seo-tong-the",
    "dich-vu-seo-local",
    "dich-vu-aeo",
    "dich-vu-seo-audit",
})


def _load_lead_task(conn: sqlite3.Connection, lifecycle_id: int) -> dict[str, Any] | None:
    tasks_by_stage = list_tasks(conn, int(lifecycle_id))
    lead_tasks = tasks_by_stage.get("lead") or []
    if not lead_tasks:
        return None
    task = lead_tasks[0]
    return {
        "task_id": int(task["id"]),
        "form_data": task.get("form_data") or {},
        "notes": str(task.get("notes") or ""),
        "is_done": bool(task.get("is_done")),
    }


def _load_intake_sessions(conn: sqlite3.Connection, lifecycle_id: int) -> list[dict[str, Any]]:
    sessions = list_sessions(conn, lifecycle_id=int(lifecycle_id), limit=20)
    out: list[dict[str, Any]] = []
    for s in sessions:
        out.append({
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
    return out


def _latest_completed(sessions: list[dict[str, Any]]) -> dict[str, Any] | None:
    completed = [s for s in sessions if s.get("status") == "completed"]
    if not completed:
        return None
    return max(
        completed,
        key=lambda s: (str(s.get("completed_at") or ""), int(s.get("id") or 0)),
    )


def _has_completed_mode(sessions: list[dict[str, Any]], mode: str) -> bool:
    return any(
        s.get("status") == "completed" and s.get("mode") == mode for s in sessions
    )


def _consult_gate_level(decision: str, bant_total: int) -> str:
    """Gate hiển thị Brief — dùng GO_THRESHOLDS (24/18) đến Director sign-off chính thức."""
    if decision == "no_go":
        return "block"
    if decision == "nurture":
        return "warn"
    if decision == "go":
        if bant_total >= GO_THRESHOLDS["go"]:
            return "ok"
        if bant_total >= GO_THRESHOLDS["nurture_min"]:
            return "warn"
        return "warn"
    return "warn"


def _extract_red_flags(session: dict[str, Any] | None) -> list[str]:
    if session is None:
        return []
    answers = session.get("answers_json") or {}
    flags = answers.get("red_flags")
    if not isinstance(flags, list):
        return []
    return [str(x).strip() for x in flags if str(x).strip()]


def _build_highlights(
    lead_task: dict[str, Any] | None,
    latest: dict[str, Any] | None,
) -> dict[str, Any]:
    form = (lead_task or {}).get("form_data") or {}
    pain = str(form.get("need") or "").strip()
    if not pain and latest:
        answers = latest.get("_answers") or {}
        meta = answers.get("meta") if isinstance(answers.get("meta"), dict) else {}
        pain = str(meta.get("pain_summary") or "").strip()
    budget = form.get("budget")
    try:
        budget_vnd = int(budget) if budget not in (None, "") else None
    except (TypeError, ValueError):
        budget_vnd = None
    return {
        "pain": pain,
        "budget_vnd": budget_vnd,
        "domain": str(form.get("domain") or "").strip(),
        "niche": str(form.get("niche") or form.get("industry") or "").strip(),
        "goal": str(form.get("goal") or form.get("campaign_goal") or "").strip(),
    }


def _build_latest_intake_summary(latest_raw: dict[str, Any] | None) -> str:
    if latest_raw is None:
        return ""
    if latest_raw.get("ai_summary"):
        return str(latest_raw["ai_summary"])[:4000]
    return build_recap_from_session(latest_raw)[:4000]


def _build_recommended_actions(brief: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    readiness = brief.get("readiness") or {}
    service_slug = str(brief.get("service_slug") or "")

    if not readiness.get("has_any_intake"):
        actions.append("Hoàn thành Lead Intake (gọi PHẦN A) trước khi audit Consult")
        return actions

    if not readiness.get("lead_task_done"):
        actions.append("Hoàn thành task Lead (tick ✓) trước khi audit Consult sâu")

    decision = str(readiness.get("decision") or "")
    if decision == "no_go":
        actions.append("Intake No-Go — không nên audit Consult sâu; cân nhắc đóng lifecycle")
        return actions
    if decision == "nurture":
        actions.append("Nurture — cân nhắc nurture thêm trước Consult sâu")

    if not readiness.get("has_intake_in_person"):
        actions.append("Hẹn gặp PHẦN B (in_person) trước audit Consult sâu")

    if service_slug in _SEO_SLUGS and decision == "go":
        actions.append("Thu GSC/GA4 read access trước buổi Consult")

    gate = str(readiness.get("consult_gate_level") or "")
    if gate == "warn" and decision == "go":
        actions.append(
            f"BANT {readiness.get('bant_total', 0)}/30 — cân nhắc bổ sung qualify trước báo giá"
        )

    if not actions and decision == "go":
        actions.append("Tiếp tục audit Consult — dùng task form + AI assist")

    return actions[:6]


def get_consult_brief(conn: sqlite3.Connection, lifecycle_id: int) -> dict[str, Any]:
    """Aggregate Lead task, intake sessions, readiness flags for Consult panel."""
    lc_row = conn.execute(
        "SELECT * FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if lc_row is None:
        raise ValueError(f"Không tìm thấy lifecycle #{lifecycle_id}")

    lc = dict(lc_row)
    slug = str(lc.get("service_slug") or "")
    lead_task = _load_lead_task(conn, int(lifecycle_id))
    raw_sessions = list_sessions(conn, lifecycle_id=int(lifecycle_id), limit=20)
    intake_sessions = _load_intake_sessions(conn, int(lifecycle_id))

    latest_raw = _latest_completed(raw_sessions)
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
    lead_task_done = is_stage_complete(conn, int(lifecycle_id), "lead")
    has_phone = _has_completed_mode(intake_sessions, "phone")
    has_in_person = _has_completed_mode(intake_sessions, "in_person")
    gate_level = _consult_gate_level(decision, bant_total)

    readiness = {
        "lead_task_done": lead_task_done,
        "has_any_intake": any(s.get("status") == "completed" for s in intake_sessions),
        "has_intake_phone": has_phone,
        "has_intake_in_person": has_in_person,
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

    highlights = _build_highlights(lead_task, latest_raw)
    latest_summary = _build_latest_intake_summary(latest_raw)

    brief: dict[str, Any] = {
        "lifecycle_id": int(lifecycle_id),
        "service_slug": slug,
        "service_label": SERVICE_LABELS.get(slug, slug),
        "lead_id": lc.get("lead_id"),
        "readiness": readiness,
        "highlights": highlights,
        "lead_task": lead_task,
        "intake_sessions": intake_sessions,
        "stakeholders": stakeholders,
        "commitments": commitments,
        "red_flags": red_flags,
        "recommended_actions": [],
        "latest_intake_summary": latest_summary,
    }
    brief["recommended_actions"] = _build_recommended_actions(brief)
    return brief


def get_lead_to_consult_field_map(service_slug: str) -> dict[str, str]:
    """Alias public — map Lead/Intake field → Consult field."""
    from crm_lead_intake_definitions import get_crm_field_map

    return get_crm_field_map(service_slug)


def _load_consult_task(conn: sqlite3.Connection, lifecycle_id: int) -> dict[str, Any] | None:
    tasks_by_stage = list_tasks(conn, int(lifecycle_id))
    consult_tasks = tasks_by_stage.get("consult") or []
    if not consult_tasks:
        return None
    task = consult_tasks[0]
    return {
        "task_id": int(task["id"]),
        "form_data": dict(task.get("form_data") or {}),
        "notes": str(task.get("notes") or ""),
    }


def _field_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _append_note_lines(existing: str, lines: list[str]) -> str:
    text = str(existing or "").strip()
    for line in lines:
        line = str(line).strip()
        if not line:
            continue
        if line in text:
            continue
        text = f"{text}\n{line}" if text else line
    return text[:4000]


def _collect_source_values(
    lead_form: dict[str, Any],
    intake_session: dict[str, Any] | None,
) -> dict[str, Any]:
    sources: dict[str, Any] = dict(lead_form or {})
    if intake_session:
        answers = intake_session.get("answers_json") or {}
        crm = answers.get("crm_fields") if isinstance(answers.get("crm_fields"), dict) else {}
        for key, val in crm.items():
            if not _field_empty(val) and _field_empty(sources.get(key)):
                sources[key] = val
        meta = answers.get("meta") if isinstance(answers.get("meta"), dict) else {}
        pain = str(meta.get("pain_summary") or "").strip()
        if pain and _field_empty(sources.get("need")):
            sources["_pain_summary"] = pain
    return sources


def _format_mapped_value(source_key: str, value: Any, target_key: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if source_key in ("need", "_pain_summary") and target_key == "current_status":
        if text.lower().startswith("pain:"):
            return text[:4000]
        return f"Pain: {text}"[:4000]
    if source_key == "domain" and target_key == "current_status":
        return f"Domain: {text}"[:4000]
    if source_key in ("platform", "urgency", "gbp_status", "has_ads_account", "has_google_ads"):
        label = source_key.replace("_", " ").title()
        return f"{label}: {text}"[:4000]
    return text[:4000]


def _extract_intake_keyword_hints(intake_session: dict[str, Any] | None) -> str:
    if intake_session is None:
        return ""
    answers = intake_session.get("answers_json") or {}
    phone = answers.get("phone") if isinstance(answers.get("phone"), dict) else {}
    snippets: list[str] = []
    for key in sorted(
        phone.keys(),
        key=lambda k: int(k[1:]) if str(k).startswith("p") and str(k)[1:].isdigit() else 999,
    ):
        val = str(phone.get(key) or "").strip()
        if not val:
            continue
        plain = val.replace("<", " ").replace(">", " ")
        if len(plain) > 160:
            plain = plain[:157] + "…"
        snippets.append(plain)
        if len(snippets) >= 6:
            break
    return "\n".join(snippets)[:4000]


def prefill_consult_task(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Fill empty consult form_data from Lead task + Intake. Returns stats."""
    from crm_lead_intake_definitions import get_crm_field_map
    from crm_svc_tasks import update_task

    lc_row = conn.execute(
        "SELECT service_slug FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if lc_row is None:
        raise ValueError(f"Không tìm thấy lifecycle #{lifecycle_id}")

    slug = str(lc_row[0] or "")
    consult_task = _load_consult_task(conn, int(lifecycle_id))
    if consult_task is None:
        return {"task_id": None, "filled": 0, "fields": [], "skipped_existing": []}

    lead_task = _load_lead_task(conn, int(lifecycle_id))
    lead_form = (lead_task or {}).get("form_data") or {}
    raw_sessions = list_sessions(conn, lifecycle_id=int(lifecycle_id), limit=20)
    latest_intake = _latest_completed(raw_sessions)

    sources = _collect_source_values(lead_form, latest_intake)
    field_map = get_crm_field_map(slug)
    form_data = dict(consult_task["form_data"])
    filled: list[str] = []
    skipped: list[str] = []

    def set_field(target_key: str, raw_value: Any, source_key: str = "") -> None:
        if _field_empty(raw_value):
            return
        new_val = (
            _format_mapped_value(source_key or target_key, raw_value, target_key)
            if source_key
            else str(raw_value).strip()[:4000]
        )
        if not new_val:
            return
        existing = form_data.get(target_key)
        if not overwrite and not _field_empty(existing):
            if target_key not in skipped:
                skipped.append(target_key)
            return
        if target_key == "current_status" and not _field_empty(existing) and overwrite:
            merged = f"{existing}\n{new_val}"[:4000]
            if merged != existing:
                form_data[target_key] = merged
                filled.append(target_key)
            return
        if str(existing or "") != new_val:
            form_data[target_key] = new_val
            filled.append(target_key)

    pain = sources.get("need") or sources.get("_pain_summary")
    if pain:
        set_field("current_status", pain, "need")

    for source_key, target_key in field_map.items():
        if source_key in ("need", "_pain_summary"):
            continue
        if source_key not in sources:
            continue
        set_field(target_key, sources[source_key], source_key)

    if slug in _SEO_SLUGS or slug == "quang-cao-google":
        kw_hint = _extract_intake_keyword_hints(latest_intake)
        if kw_hint:
            set_field("target_keywords", kw_hint)

    note_lines: list[str] = []
    niche = str(sources.get("niche") or "").strip()
    budget = sources.get("budget") or sources.get("monthly_budget") or sources.get("daily_budget")
    if niche:
        note_lines.append(f"Ngành: {niche}")
    if budget not in (None, ""):
        try:
            note_lines.append(f"NS: {int(budget):,} VND")
        except (TypeError, ValueError):
            note_lines.append(f"NS: {budget} VND")
    if latest_intake and latest_intake.get("decision"):
        note_lines.append(
            f"Intake #{latest_intake.get('id')}: {latest_intake.get('decision')} "
            f"BANT {latest_intake.get('bant_total')}/30"
        )

    notes = _append_note_lines(consult_task["notes"], note_lines)
    update_task(
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


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _append_lifecycle_note(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    line: str,
) -> bool:
    row = conn.execute(
        "SELECT notes FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if row is None:
        return False
    text = str(row[0] or "").strip()
    snippet = str(line or "").strip()
    if not snippet or snippet in text:
        return False
    merged = f"{text}\n{snippet}" if text else snippet
    conn.execute(
        """
        UPDATE crm_service_lifecycle
        SET notes = ?, updated_at = ?
        WHERE id = ?
        """,
        (merged[:4000], _ts(), int(lifecycle_id)),
    )
    return True


def _mark_lead_task_done(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    *,
    done_by: int | None = None,
) -> bool:
    lead_task = _load_lead_task(conn, int(lifecycle_id))
    if lead_task is None or lead_task.get("is_done"):
        return False
    update_task(conn, int(lead_task["task_id"]), is_done=True, done_by=done_by)
    return True


def validate_consult_advance(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    *,
    override_reason: str = "",
    allow_override: bool = False,
) -> dict[str, Any]:
    """Gate Lead→Consult theo Intake decision/BANT. Director override cho No-Go."""
    brief = get_consult_brief(conn, int(lifecycle_id))
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


def on_intake_completed(
    conn: sqlite3.Connection,
    session_id: int,
    *,
    actor_id: int | None = None,
) -> dict[str, Any]:
    """Side effects sau complete_session — auto ✓ Lead, ghi chú lifecycle."""
    session = get_session(conn, int(session_id))
    if session is None:
        return {"actions": []}

    actions: list[str] = []
    decision = str(session.get("decision") or "")
    mode = str(session.get("mode") or "")
    bant_total = int(session.get("bant_total") or 0)
    lifecycle_id = session.get("lifecycle_id")

    if (
        decision == "go"
        and mode == "in_person"
        and bant_total >= GO_THRESHOLDS["go"]
        and lifecycle_id
    ):
        if _mark_lead_task_done(conn, int(lifecycle_id), done_by=actor_id):
            actions.append("lead_task_auto_done")

    if decision == "go" and mode == "phone":
        actions.append("phone_go_schedule_part_b")

    if decision == "no_go" and lifecycle_id:
        if _append_lifecycle_note(
            conn,
            int(lifecycle_id),
            f"Intake #{session.get('id')} No-Go — cân nhắc đóng lifecycle",
        ):
            actions.append("no_go_lifecycle_note")

    return {
        "session_id": int(session_id),
        "lifecycle_id": lifecycle_id,
        "decision": decision,
        "mode": mode,
        "bant_total": bant_total,
        "actions": actions,
    }


def _safe_prompt_value(value: Any, *, limit: int = 3500) -> str:
    text = str(value or "").replace("{", "{{").replace("}", "}}")
    return text[:limit]


def build_ai_context_for_consult(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    task_id: int,
    form_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge Consult Brief + form fields từ UI cho run_ai_assist."""
    _ = task_id  # reserved — future per-task tweaks
    brief = get_consult_brief(conn, int(lifecycle_id))
    merged: dict[str, Any] = dict(form_context or {})
    lead_task = brief.get("lead_task") or {}
    lead_form = lead_task.get("form_data") or {}
    highlights = brief.get("highlights") or {}
    readiness = brief.get("readiness") or {}

    for key in ("niche", "budget", "need", "goal", "current_status"):
        if not str(merged.get(key) or "").strip():
            if lead_form.get(key) not in (None, ""):
                merged[key] = lead_form.get(key)
    if not str(merged.get("niche") or "").strip() and highlights.get("niche"):
        merged["niche"] = highlights["niche"]
    if not str(merged.get("budget") or "").strip() and highlights.get("budget_vnd"):
        merged["budget"] = highlights["budget_vnd"]
    if not str(merged.get("need") or "").strip() and highlights.get("pain"):
        merged["need"] = highlights["pain"]
    if not str(merged.get("current_status") or "").strip():
        parts = []
        if highlights.get("pain"):
            parts.append(str(highlights["pain"]))
        if highlights.get("domain"):
            parts.append(f"Domain: {highlights['domain']}")
        if parts:
            merged["current_status"] = " · ".join(parts)

    red_flags = brief.get("red_flags") or []
    merged["bant_total"] = int(readiness.get("bant_total") or 0)
    merged["decision"] = str(
        readiness.get("decision_label") or readiness.get("decision") or "—"
    )
    merged["intake_summary"] = _safe_prompt_value(
        brief.get("latest_intake_summary") or "", limit=2500
    )
    merged["lead_form_json"] = _safe_prompt_value(
        json.dumps(lead_form, ensure_ascii=False) if lead_form else "{}", limit=2500
    )
    merged["red_flags"] = _safe_prompt_value(
        ", ".join(str(x) for x in red_flags if str(x).strip()) or "—", limit=500
    )
    merged["consult_brief_json"] = _safe_prompt_value(
        json.dumps(
            {
                "readiness": {
                    "decision": readiness.get("decision"),
                    "bant_total": readiness.get("bant_total"),
                    "has_intake_in_person": readiness.get("has_intake_in_person"),
                    "consult_gate_level": readiness.get("consult_gate_level"),
                },
                "highlights": highlights,
            },
            ensure_ascii=False,
        ),
        limit=1500,
    )
    return merged


def _month_bounds_from_date(date_str: str) -> tuple[str, str]:
    text = str(date_str or "").strip()[:10]
    if len(text) < 10:
        now = datetime.utcnow()
        start = f"{now.year:04d}-{now.month:02d}-01"
        if now.month == 12:
            end = f"{now.year:04d}-12-31"
        else:
            next_month = datetime(now.year, now.month + 1, 1)
            end = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
        return start, end
    dt = datetime.strptime(text, "%Y-%m-%d")
    start = f"{dt.year:04d}-{dt.month:02d}-01"
    if dt.month == 12:
        end = f"{dt.year:04d}-12-31"
    else:
        next_month = datetime(dt.year, dt.month + 1, 1)
        end = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
    return start, end


def get_lifecycle_funnel_progress(
    conn: sqlite3.Connection,
    lifecycle_id: int,
) -> dict[str, Any]:
    """Tiến độ funnel Go→Consult→Proposal cho một lifecycle (C6)."""
    from crm_service_lifecycle import stage_index
    from crm_svc_presales import (
        _has_in_person_before_consult,
        _is_funnel_won,
        _latest_intake_decision,
        _stage_first_entered_at,
    )

    row = conn.execute(
        "SELECT * FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if row is None:
        raise ValueError(f"Không tìm thấy lifecycle #{lifecycle_id}")

    lc = dict(row)
    lid = int(lifecycle_id)
    has_intake = bool(
        conn.execute(
            """
            SELECT 1 FROM crm_lead_intake_sessions
            WHERE lifecycle_id = ? AND status = 'completed'
            LIMIT 1
            """,
            (lid,),
        ).fetchone()
    )
    decision = _latest_intake_decision(conn, lid)
    bant_row = conn.execute(
        """
        SELECT bant_total FROM crm_lead_intake_sessions
        WHERE lifecycle_id = ? AND status = 'completed'
        ORDER BY completed_at DESC, id DESC
        LIMIT 1
        """,
        (lid,),
    ).fetchone()
    bant_total = int(bant_row[0] or 0) if bant_row else 0

    current_stage = str(lc.get("stage") or "lead")
    stg_idx = stage_index(current_stage)
    consult_at = _stage_first_entered_at(conn, lid, "consult")
    proposal_at = _stage_first_entered_at(conn, lid, "proposal")

    days_to_proposal: float | None = None
    within_7d_proposal: bool | None = None
    if consult_at and proposal_at:
        days_to_proposal = round(
            (proposal_at - consult_at).total_seconds() / 86400.0, 1
        )
        within_7d_proposal = 0 <= days_to_proposal <= 7

    in_person_before_consult = False
    if decision == "go" and consult_at:
        in_person_before_consult = _has_in_person_before_consult(
            conn, lid, consult_at
        )

    period_start, period_end = _month_bounds_from_date(str(lc.get("created_at") or ""))
    query: list[str] = [f"from={period_start}", f"to={period_end}"]
    am_id = lc.get("assigned_am")
    slug = str(lc.get("service_slug") or "")
    if am_id:
        query.append(f"am_id={int(am_id)}")
    if slug:
        query.append(f"service_slug={slug}")
    dashboard_funnel_url = f"/crm/service-delivery?{'&'.join(query)}"

    milestones = [
        {
            "key": "intake",
            "label": "Intake",
            "done": has_intake,
        },
        {
            "key": "go",
            "label": "GO",
            "done": decision == "go",
        },
        {
            "key": "consult",
            "label": "Consult",
            "done": stg_idx >= stage_index("consult"),
        },
        {
            "key": "proposal",
            "label": "Proposal",
            "done": stg_idx >= stage_index("proposal"),
        },
        {
            "key": "won",
            "label": "Won",
            "done": _is_funnel_won(lc),
        },
    ]

    return {
        "lifecycle_id": lid,
        "service_slug": slug,
        "current_stage": current_stage,
        "decision": decision or "",
        "bant_total": bant_total,
        "milestones": milestones,
        "consult_entered_at": consult_at.strftime("%Y-%m-%d %H:%M:%S")
        if consult_at
        else "",
        "proposal_entered_at": proposal_at.strftime("%Y-%m-%d %H:%M:%S")
        if proposal_at
        else "",
        "days_to_proposal": days_to_proposal,
        "within_7d_proposal": within_7d_proposal,
        "in_person_before_consult": in_person_before_consult,
        "cohort_period_start": period_start,
        "cohort_period_end": period_end,
        "dashboard_funnel_url": dashboard_funnel_url,
    }
