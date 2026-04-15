from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aaax import AAAXConfig, bootstrap_kernel
from aaax.libos.action_mixin import ActionMixin
from aaax.libos.capability_mixin import CapabilityMixin
from sssn.core.system import BaseSystem


class DemoAnalyst(CapabilityMixin, ActionMixin, BaseSystem):
    async def setup(self) -> None:
        pass

    async def step(self) -> None:
        self.stop()


async def _read_latest_reply(system: BaseSystem) -> dict:
    replies = await system.read_channel("aaax.kernel-replies", limit=10)
    if not replies:
        raise RuntimeError("Expected a reply on aaax.kernel-replies.")
    return replies[-1].content.data


async def main() -> None:
    kernel = await bootstrap_kernel(
        AAAXConfig(id="aaax-capability-demo", name="AAAX Capability Demo"),
        start_channels=True,
    )
    analyst = DemoAnalyst(id="analyst-1", name="Demo Analyst")
    await kernel.dock(analyst)

    await analyst.request_capability(
        resource="executor:web-research",
        access="execute",
        context={"reason": "capability-roundtrip example"},
    )
    await kernel.step()

    capability_reply = await _read_latest_reply(analyst)
    print("capability_reply=")
    print(json.dumps(capability_reply, indent=2, sort_keys=True))

    token = capability_reply["token"]
    await analyst.request_action(
        action="search",
        executor="executor:web-research",
        target="query:web",
        payload={"query": "Advanced Autonomous Agentic ICS"},
        capability=token,
        risk_level="low",
    )
    await kernel.step()

    action_reply = await _read_latest_reply(analyst)
    print("action_reply=")
    print(json.dumps(action_reply, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
