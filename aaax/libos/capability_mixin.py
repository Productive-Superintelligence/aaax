from __future__ import annotations


class CapabilityMixin:
    """Convenience helper for docked systems that want mediated capabilities."""

    async def request_capability(
        self,
        resource: str,
        access: str,
        *,
        scope: dict | None = None,
        context: dict | None = None,
    ) -> None:
        await self.write_channel(
            "aaax.capability-request",
            data={
                "resource": resource,
                "access": access,
                "scope": scope or {},
                "context": context or {},
            },
        )
