"""Map legacy CRM webhook rows → normalized models."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from ptt_channel.enums import ChannelCode, EventSource, StandardEventName
from ptt_channel.models import NormalizedEvent, NormalizedLead, UtmParams


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _idempotency_key(channel: ChannelCode, parts: dict[str, Any]) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.sha256(f"{channel.value}:{blob}".encode()).hexdigest()
    return digest[:64]


def legacy_lead_row_to_normalized(
    row: dict[str, Any],
    *,
    client_id: str,
    channel: ChannelCode,
) -> NormalizedLead:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    external_lead_id = str(
        meta.get("facebook_leadgen_id")
        or meta.get("zalo_lead_id")
        or row.get("external_lead_id")
        or _idempotency_key(channel, {"phone": row.get("phone"), "email": row.get("email"), "name": row.get("full_name")})
    )
    utm_campaign = str(row.get("utm_campaign") or meta.get("utm_campaign") or "")
    return NormalizedLead(
        client_id=client_id,
        channel=channel,
        external_lead_id=external_lead_id,
        idempotency_key=_idempotency_key(
            channel,
            {"external_lead_id": external_lead_id, "client_id": client_id},
        ),
        occurred_at=str(row.get("occurred_at") or _utc_now_iso()),
        contact={
            "full_name": str(row.get("full_name") or row.get("name") or "") or None,
            "phone": str(row.get("phone") or row.get("phone_number") or "") or None,
            "email": str(row.get("email") or "") or None,
        },
        fields={
            k: str(v)
            for k, v in row.items()
            if k not in {"full_name", "name", "phone", "phone_number", "email", "meta", "source"}
            and v is not None
        },
        external_form_id=str(meta.get("facebook_form_id") or meta.get("form_id") or "") or None,
        external_campaign_id=str(
            meta.get("facebook_campaign_id") or meta.get("campaign_id") or utm_campaign or ""
        )
        or None,
        utm=UtmParams(campaign=utm_campaign or None, source=channel.value) if utm_campaign else UtmParams(source=channel.value),
        raw=row,
    )


def normalized_lead_to_legacy(lead: dict[str, Any] | NormalizedLead) -> dict[str, Any]:
    """Map NormalizedLead → legacy CRM webhook item for ingest_webhook_leads."""
    if isinstance(lead, NormalizedLead):
        data = lead.to_dict()
    else:
        data = dict(lead)

    raw = data.get("raw")
    if isinstance(raw, dict) and (raw.get("full_name") or raw.get("phone") or raw.get("email")):
        return raw

    contact = data.get("contact") if isinstance(data.get("contact"), dict) else {}
    channel = str(data.get("channel") or "")
    source = "facebook" if channel == ChannelCode.META.value else channel or "webhook"

    meta: dict[str, Any] = {}
    if isinstance(raw, dict) and isinstance(raw.get("meta"), dict):
        meta = dict(raw["meta"])
    ext_id = str(data.get("external_lead_id") or "")
    if channel == ChannelCode.META.value and ext_id:
        meta.setdefault("facebook_leadgen_id", ext_id)
    elif channel == ChannelCode.ZALO.value and ext_id:
        meta.setdefault("zalo_lead_id", ext_id)

    utm = data.get("utm") if isinstance(data.get("utm"), dict) else {}
    fields = data.get("fields") if isinstance(data.get("fields"), dict) else {}

    item: dict[str, Any] = {
        "full_name": str(contact.get("full_name") or fields.get("full_name") or ""),
        "phone": str(contact.get("phone") or fields.get("phone") or ""),
        "email": str(contact.get("email") or fields.get("email") or ""),
        "source": source,
        "utm_campaign": str(
            utm.get("campaign") or data.get("external_campaign_id") or fields.get("utm_campaign") or ""
        ),
        "meta": meta,
    }
    for key, val in fields.items():
        if key not in item and val is not None:
            item[key] = val
    return item


def lead_to_standard_event(lead: NormalizedLead) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=lead.idempotency_key,
        event_name=StandardEventName.LEAD,
        occurred_at=lead.occurred_at,
        source=EventSource.WEBHOOK,
        client_id=lead.client_id,
        channel=lead.channel,
        user={
            "email": lead.contact.get("email"),
            "phone": lead.contact.get("phone"),
            "external_id": lead.external_lead_id,
        },
        custom_data={"fields": lead.fields},
        utm=lead.utm,
        raw=lead.raw,
    )
