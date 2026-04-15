from __future__ import annotations

from typing import Any

from aaax._vendor import ensure_vendor_paths

ensure_vendor_paths()

from sssn.core.channel import MessageContent


class ModuleRequest(MessageContent):
    module_id: str
    manifest: dict[str, Any]


class ModuleAccepted(MessageContent):
    module_id: str
    system_id: str
    granted_wiring: list[str]
    granted_capabilities: list[dict[str, Any]]


class ModuleRejected(MessageContent):
    module_id: str
    reason: str
