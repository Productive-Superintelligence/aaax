from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aaax.boundary import copy_mapping


def _load_toml(path: str | Path) -> dict[str, Any]:
    try:
        import tomllib  # type: ignore[attr-defined]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

    with open(path, "rb") as handle:
        return tomllib.load(handle)


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""
    escalate: bool = False
    escalate_to: str = ""
    modified_payload: dict[str, Any] | None = None


class PolicyEngine(ABC):
    @abstractmethod
    async def evaluate_capability(
        self,
        system_id: str,
        resource: str,
        access: str,
        context: dict[str, Any],
    ) -> PolicyDecision:
        ...

    @abstractmethod
    async def evaluate_action(
        self,
        system_id: str,
        action: str,
        executor: str,
        target: str,
        payload: dict[str, Any],
        risk_level: str,
    ) -> PolicyDecision:
        ...

    @abstractmethod
    async def evaluate_module(self, manifest: dict[str, Any]) -> PolicyDecision:
        ...

    @classmethod
    def from_config(cls, config: str | dict[str, Any] | None) -> "PolicyEngine":
        if config in (None, "default"):
            return DefaultRulePolicy()
        if isinstance(config, dict):
            return DefaultRulePolicy(rules=config)
        if isinstance(config, str):
            return DefaultRulePolicy.from_file(config)
        return DefaultRulePolicy()


class DefaultRulePolicy(PolicyEngine):
    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self._rules = copy_mapping(rules) if isinstance(rules, Mapping) and rules else {
            "default_capability": "allow",
            "default_action": {
                "low": "allow",
                "medium": "allow",
                "high": "deny",
                "irreversible": "escalate",
            },
            "default_module": "allow",
        }

    async def evaluate_capability(
        self,
        system_id: str,
        resource: str,
        access: str,
        context: dict[str, Any],
    ) -> PolicyDecision:
        del system_id, resource, access, context
        rule = self._rules.get("default_capability", "allow")
        if rule == "deny":
            return PolicyDecision(allowed=False, reason="Capability requests denied by default policy")
        return PolicyDecision(allowed=True)

    async def evaluate_action(
        self,
        system_id: str,
        action: str,
        executor: str,
        target: str,
        payload: dict[str, Any],
        risk_level: str,
    ) -> PolicyDecision:
        del system_id, action, executor, target, payload
        rule = self._rules.get("default_action", {}).get(risk_level, "deny")
        if rule == "allow":
            return PolicyDecision(allowed=True)
        if rule == "escalate":
            return PolicyDecision(
                allowed=False,
                reason=f"Risk '{risk_level}' requires escalation",
                escalate=True,
                escalate_to="human",
            )
        return PolicyDecision(allowed=False, reason=f"Denied for risk '{risk_level}'")

    async def evaluate_module(self, manifest: dict[str, Any]) -> PolicyDecision:
        del manifest
        rule = self._rules.get("default_module", "allow")
        if rule == "deny":
            return PolicyDecision(allowed=False, reason="Module loading denied by default policy")
        return PolicyDecision(allowed=True)

    @classmethod
    def from_file(cls, path: str | Path) -> "DefaultRulePolicy":
        return cls(rules=_load_toml(path))
