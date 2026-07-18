"""Adapter registry."""
from __future__ import annotations

from ptt_channel.base import ChannelAdapter, ChannelNotSupportedError
from ptt_channel.capabilities import AdapterCapabilities
from ptt_channel.enums import ChannelCode


class ChannelAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[ChannelCode, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter) -> None:
        self._adapters[adapter.channel] = adapter

    def get(self, channel: ChannelCode | str) -> ChannelAdapter:
        code = channel if isinstance(channel, ChannelCode) else ChannelCode(str(channel))
        adapter = self._adapters.get(code)
        if adapter is None:
            raise ChannelNotSupportedError(code)
        return adapter

    def has(self, channel: ChannelCode | str) -> bool:
        code = channel if isinstance(channel, ChannelCode) else ChannelCode(str(channel))
        return code in self._adapters

    def list_channels(self) -> list[ChannelCode]:
        return list(self._adapters.keys())

    def list_capabilities(self) -> dict[str, AdapterCapabilities]:
        return {a.channel.value: a.capabilities for a in self._adapters.values()}


_default_registry: ChannelAdapterRegistry | None = None


def register_default_adapters(registry: ChannelAdapterRegistry) -> None:
    from ptt_channel.adapters.email import EmailAdapter
    from ptt_channel.adapters.google import GoogleAdsAdapter
    from ptt_channel.adapters.meta import MetaAdapter
    from ptt_channel.adapters.zalo import ZaloAdapter

    registry.register(MetaAdapter())
    registry.register(ZaloAdapter())
    registry.register(GoogleAdsAdapter())
    registry.register(EmailAdapter())


def get_default_registry() -> ChannelAdapterRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = ChannelAdapterRegistry()
        register_default_adapters(_default_registry)
    return _default_registry
