from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping
from typing import Any

from aaax.boundary import copy_mapping
from aaax.capability import CapabilityManager
from aaax.constellation import ConstellationManager


def _message_content_data(msg) -> dict[str, Any]:
    content = getattr(msg, "content", None)
    data = getattr(content, "data", None)
    return copy_mapping(data) if isinstance(data, Mapping) else {}


class LifecycleManager:
    """Cooperative lifecycle controls for docked systems."""

    async def process(
        self,
        msg,
        constellation: ConstellationManager,
        capabilities: CapabilityManager,
    ) -> dict[str, Any]:
        content = _message_content_data(msg)
        command = str(content["command"])
        target = str(content["system_id"])
        timeout = float(content.get("timeout", 30.0))

        if constellation.get(target) is None:
            return {
                "type": "lifecycle_error",
                "command": command,
                "system_id": target,
                "reason": f"Unknown system: {target}",
            }

        if command == "revoke":
            capabilities.revoke_all(target)
            constellation.set_status(target, "revoked")
            return {"type": "lifecycle_ok", "command": command, "system_id": target}
        if command == "pause":
            self.pause(target, constellation)
            return {"type": "lifecycle_ok", "command": command, "system_id": target}
        if command == "resume":
            self.resume(target, constellation)
            return {"type": "lifecycle_ok", "command": command, "system_id": target}
        if command == "drain":
            await self.drain(target, constellation, timeout)
            return {"type": "lifecycle_ok", "command": command, "system_id": target}
        return {
            "type": "lifecycle_error",
            "command": command,
            "system_id": target,
            "reason": f"Unknown command: {command}",
        }

    def pause(self, system_id: str, constellation: ConstellationManager) -> None:
        record = constellation.get(system_id)
        if record and record.system is not None:
            record.system.pause()
        constellation.set_status(system_id, "paused")

    def resume(self, system_id: str, constellation: ConstellationManager) -> None:
        record = constellation.get(system_id)
        if record and record.system is not None:
            record.system.resume()
        constellation.set_status(system_id, "running")

    async def drain(
        self,
        system_id: str,
        constellation: ConstellationManager,
        timeout: float,
    ) -> None:
        record = constellation.get(system_id)
        if record is None:
            return
        constellation.set_status(system_id, "draining")
        system = record.system
        drain_fn = getattr(system, "drain", None)
        if callable(drain_fn):
            result = drain_fn(timeout=timeout)
            if inspect.isawaitable(result):
                await asyncio.wait_for(result, timeout=timeout)
        else:
            system.stop()
        constellation.set_status(system_id, "drained")
