from __future__ import annotations

from typing import Any

from aaax._vendor import ensure_vendor_paths
from aaax.config import ModuleConfig
from aaax.policy import PolicyEngine

ensure_vendor_paths()

from sssn.core.system import BaseSystem


class PlaceholderSystem(BaseSystem):
    """Fallback docked system when no specific LibOS adapter is required yet."""

    async def step(self) -> None:
        self.stop()


class ModuleLoader:
    async def load_from_config(self, kernel, config: ModuleConfig, policy: PolicyEngine) -> None:
        manifest = self._parse_manifest(config)
        await self._verify_and_dock(kernel, manifest, policy)

    async def process_request(self, kernel, msg, policy: PolicyEngine) -> dict[str, Any]:
        payload = getattr(getattr(msg, "content", None), "data", {}) or {}
        manifest = payload.get("manifest", {})
        module_id = str(payload.get("module_id") or manifest.get("module_id"))

        decision = await policy.evaluate_module(manifest)
        if not decision.allowed:
            return {
                "type": "module_rejected",
                "module_id": module_id,
                "reason": decision.reason,
            }

        system = await self._create_system(manifest, libos=kernel._libos)
        await kernel.dock(system, channels=manifest.get("requires_channels", []))
        capabilities = await self._issue_initial_capabilities(kernel, manifest)
        return {
            "type": "module_accepted",
            "module_id": module_id,
            "system_id": system.id,
            "granted_wiring": manifest.get("requires_channels", []),
            "granted_capabilities": capabilities,
        }

    def _parse_manifest(self, config: ModuleConfig) -> dict[str, Any]:
        if config.manifest is not None:
            manifest = dict(config.manifest)
            manifest.setdefault("module_id", config.id)
            manifest.setdefault("framework", config.framework)
            manifest.setdefault("lllm_toml", config.lllm_toml)
            return manifest
        return {
            "module_id": config.id,
            "framework": config.framework,
            "lllm_toml": config.lllm_toml,
            "requires_channels": list(config.channels),
            "requires_executors": list(config.executors),
            "requires_remote_channels": list(config.remote_channels),
            "provides_channels": [],
            "risk_profile": "low",
        }

    async def _verify_and_dock(
        self,
        kernel,
        manifest: dict[str, Any],
        policy: PolicyEngine,
    ) -> None:
        decision = await policy.evaluate_module(manifest)
        if not decision.allowed:
            raise PermissionError(f"Module {manifest['module_id']} rejected: {decision.reason}")
        system = await self._create_system(manifest, libos=kernel._libos)
        await kernel.dock(system, channels=manifest.get("requires_channels", []))
        await self._issue_initial_capabilities(kernel, manifest)

    async def _create_system(self, manifest: dict[str, Any], libos=None) -> BaseSystem:
        framework = manifest.get("framework", "lllm")
        if framework == "lllm":
            from aaax.libos.bridge import TacticSystem

            return TacticSystem(
                id=manifest["module_id"],
                name=manifest["module_id"],
                manifest=manifest,
                libos=libos,
            )

        return PlaceholderSystem(id=manifest["module_id"], name=manifest["module_id"])

    async def _issue_initial_capabilities(self, kernel, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        capabilities: list[dict[str, Any]] = []
        for executor in manifest.get("requires_executors", []):
            capabilities.append(
                await kernel._capabilities.issue(
                    system_id=manifest["module_id"],
                    resource=executor,
                    access="execute",
                    scope={"issued_by": "module_loader"},
                )
            )
        for channel in manifest.get("requires_remote_channels", []):
            capabilities.append(
                await kernel._capabilities.issue(
                    system_id=manifest["module_id"],
                    resource=channel,
                    access="read",
                    scope={"issued_by": "module_loader"},
                )
            )
        return capabilities
