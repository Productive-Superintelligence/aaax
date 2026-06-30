from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from aaax.boundary import copy_boundary_value, copy_mapping
from aaax.policy import PolicyEngine

ACCESS_LEVELS = {"read": 0, "write": 1, "execute": 2}


def _message_content_data(msg) -> dict[str, Any]:
    content = getattr(msg, "content", None)
    data = getattr(content, "data", None)
    return copy_mapping(data) if isinstance(data, Mapping) else {}


def _requester_id(msg, payload: dict[str, Any]) -> str:
    return str(payload.get("from") or payload.get("system_id") or msg.sender_id)


@dataclass(slots=True)
class Capability:
    token: str
    system_id: str
    resource: str
    access: str
    issued_at: float
    expires_at: float
    scope: dict[str, Any] = field(default_factory=dict)


class CapabilityManager:
    """AAAX-local capability tokens for mediated resources."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}
        self._by_system: dict[str, set[str]] = {}

    async def process_request(self, msg, policy: PolicyEngine) -> dict[str, Any]:
        content = _message_content_data(msg)
        system_id = _requester_id(msg, content)
        resource = str(content["resource"])
        access = str(content["access"])
        scope = content.get("scope", {})
        context = content.get("context", {})
        if isinstance(context, Mapping):
            context = copy_mapping(context)

        decision = await policy.evaluate_capability(
            system_id=system_id,
            resource=resource,
            access=access,
            context=context,
        )
        if not decision.allowed:
            return {
                "type": "capability_deny",
                "resource": resource,
                "reason": decision.reason,
            }

        return await self.issue(
            system_id=system_id,
            resource=resource,
            access=access,
            scope=scope,
        )

    async def issue(
        self,
        system_id: str,
        resource: str,
        access: str,
        scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scope = copy_mapping(scope) if isinstance(scope, Mapping) else {}
        ttl = float(scope.get("ttl", 3600.0))
        token = uuid.uuid4().hex
        now = time.time()
        capability = Capability(
            token=token,
            system_id=system_id,
            resource=resource,
            access=access,
            issued_at=now,
            expires_at=now + ttl,
            scope=copy_boundary_value(scope),
        )
        self._capabilities[token] = capability
        self._by_system.setdefault(system_id, set()).add(token)
        return {
            "type": "capability_grant",
            "resource": resource,
            "token": token,
            "expires": capability.expires_at,
        }

    def validate(self, system_id: str, token: str, resource: str, access: str) -> bool:
        capability = self._capabilities.get(token)
        if capability is None:
            return False
        if capability.expires_at < time.time():
            self._capabilities.pop(token, None)
            self._by_system.get(capability.system_id, set()).discard(token)
            return False
        if capability.system_id != system_id:
            return False
        if capability.resource != resource:
            return False
        return ACCESS_LEVELS.get(capability.access, -1) >= ACCESS_LEVELS.get(access, 0)

    def revoke_all(self, system_id: str) -> None:
        tokens = self._by_system.pop(system_id, set())
        for token in tokens:
            self._capabilities.pop(token, None)

    def expire_stale(self) -> None:
        now = time.time()
        expired = [token for token, cap in self._capabilities.items() if cap.expires_at < now]
        for token in expired:
            cap = self._capabilities.pop(token)
            self._by_system.get(cap.system_id, set()).discard(token)

    def active_count(self) -> int:
        return len(self._capabilities)
