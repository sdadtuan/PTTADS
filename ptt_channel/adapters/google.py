"""Google Ads channel adapter (stub — Phase 2)."""
from __future__ import annotations

import json

from ptt_channel.base import ChannelAdapter
from ptt_channel.capabilities import AdapterCapabilities
from ptt_channel.context import AdapterContext
from ptt_channel.enums import CampaignObjective, ChannelCode
from ptt_channel.results import CredentialValidationResult, WebhookParseResult


class GoogleAdsAdapter(ChannelAdapter):
    @property
    def channel(self) -> ChannelCode:
        return ChannelCode.GOOGLE

    @property
    def display_name(self) -> str:
        return "Google Ads"

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_webhooks=True,
            supports_server_events=True,
            supports_campaign_write=True,
            supports_lead_ingest=True,
            supports_daily_insights=True,
            supports_creative_upload=True,
            supports_audience_sync=True,
            max_insights_lookback_days=90,
        )

    def validate_credentials(self, ctx: AdapterContext) -> CredentialValidationResult:
        return CredentialValidationResult(valid=False, message="Not implemented — Google Ads API")

    def parse_webhook(
        self,
        headers: dict[str, str],
        raw_body: bytes,
        query: dict[str, str] | None = None,
        *,
        client_id: str = "",
    ) -> WebhookParseResult:
        return WebhookParseResult(verified=False, reject_reason="Google webhook handler not implemented")

    def map_objective(self, internal: CampaignObjective) -> str:
        mapping = {
            CampaignObjective.LEADS: "LEAD_GENERATION",
            CampaignObjective.TRAFFIC: "WEBSITE_TRAFFIC",
            CampaignObjective.SALES: "SALES",
            CampaignObjective.AWARENESS: "BRAND_AWARENESS",
            CampaignObjective.ENGAGEMENT: "ENGAGEMENT",
        }
        return mapping.get(internal, "LEAD_GENERATION")
