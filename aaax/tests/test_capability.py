import time
from types import MappingProxyType

import pytest

from aaax.capability import CapabilityManager
from aaax.policy import DefaultRulePolicy
from sssn.core.channel import ChannelMessage, GenericContent


def make_request(payload: dict) -> ChannelMessage:
    return ChannelMessage(
        id="req-1",
        timestamp=time.time(),
        sender_id=payload.get("from", "system-a"),
        content=GenericContent(data=payload),
    )


@pytest.mark.asyncio
async def test_capability_request_issues_and_validates_token():
    manager = CapabilityManager()
    result = await manager.process_request(
        make_request(
            {
                "from": "system-a",
                "resource": "executor:web-research",
                "access": "execute",
            }
        ),
        DefaultRulePolicy(),
    )

    assert result["type"] == "capability_grant"
    assert manager.validate("system-a", result["token"], "executor:web-research", "execute")


@pytest.mark.asyncio
async def test_capability_request_accepts_read_only_mapping_payload():
    manager = CapabilityManager()
    context = {"risk": "low"}
    payload = MappingProxyType(
        {
            "from": "system-a",
            "resource": "executor:web-research",
            "access": "execute",
            "context": MappingProxyType(context),
        }
    )

    result = await manager.process_request(make_request(payload), DefaultRulePolicy())

    context["risk"] = "changed"
    assert result["type"] == "capability_grant"
    assert manager.validate("system-a", result["token"], "executor:web-research", "execute")


@pytest.mark.asyncio
async def test_capability_scope_boundary_copies_read_only_mappings():
    manager = CapabilityManager()
    nested = {"owner": "system-a"}
    scope = {"ttl": 3600.0, "details": MappingProxyType(nested)}

    grant = await manager.issue(
        "system-a",
        "executor:web-research",
        "execute",
        scope=MappingProxyType(scope),
    )
    scope["ttl"] = 0.0
    nested["owner"] = "changed"

    stored_scope = manager._capabilities[grant["token"]].scope
    assert stored_scope == {"ttl": 3600.0, "details": {"owner": "system-a"}}
    assert isinstance(stored_scope["details"], dict)


@pytest.mark.asyncio
async def test_capability_token_is_bound_to_system_id():
    manager = CapabilityManager()
    grant = await manager.issue("system-a", "executor:web-research", "execute")

    assert not manager.validate("system-b", grant["token"], "executor:web-research", "execute")


@pytest.mark.asyncio
async def test_revoke_all_removes_issued_capabilities():
    manager = CapabilityManager()
    grant = await manager.issue("system-a", "executor:web-research", "execute")
    manager.revoke_all("system-a")

    assert not manager.validate("system-a", grant["token"], "executor:web-research", "execute")
