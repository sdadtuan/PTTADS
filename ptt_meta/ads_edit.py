"""B15 — Meta ad edit snapshot, diff, and preflight."""
from __future__ import annotations

from typing import Any

EDIT_ACTIONS = frozenset({"update_ad_creative", "update_ad_copy"})


def build_edit_snapshot(
    *,
    client_id: str,
    external_ad_id: str,
    stub: bool = True,
) -> dict[str, Any]:
    ad_id = str(external_ad_id or "").strip()
    return {
        "ok": True,
        "stub": stub,
        "client_id": client_id,
        "external_ad_id": ad_id,
        "effective_status": "ACTIVE",
        "headline": "Sample headline — refresh from Graph in pilot",
        "primary_text": "Sample primary text",
        "description": "",
        "call_to_action": "LEARN_MORE",
        "creative_submission_id": None,
        "external_creative_id": f"creative_{ad_id[-8:]}" if ad_id else None,
        "cached_at": None,
    }


def build_edit_diff(
    *,
    old_value: dict[str, Any],
    new_value: dict[str, Any],
) -> dict[str, Any]:
    keys = sorted(set(old_value.keys()) | set(new_value.keys()))
    changes = []
    for key in keys:
        old = old_value.get(key)
        new = new_value.get(key)
        if old != new:
            changes.append({"field": key, "old": old, "new": new})
    return {"ok": True, "changes": changes, "change_count": len(changes)}


def validate_edit_submit(
    *,
    action: str,
    client_id: str,
    external_ad_id: str,
    new_value: dict[str, Any],
    disapproved_ack: bool = False,
    effective_status: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if action not in EDIT_ACTIONS:
        errors.append("invalid_action")
    if not client_id.strip():
        errors.append("client_id_required")
    if not external_ad_id.strip():
        errors.append("external_ad_id_required")
    if not new_value:
        errors.append("new_value_required")
    if action == "update_ad_creative" and not str(new_value.get("creative_submission_id") or "").strip():
        errors.append("creative_submission_id_required")
    if action == "update_ad_copy":
        for field in ("headline", "primary_text"):
            if not str(new_value.get(field) or "").strip():
                errors.append(f"{field}_required")
    status = str(effective_status or "").upper()
    if status == "DISAPPROVED" and not disapproved_ack:
        errors.append("disapproved_ack_required")
    return errors
