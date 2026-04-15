from __future__ import annotations

from typing import Any, Literal

from aaax._vendor import ensure_vendor_paths

ensure_vendor_paths()

from sssn.core.channel import MessageContent


class ActionRequest(MessageContent):
    system_id: str
    action: str
    executor: str
    target: str
    payload: dict[str, Any]
    capability: str | None = None
    risk_level: Literal["low", "medium", "high", "irreversible"] = "medium"


class ActionApproved(MessageContent):
    request_id: str
    executor: str
    modified_payload: dict[str, Any]


class ActionDenied(MessageContent):
    request_id: str
    reason: str


class ActionEscalated(MessageContent):
    request_id: str
    reason: str
    escalated_to: str
