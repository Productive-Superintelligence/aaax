from __future__ import annotations

from typing import Any, Literal

from aaax._vendor import ensure_vendor_paths

ensure_vendor_paths()

from sssn.core.channel import MessageContent


class CapabilityRequest(MessageContent):
    system_id: str
    resource: str
    access: Literal["read", "write", "execute"]
    scope: dict[str, Any] = {}
    context: dict[str, Any] = {}


class CapabilityGrant(MessageContent):
    resource: str
    token: str
    expires: float


class CapabilityDeny(MessageContent):
    resource: str
    reason: str
