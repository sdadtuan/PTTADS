"""Meta (Facebook / Instagram) channel adapter."""
from __future__ import annotations

import json
from typing import Any

from crm_lead_webhooks import (
    facebook_verify_token,
    parse_facebook_webhook,
    parse_facebook_webhook_json,
    verify_facebook_signature,
)

from ptt_channel.base import ChannelAdapter
from ptt_channel.capabilities import AdapterCapabilities
from ptt_channel.context import AdapterContext
from ptt_channel.enums import CampaignObjective, ChannelCode
from ptt_channel.mappers import lead_to_standard_event, legacy_lead_row_to_normalized
from ptt_channel.results import CredentialValidationResult, WebhookParseResult


class MetaAdapter(ChannelAdapter):
    @property
    def channel(self) -> ChannelCode:
        return ChannelCode.META

    @property
    def display_name(self) -> str:
        return "Meta (Facebook & Instagram)"

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
            max_insights_lookback_days=37,
            rate_limit_per_minute=200,
        )

    def validate_credentials(self, ctx: AdapterContext) -> CredentialValidationResult:
        if not ctx.credential_ref:
            return CredentialValidationResult(valid=False, message="Missing credential_ref")
        return CredentialValidationResult(valid=True, message="Stub — wire Marketing API / Vault")

    def parse_webhook(
        self,
        headers: dict[str, str],
        raw_body: bytes,
        query: dict[str, str] | None = None,
        *,
        client_id: str = "",
    ) -> WebhookParseResult:
        q = query or {}
        mode = q.get("hub.mode") or q.get("hub_mode")
        if mode == "subscribe":
            token = q.get("hub.verify_token") or q.get("hub_verify_token") or ""
            if token and token == facebook_verify_token():
                return WebhookParseResult(
                    verified=True,
                    challenge_response=q.get("hub.challenge") or q.get("hub_challenge") or "",
                )
            return WebhookParseResult(verified=False, reject_reason="Invalid verify token")

        sig = headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256")
        if not verify_facebook_signature(raw_body, sig):
            return WebhookParseResult(verified=False, reject_reason="Invalid Facebook signature")

        payload = parse_facebook_webhook_json(raw_body)
        rows = parse_facebook_webhook(payload)
        leads = [
            legacy_lead_row_to_normalized(row, client_id=client_id or "unknown", channel=ChannelCode.META)
            for row in rows
        ]
        events = [lead_to_standard_event(lead) for lead in leads]
        return WebhookParseResult(verified=True, leads=leads, events=events)

    def map_objective(self, internal: CampaignObjective) -> str:
        mapping = {
            CampaignObjective.LEADS: "OUTCOME_LEADS",
            CampaignObjective.TRAFFIC: "OUTCOME_TRAFFIC",
            CampaignObjective.SALES: "OUTCOME_SALES",
            CampaignObjective.AWARENESS: "OUTCOME_AWARENESS",
            CampaignObjective.ENGAGEMENT: "OUTCOME_ENGAGEMENT",
        }
        return mapping.get(internal, "OUTCOME_LEADS")

    def validate_naming(self, entity_type: str, name: str) -> tuple[bool, str | None]:
        ok, err = super().validate_naming(entity_type, name)
        if not ok:
            return ok, err
        if " " in name:
            return False, "Meta naming: avoid spaces; use underscore"
        return True, None
