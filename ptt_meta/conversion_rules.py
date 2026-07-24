"""Meta conversion rules engine (B9) — CRM status → CAPI events."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, TypedDict

from ptt_jobs.db import pg_connection
from ptt_meta.capi_dispatch import hash_email, hash_phone

logger = logging.getLogger(__name__)

_ACTION_SOURCE = "system_generated"


class ConversionRule(TypedDict):
    id: str
    client_id: str | None
    lead_status: str
    event_name: str
    enabled: bool
    require_meta_attribution: bool
    value_vnd: int
    notes: str


class ConversionDispatchIntent(TypedDict, total=False):
    ok: bool
    skipped: bool
    reason: str
    lead_id: int
    client_id: str
    rule_id: str
    lead_status: str
    event_name: str
    event_id: str
    event: dict[str, Any]


def pg_meta_conversion_rules_ready() -> bool:
    try:
        from ptt_crm.pg_schema import pg_meta_conversion_rules_ready as _ready

        return _ready()
    except Exception:
        return False


def _parse_meta_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def normalize_status(value: str | None) -> str:
    return str(value or "").strip().lower()


def normalize_lead(lead: dict[str, Any]) -> dict[str, Any]:
    """Accept SQLite/PG/Nest-shaped lead dicts."""
    meta = _parse_meta_json(lead.get("meta_json"))
    for key in ("utm_campaign", "utm_source", "utm_medium", "utm_content", "utm_term"):
        if key not in meta and lead.get(key):
            meta[key] = lead.get(key)

    lead_id = lead.get("id") or lead.get("sqlite_lead_id") or lead.get("lead_id")
    client_id = (
        lead.get("client_id")
        or lead.get("agency_client_id")
        or meta.get("agency_client_id")
        or meta.get("client_id")
        or ""
    )
    external_lead_id = (
        lead.get("external_lead_id")
        or lead.get("external_id")
        or meta.get("facebook_leadgen_id")
        or meta.get("external_lead_id")
        or ""
    )
    campaign_id = (
        lead.get("campaign_id")
        or meta.get("campaign_id")
        or meta.get("facebook_campaign_id")
        or meta.get("external_campaign_id")
        or ""
    )
    external_campaign_id = (
        meta.get("external_campaign_id")
        or meta.get("utm_campaign")
        or campaign_id
        or ""
    )

    return {
        "id": int(lead_id) if lead_id is not None else 0,
        "client_id": str(client_id).strip(),
        "status": normalize_status(lead.get("status")),
        "email": str(lead.get("email") or ""),
        "phone": str(lead.get("phone") or ""),
        "channel": str(lead.get("channel") or meta.get("channel") or "").strip().lower(),
        "external_lead_id": str(external_lead_id).strip(),
        "campaign_id": str(campaign_id).strip(),
        "external_campaign_id": str(external_campaign_id).strip(),
        "meta_json": meta,
        "landing_url": str(
            lead.get("landing_url")
            or meta.get("landing_url")
            or meta.get("source_url")
            or ""
        ),
        "deal_id": str(meta.get("deal_id") or meta.get("deal_uuid") or "").strip(),
        "deal_value_vnd": meta.get("deal_value_vnd") or meta.get("deal_value") or meta.get("value_vnd"),
        "status_entered_at": lead.get("status_entered_at") or lead.get("status_changed_at"),
    }


def require_meta_attribution_ok(lead: dict[str, Any]) -> bool:
    """True when lead has Meta/UTM/campaign attribution signals."""
    norm = normalize_lead(lead)
    if norm.get("external_lead_id"):
        return True
    if norm.get("campaign_id") or norm.get("external_campaign_id"):
        return True
    meta = norm.get("meta_json") or {}
    utm_keys = ("utm_campaign", "utm_source", "utm_medium", "utm_content", "fbclid")
    if any(str(meta.get(k) or "").strip() for k in utm_keys):
        return True
    if norm.get("channel") == "meta" and (norm.get("external_lead_id") or norm.get("campaign_id")):
        return True
    return False


def _rule_row_to_dict(row: tuple[Any, ...], cols: list[str]) -> ConversionRule:
    data = dict(zip(cols, row))
    client_raw = data.get("client_id")
    return {
        "id": str(data.get("id") or ""),
        "client_id": str(client_raw) if client_raw else None,
        "lead_status": normalize_status(str(data.get("lead_status") or "")),
        "event_name": str(data.get("event_name") or "").strip(),
        "enabled": bool(data.get("enabled")),
        "require_meta_attribution": bool(data.get("require_meta_attribution", True)),
        "value_vnd": int(data.get("value_vnd") or 0),
        "notes": str(data.get("notes") or ""),
    }


def load_rules(client_id: str | None = None) -> list[ConversionRule]:
    """
    Load enabled conversion rules for a client.
    Client-specific rows override global (client_id IS NULL) on (lead_status, event_name).
    """
    if not pg_meta_conversion_rules_ready():
        return []

    cid = str(client_id or "").strip()
    params: list[Any]
    if cid:
        sql = """
            SELECT id, client_id, lead_status, event_name, enabled,
                   require_meta_attribution, value_vnd, notes
            FROM meta_conversion_rules
            WHERE client_id IS NULL OR client_id = %s::uuid
            ORDER BY client_id NULLS FIRST, lead_status, event_name
        """
        params = [cid]
    else:
        sql = """
            SELECT id, client_id, lead_status, event_name, enabled,
                   require_meta_attribution, value_vnd, notes
            FROM meta_conversion_rules
            WHERE client_id IS NULL
            ORDER BY lead_status, event_name
        """
        params = []

    merged: dict[tuple[str, str], ConversionRule] = {}
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            for row in cur.fetchall():
                rule = _rule_row_to_dict(row, cols)
                key = (rule["lead_status"], rule["event_name"])
                merged[key] = rule

    return list(merged.values())


def _status_entered_token(lead: dict[str, Any]) -> str:
    raw = lead.get("status_entered_at") or lead.get("status_changed_at")
    if raw is None:
        return str(int(datetime.now(timezone.utc).timestamp()))
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            raw = raw.replace(tzinfo=timezone.utc)
        return str(int(raw.timestamp()))
    text = str(raw).strip()
    if not text:
        return str(int(datetime.now(timezone.utc).timestamp()))
    if text.isdigit():
        return text
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return str(int(dt.timestamp()))
    except ValueError:
        safe = re.sub(r"[^0-9A-Za-z_-]", "", text) or str(int(datetime.now(timezone.utc).timestamp()))
        return safe[:64]


def build_event_id(
    *,
    event_name: str,
    lead: dict[str, Any],
    manual_uuid: str | None = None,
) -> str:
    """Meta CAPI dedupe event_id convention (spec §7.3)."""
    norm = normalize_lead(lead)
    lead_id = norm["id"]
    status = norm["status"]
    external_lead_id = norm.get("external_lead_id") or ""

    if manual_uuid:
        return f"manual_{lead_id}_{manual_uuid}"

    name = event_name.strip()
    if name == "Lead" and external_lead_id:
        return f"leadgen_{external_lead_id}"

    entered = _status_entered_token(norm)
    if name == "Purchase" or status == "post_sale":
        deal_ref = norm.get("deal_id") or entered
        return f"crm_purchase_{lead_id}_{deal_ref}"

    if name in {"CompleteRegistration", "Lead"} or status in {"qualified", "new"}:
        if status == "new" and external_lead_id:
            return f"leadgen_{external_lead_id}"
        return f"crm_qualify_{lead_id}_{entered}"

    return f"crm_conv_{lead_id}_{name.lower()}_{entered}"


def _purchase_value_vnd(rule: ConversionRule, lead: dict[str, Any]) -> float:
    norm = normalize_lead(lead)
    deal_val = norm.get("deal_value_vnd")
    if deal_val is not None:
        try:
            parsed = float(deal_val)
            if parsed > 0:
                return round(parsed, 2)
        except (TypeError, ValueError):
            pass
    rule_val = int(rule.get("value_vnd") or 0)
    return float(rule_val) if rule_val > 0 else 0.0


def build_conversion_event(
    lead: dict[str, Any],
    rule: ConversionRule,
    *,
    event_time: int | None = None,
    manual_uuid: str | None = None,
) -> dict[str, Any]:
    """Build a Meta CAPI event payload for a conversion rule."""
    norm = normalize_lead(lead)
    user_data: dict[str, Any] = {}
    em = hash_email(norm.get("email"))
    ph = hash_phone(norm.get("phone"))
    if em:
        user_data["em"] = [em]
    if ph:
        user_data["ph"] = [ph]
    ext = norm.get("external_lead_id") or str(norm.get("id") or "")
    if ext:
        user_data["external_id"] = hashlib.sha256(str(ext).encode("utf-8")).hexdigest()

    event_name = str(rule.get("event_name") or "").strip()
    event_id = build_event_id(event_name=event_name, lead=norm, manual_uuid=manual_uuid)

    custom_data: dict[str, Any] = {
        "lead_id": norm.get("id"),
        "client_id": norm.get("client_id"),
        "lead_status": norm.get("status"),
        "rule_id": rule.get("id"),
    }
    if event_name == "Purchase":
        value = _purchase_value_vnd(rule, norm)
        if value > 0:
            custom_data["value"] = value
            custom_data["currency"] = "VND"

    evt: dict[str, Any] = {
        "event_name": event_name,
        "event_time": event_time or int(datetime.now(timezone.utc).timestamp()),
        "event_id": event_id,
        "action_source": _ACTION_SOURCE,
        "user_data": user_data,
        "custom_data": custom_data,
    }
    landing = norm.get("landing_url") or ""
    if landing.strip():
        evt["event_source_url"] = landing.strip()
    return evt


def evaluate_conversion_rules(
    lead: dict[str, Any],
    old_status: str | None,
    new_status: str | None,
    *,
    rules: list[ConversionRule] | None = None,
    force: bool = False,
) -> list[ConversionDispatchIntent]:
    """
    Return CAPI dispatch intents when lead enters new_status.
    Skips disabled rules and attribution-gated rules (with skipped intent + reason).
    """
    norm = normalize_lead(lead)
    lead_id = int(norm.get("id") or 0)
    client_id = str(norm.get("client_id") or "")
    target = normalize_status(new_status)
    prior = normalize_status(old_status)

    if not lead_id or not client_id:
        return [
            {
                "ok": False,
                "skipped": True,
                "reason": "missing_lead_or_client",
                "lead_id": lead_id,
                "client_id": client_id,
            }
        ]

    if not target:
        return []

    if not force and prior == target:
        return []

    active_rules = rules if rules is not None else load_rules(client_id)
    matched = [r for r in active_rules if r.get("lead_status") == target]

    intents: list[ConversionDispatchIntent] = []
    for rule in matched:
        base: ConversionDispatchIntent = {
            "ok": True,
            "lead_id": lead_id,
            "client_id": client_id,
            "rule_id": str(rule.get("id") or ""),
            "lead_status": target,
            "event_name": str(rule.get("event_name") or ""),
        }
        if not rule.get("enabled"):
            intents.append({**base, "skipped": True, "reason": "rule_disabled"})
            continue
        if rule.get("require_meta_attribution") and not require_meta_attribution_ok(norm):
            intents.append({**base, "skipped": True, "reason": "attribution_required"})
            continue
        event = build_conversion_event(norm, rule)
        intents.append(
            {
                **base,
                "skipped": False,
                "event_id": str(event.get("event_id") or ""),
                "event": event,
            }
        )
    return intents


def summarize_intents(intents: list[ConversionDispatchIntent]) -> dict[str, Any]:
    """Compact summary for jobs/logging."""
    dispatch = [i for i in intents if i.get("ok") and not i.get("skipped")]
    skipped = [i for i in intents if i.get("skipped")]
    return {
        "ok": True,
        "dispatch_count": len(dispatch),
        "skipped_count": len(skipped),
        "event_names": [i.get("event_name") for i in dispatch],
        "skip_reasons": [i.get("reason") for i in skipped if i.get("reason")],
    }
