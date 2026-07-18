"""Per-channel capability flags."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AdapterCapabilities:
    supports_webhooks: bool = False
    supports_server_events: bool = False
    supports_campaign_write: bool = False
    supports_lead_ingest: bool = False
    supports_daily_insights: bool = False
    supports_creative_upload: bool = False
    supports_audience_sync: bool = False
    max_insights_lookback_days: int = 30
    rate_limit_per_minute: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)
