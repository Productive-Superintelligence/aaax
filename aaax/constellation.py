from __future__ import annotations

from dataclasses import dataclass, field

from aaax._vendor import ensure_vendor_paths

ensure_vendor_paths()

from sssn.core.channel import BaseChannel
from sssn.core.system import BaseSystem


@dataclass(slots=True)
class DockRecord:
    system_id: str
    system: BaseSystem
    granted_channels: set[str] = field(default_factory=set)
    provided_channels: set[str] = field(default_factory=set)
    privileged: bool = False
    status: str = "docked"


class ConstellationManager:
    def __init__(self) -> None:
        self._systems: dict[str, DockRecord] = {}
        self._channels: dict[str, BaseChannel] = {}

    def register(
        self,
        system: BaseSystem,
        channels: list[str] | None = None,
        *,
        privileged: bool = False,
    ) -> DockRecord:
        if system.id in self._systems:
            raise ValueError(f"System '{system.id}' is already docked.")

        provided_channels: set[str] = set()
        for channel in system.all_channels:
            existing = self._channels.get(channel.id)
            if existing is not None and existing is not channel:
                raise ValueError(f"Channel '{channel.id}' already registered by another system.")
            self._channels[channel.id] = channel
            provided_channels.add(channel.id)

        record = DockRecord(
            system_id=system.id,
            system=system,
            granted_channels=set(channels or []),
            provided_channels=provided_channels,
            privileged=privileged,
        )
        self._systems[system.id] = record
        return record

    def unregister(self, system_id: str) -> DockRecord | None:
        record = self._systems.pop(system_id, None)
        if record is None:
            return None
        for channel_id in record.provided_channels:
            channel = self._channels.get(channel_id)
            if channel is not None and channel in record.system.all_channels:
                self._channels.pop(channel_id, None)
        return record

    def get(self, system_id: str) -> DockRecord | None:
        return self._systems.get(system_id)

    def set_status(self, system_id: str, status: str) -> None:
        record = self._systems.get(system_id)
        if record is not None:
            record.status = status

    def resolve_channel(self, channel_id: str) -> BaseChannel | None:
        return self._channels.get(channel_id)

    def systems(self) -> list[DockRecord]:
        return list(self._systems.values())

    def system_ids(self) -> list[str]:
        return sorted(self._systems.keys())

    def active_count(self) -> int:
        return len(self._systems)
