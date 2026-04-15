import time

import pytest

from aaax.action_gate import ActionGate
from aaax.capability import CapabilityManager
from aaax.policy import DefaultRulePolicy
from sssn.core.channel import ChannelMessage, GenericContent


def make_request(payload: dict) -> ChannelMessage:
    return ChannelMessage(
        id="action-1",
        timestamp=time.time(),
        sender_id=payload.get("from", "system-a"),
        content=GenericContent(data=payload),
    )


@pytest.mark.asyncio
async def test_action_gate_denies_missing_capability():
    gate = ActionGate()
    result = await gate.process(
        make_request(
            {
                "from": "system-a",
                "action": "search",
                "executor": "executor:web-research",
                "target": "https://example.com",
                "payload": {},
            }
        ),
        DefaultRulePolicy(),
        CapabilityManager(),
    )

    assert result["type"] == "action_denied"


@pytest.mark.asyncio
async def test_action_gate_approves_valid_execute_capability():
    capabilities = CapabilityManager()
    grant = await capabilities.issue("system-a", "executor:web-research", "execute")
    gate = ActionGate()

    result = await gate.process(
        make_request(
            {
                "from": "system-a",
                "action": "search",
                "executor": "executor:web-research",
                "target": "query",
                "payload": {"query": "aaax"},
                "capability": grant["token"],
                "risk_level": "low",
            }
        ),
        DefaultRulePolicy(),
        capabilities,
    )

    assert result["type"] == "action_approved"
    assert result["executor"] == "executor:web-research"


@pytest.mark.asyncio
async def test_action_gate_escalates_irreversible_risk():
    capabilities = CapabilityManager()
    grant = await capabilities.issue("system-a", "executor:robot-arm", "execute")
    gate = ActionGate()

    result = await gate.process(
        make_request(
            {
                "from": "system-a",
                "action": "move",
                "executor": "executor:robot-arm",
                "target": "robot-arm-1",
                "payload": {"position": 1},
                "capability": grant["token"],
                "risk_level": "irreversible",
            }
        ),
        DefaultRulePolicy(),
        capabilities,
    )

    assert result["type"] == "action_escalated"
