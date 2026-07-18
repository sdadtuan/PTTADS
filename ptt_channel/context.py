"""Adapter execution context."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdapterContext:
    client_id: str
    channel_account_id: str
    credential_ref: str
    request_id: str
    idempotency_key: str | None = None
    locale: str = "vi"
