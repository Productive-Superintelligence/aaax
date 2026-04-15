from __future__ import annotations

from typing import Any

from aaax.capability import CapabilityManager
from aaax.policy import PolicyEngine


def _message_content_data(msg) -> dict[str, Any]:
    content = getattr(msg, "content", None)
    data = getattr(content, "data", None)
    return data if isinstance(data, dict) else {}


def _requester_id(msg, payload: dict[str, Any]) -> str:
    return str(payload.get("from") or payload.get("system_id") or msg.sender_id)


class ActionGate:
    """Authorize and classify side-effecting operations."""

    async def process(
        self,
        msg,
        policy: PolicyEngine,
        capabilities: CapabilityManager,
    ) -> dict[str, Any]:
        content = _message_content_data(msg)
        system_id = _requester_id(msg, content)
        action = str(content["action"])
        executor = str(content["executor"])
        target = str(content["target"])
        payload = content.get("payload", {})
        cap_token = content.get("capability")
        risk_level = str(content.get("risk_level", "medium"))

        if not cap_token:
            return {
                "type": "action_denied",
                "request_id": msg.id,
                "reason": "Missing execute capability token",
            }

        if not capabilities.validate(system_id, cap_token, executor, "execute"):
            return {
                "type": "action_denied",
                "request_id": msg.id,
                "reason": "Invalid or expired capability token",
            }

        decision = await policy.evaluate_action(
            system_id=system_id,
            action=action,
            executor=executor,
            target=target,
            payload=payload,
            risk_level=risk_level,
        )
        if decision.escalate:
            return {
                "type": "action_escalated",
                "request_id": msg.id,
                "reason": decision.reason,
                "escalated_to": decision.escalate_to,
            }
        if not decision.allowed:
            return {
                "type": "action_denied",
                "request_id": msg.id,
                "reason": decision.reason,
            }
        return {
            "type": "action_approved",
            "request_id": msg.id,
            "executor": executor,
            "modified_payload": decision.modified_payload or payload,
        }
