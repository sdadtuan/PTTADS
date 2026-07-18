"""Normalized cross-channel data models (JSON Schema aligned)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ptt_channel.enums import ChannelCode, EventSource, StandardEventName


@dataclass
class UtmParams:
    source: str | None = None
    medium: str | None = None
    campaign: str | None = None
    content: str | None = None
    term: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass
class NormalizedLead:
    client_id: str
    channel: ChannelCode
    external_lead_id: str
    idempotency_key: str
    occurred_at: str
    contact: dict[str, str | None] = field(default_factory=dict)
    fields: dict[str, str] = field(default_factory=dict)
    external_form_id: str | None = None
    external_campaign_id: str | None = None
    external_ad_id: str | None = None
    utm: UtmParams | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["channel"] = self.channel.value
        if self.utm:
            d["utm"] = self.utm.to_dict()
        return d


@dataclass
class NormalizedEvent:
    event_id: str
    event_name: StandardEventName
    occurred_at: str
    source: EventSource
    client_id: str | None = None
    channel: ChannelCode | None = None
    user: dict[str, str | None] = field(default_factory=dict)
    custom_data: dict[str, Any] = field(default_factory=dict)
    utm: UtmParams | None = None
    page_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_name"] = self.event_name.value
        d["source"] = self.source.value
        if self.channel:
            d["channel"] = self.channel.value
        if self.utm:
            d["utm"] = self.utm.to_dict()
        return d


@dataclass
class NormalizedDailyPerformance:
    client_id: str
    channel: ChannelCode
    date: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    currency: str
    external_campaign_id: str | None = None
    external_ad_group_id: str | None = None
    external_ad_id: str | None = None
    reach: int | None = None
    conversion_value: float | None = None
    cpc: float | None = None
    cpm: float | None = None
    ctr: float | None = None
    cpa: float | None = None
    roas: float | None = None
    frequency: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["channel"] = self.channel.value
        return d


@dataclass
class NormalizedCampaign:
    client_id: str
    channel: ChannelCode
    external_id: str
    name: str
    objective: str
    status: str
    currency: str
    daily_budget: float | None = None
    lifetime_budget: float | None = None
    start_time: str | None = None
    end_time: str | None = None
    utm_campaign: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["channel"] = self.channel.value
        return d
