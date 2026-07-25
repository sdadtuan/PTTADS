"""Zalo OA / Zalo Ads channel adapter."""
from __future__ import annotations

import json

from crm_lead_webhooks import parse_zalo_webhook, verify_zalo_signature

from ptt_channel.base import ChannelAdapter
from ptt_channel.capabilities import AdapterCapabilities
from ptt_channel.context import AdapterContext
from ptt_channel.enums import ChannelCode
from ptt_channel.mappers import lead_to_standard_event, legacy_lead_row_to_normalized
from ptt_channel.results import CredentialValidationResult, WebhookParseResult


class ZaloAdapter(ChannelAdapter):
    @property
    def channel(self) -> ChannelCode:
        return ChannelCode.ZALO

    @property
    def display_name(self) -> str:
        return "Zalo OA / Zalo Ads"

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_webhooks=True,
            supports_server_events=False,
            supports_campaign_write=False,
            supports_lead_ingest=True,
            supports_daily_insights=True,
            supports_creative_upload=False,
            supports_audience_sync=False,
            max_insights_lookback_days=90,
        )

    def validate_credentials(self, ctx: AdapterContext) -> CredentialValidationResult:
        import os

        has_ref = bool(str(ctx.credential_ref or "").strip())
        has_env = bool((os.environ.get("PTT_ZALO_ACCESS_TOKEN") or "").strip())
        stub = (os.environ.get("PTT_ZALO_ADS_STUB") or "").strip().lower() in {"1", "true", "yes", "on"}
        if has_ref or has_env or stub:
            return CredentialValidationResult(valid=True, message="Zalo credentials configured")
        return CredentialValidationResult(
            valid=False,
            message="Thiếu credential_ref hoặc PTT_ZALO_ACCESS_TOKEN",
        )

    def parse_webhook(
        self,
        headers: dict[str, str],
        raw_body: bytes,
        query: dict[str, str] | None = None,
        *,
        client_id: str = "",
    ) -> WebhookParseResult:
        sig = headers.get("X-Zalo-Signature") or headers.get("x-zalo-signature")
        if not verify_zalo_signature(raw_body, sig):
            return WebhookParseResult(verified=False, reject_reason="Invalid Zalo signature")

        payload = json.loads(raw_body.decode("utf-8") or "{}")
        rows = parse_zalo_webhook(payload)
        leads = [
            legacy_lead_row_to_normalized(row, client_id=client_id or "unknown", channel=ChannelCode.ZALO)
            for row in rows
        ]
        events = [lead_to_standard_event(lead) for lead in leads]
        return WebhookParseResult(verified=True, leads=leads, events=events)
