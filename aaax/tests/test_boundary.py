from types import MappingProxyType

import pytest

from aaax.config import ModuleConfig
from aaax.libos.bridge import TacticSystem
from aaax.module_loader import ModuleLoader
from aaax.policy import DefaultRulePolicy


def test_module_manifest_boundary_copies_read_only_mappings():
    nested = {"value": "original"}
    manifest = {
        "module_id": "module-a",
        "framework": "custom",
        "nested": MappingProxyType(nested),
    }
    config = ModuleConfig.model_construct(
        id="module-a",
        framework="custom",
        lllm_toml=None,
        channels=[],
        executors=[],
        remote_channels=[],
        manifest=MappingProxyType(manifest),
    )

    parsed = ModuleLoader()._parse_manifest(config)
    nested["value"] = "changed"

    assert parsed["nested"] == {"value": "original"}
    assert isinstance(parsed["nested"], dict)


def test_tactic_system_manifest_boundary_copies_read_only_mappings():
    nested = {"value": "original"}
    manifest = {
        "module_id": "module-a",
        "lllm_toml": "lllm.toml",
        "nested": MappingProxyType(nested),
    }

    system = TacticSystem(
        id="module-a",
        name="module-a",
        manifest=MappingProxyType(manifest),
        libos=None,
    )
    nested["value"] = "changed"

    assert system.manifest["nested"] == {"value": "original"}
    assert isinstance(system.manifest["nested"], dict)


@pytest.mark.asyncio
async def test_policy_rules_boundary_copy_read_only_mappings():
    action_rules = {"low": "allow"}
    rules = {
        "default_capability": "allow",
        "default_action": MappingProxyType(action_rules),
        "default_module": "allow",
    }

    policy = DefaultRulePolicy(rules=MappingProxyType(rules))
    action_rules["low"] = "deny"

    decision = await policy.evaluate_action(
        system_id="system-a",
        action="search",
        executor="executor:web-research",
        target="query",
        payload={},
        risk_level="low",
    )

    assert decision.allowed is True
