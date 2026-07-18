"""Domain event idempotency keys — aligned with docs/specs/events/catalog.yaml."""
from __future__ import annotations

from typing import Any


def lead_assigned_idempotency_key(lead_id: int | str, owner_id: int | str) -> str:
    return f"lead:{lead_id}:assigned:{owner_id}"


def lead_created_idempotency_key(lead_id: int | str) -> str:
    return f"lead:{lead_id}:created"


def build_event_idempotency_key(event_type: str, payload: dict[str, Any]) -> str | None:
    """Return catalog idempotency key when pattern is known."""
    if event_type == "LeadAssigned":
        lead_id = payload.get("lead_id")
        owner_id = payload.get("owner_id")
        if lead_id is not None and owner_id is not None:
            return lead_assigned_idempotency_key(lead_id, owner_id)
    if event_type == "LeadCreated":
        lead_id = payload.get("lead_id")
        if lead_id is not None:
            return lead_created_idempotency_key(lead_id)
    return None
