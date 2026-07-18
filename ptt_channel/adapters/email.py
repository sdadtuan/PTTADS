"""Email marketing channel adapter (stub — Phase 3)."""
from __future__ import annotations

from ptt_channel.base import ChannelAdapter
from ptt_channel.capabilities import AdapterCapabilities
from ptt_channel.context import AdapterContext
from ptt_channel.enums import ChannelCode, EventSource, StandardEventName
from ptt_channel.models import NormalizedEvent
from ptt_channel.results import CredentialValidationResult, WebhookParseResult


class EmailAdapter(ChannelAdapter):
    @property
    def channel(self) -> ChannelCode:
        return ChannelCode.EMAIL

    @property
    def display_name(self) -> str:
        return "Email Marketing (ESP)"

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_webhooks=True,
            supports_server_events=False,
            supports_campaign_write=True,
            supports_lead_ingest=False,
            supports_daily_insights=True,
            supports_creative_upload=True,
            supports_audience_sync=True,
            max_insights_lookback_days=365,
        )

    def validate_credentials(self, ctx: AdapterContext) -> CredentialValidationResult:
        return CredentialValidationResult(valid=False, message="Not implemented — ESP API key")

    def parse_webhook(
        self,
        headers: dict[str, str],
        raw_body: bytes,
        query: dict[str, str] | None = None,
        *,
        client_id: str = "",
    ) -> WebhookParseResult:
        return WebhookParseResult(verified=False, reject_reason="Email ESP webhook not implemented")

    def normalize_event(self, raw: dict, source: str) -> NormalizedEvent | None:
        event_type = str(raw.get("event") or raw.get("type") or "").lower()
        name_map = {
            "open": StandardEventName.EMAIL_OPEN,
            "click": StandardEventName.EMAIL_CLICK,
            "unsubscribe": StandardEventName.UNSUBSCRIBE,
        }
        mapped = name_map.get(event_type)
        if not mapped:
            return None
        return NormalizedEvent(
            event_id=str(raw.get("id") or raw.get("event_id") or ""),
            event_name=mapped,
            occurred_at=str(raw.get("timestamp") or ""),
            source=EventSource.EMAIL,
            channel=ChannelCode.EMAIL,
            user={"email": str(raw.get("email") or "") or None},
            raw=raw,
        )
