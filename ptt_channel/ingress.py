"""Unified webhook ingress — dùng từ Flask route hoặc FastAPI sau này."""
from __future__ import annotations

from typing import Any

from ptt_channel.base import ChannelNotSupportedError
from ptt_channel.enums import ChannelCode
from ptt_channel.registry import ChannelAdapterRegistry, get_default_registry


def parse_channel_webhook(
    channel: str,
    headers: dict[str, str],
    raw_body: bytes,
    query: dict[str, str] | None = None,
    *,
    client_id: str = "",
    registry: ChannelAdapterRegistry | None = None,
) -> dict[str, Any]:
    """
    Parse webhook qua ChannelAdapter.

    Returns dict:
      - challenge: str|int nếu verify handshake (Meta/Zalo)
      - verified, leads, events, reject_reason
    """
    reg = registry or get_default_registry()
    try:
        adapter = reg.get(channel)
    except ChannelNotSupportedError as exc:
        return {"verified": False, "reject_reason": str(exc)}

    result = adapter.parse_webhook(headers, raw_body, query, client_id=client_id)
    if result.challenge_response is not None:
        return {"verified": True, "challenge": result.challenge_response}

    return {
        "verified": result.verified,
        "reject_reason": result.reject_reason,
        "leads": [lead.to_dict() for lead in result.leads],
        "events": [event.to_dict() for event in result.events],
        "channel": adapter.channel.value,
    }


def supported_channels(registry: ChannelAdapterRegistry | None = None) -> list[str]:
    reg = registry or get_default_registry()
    return [c.value for c in reg.list_channels()]
