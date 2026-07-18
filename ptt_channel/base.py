"""ChannelAdapter abstract base."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ptt_channel.capabilities import AdapterCapabilities
from ptt_channel.context import AdapterContext
from ptt_channel.enums import CampaignObjective, ChannelCode
from ptt_channel.models import NormalizedDailyPerformance, NormalizedEvent, NormalizedLead
from ptt_channel.results import (
    CredentialValidationResult,
    HealthCheckResult,
    SyncResult,
    WebhookParseResult,
)


class ChannelNotSupportedError(LookupError):
    def __init__(self, channel: ChannelCode | str) -> None:
        super().__init__(f"Channel adapter not registered: {channel}")


class CapabilityNotSupportedError(NotImplementedError):
    def __init__(self, channel: ChannelCode, capability: str) -> None:
        super().__init__(f"{channel.value} does not support: {capability}")


class ChannelAdapter(ABC):
    """Contract for Meta, Zalo, Google Ads, Email, …"""

    @property
    @abstractmethod
    def channel(self) -> ChannelCode:
        raise NotImplementedError

    @property
    @abstractmethod
    def display_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        raise NotImplementedError

    @abstractmethod
    def validate_credentials(self, ctx: AdapterContext) -> CredentialValidationResult:
        raise NotImplementedError

    def health_check(self, ctx: AdapterContext) -> HealthCheckResult:
        result = self.validate_credentials(ctx)
        return HealthCheckResult(ok=result.valid, message=result.message)

    def list_assets(self, ctx: AdapterContext) -> SyncResult:
        raise CapabilityNotSupportedError(self.channel, "list_assets")

    def sync_campaigns(self, ctx: AdapterContext, **opts: Any) -> SyncResult:
        raise CapabilityNotSupportedError(self.channel, "sync_campaigns")

    def sync_daily_insights(self, ctx: AdapterContext, **opts: Any) -> SyncResult[NormalizedDailyPerformance]:
        raise CapabilityNotSupportedError(self.channel, "sync_daily_insights")

    def sync_leads(self, ctx: AdapterContext, **opts: Any) -> SyncResult[NormalizedLead]:
        raise CapabilityNotSupportedError(self.channel, "sync_leads")

    @abstractmethod
    def parse_webhook(
        self,
        headers: dict[str, str],
        raw_body: bytes,
        query: dict[str, str] | None = None,
        *,
        client_id: str = "",
    ) -> WebhookParseResult:
        raise NotImplementedError

    def normalize_event(self, raw: Any, source: str) -> NormalizedEvent | None:
        return None

    def map_objective(self, internal: CampaignObjective) -> str:
        return internal.value

    def validate_naming(self, entity_type: str, name: str) -> tuple[bool, str | None]:
        if not name or len(name.strip()) < 3:
            return False, "Name too short"
        return True, None
