"""Channel adapter implementations."""
from __future__ import annotations

from ptt_channel.adapters.email import EmailAdapter
from ptt_channel.adapters.google import GoogleAdsAdapter
from ptt_channel.adapters.meta import MetaAdapter
from ptt_channel.adapters.zalo import ZaloAdapter

__all__ = ["EmailAdapter", "GoogleAdsAdapter", "MetaAdapter", "ZaloAdapter"]
