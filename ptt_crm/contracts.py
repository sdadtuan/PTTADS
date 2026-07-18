"""LeadV1 contract constants — keep in sync with schemas/crm/lead-v1.schema.json."""
from __future__ import annotations

LEAD_V1_FIELDS: tuple[str, ...] = (
    "id",
    "full_name",
    "phone",
    "email",
    "status",
    "source",
    "channel",
    "client_id",
    "campaign_id",
    "external_lead_id",
    "owner_id",
    "created_at",
    "received_at",
    "is_duplicate",
)

LIST_RESPONSE_FIELDS: tuple[str, ...] = ("leads", "total", "limit", "offset")
