"""Multi-channel ads platform — ChannelAdapter registry & normalized models."""
from __future__ import annotations

from ptt_channel.base import ChannelAdapter
from ptt_channel.enums import AssetType, CampaignObjective, ChannelCode, StandardEventName, SyncJobType
from ptt_channel.models import (
    NormalizedDailyPerformance,
    NormalizedEvent,
    NormalizedLead,
)
from ptt_channel.registry import ChannelAdapterRegistry, get_default_registry, register_default_adapters

__all__ = [
    "AssetType",
    "CampaignObjective",
    "ChannelAdapter",
    "ChannelAdapterRegistry",
    "ChannelCode",
    "NormalizedDailyPerformance",
    "NormalizedEvent",
    "NormalizedLead",
    "StandardEventName",
    "SyncJobType",
    "get_default_registry",
    "register_default_adapters",
]
