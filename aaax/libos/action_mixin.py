from __future__ import annotations


class ActionMixin:
    """Convenience helper for docked systems that route side effects via AAAX."""

    async def request_action(
        self,
        *,
        action: str,
        executor: str,
        target: str,
        payload: dict,
        capability: str,
        risk_level: str = "medium",
    ) -> None:
        await self.write_channel(
            "aaax.action-gate",
            data={
                "action": action,
                "executor": executor,
                "target": target,
                "payload": payload,
                "capability": capability,
                "risk_level": risk_level,
            },
        )
