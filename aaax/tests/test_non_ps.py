import pytest

from aaax.bootstrap import bootstrap_kernel
from aaax.config import AAAXConfig
from sssn.channels.broadcast import BroadcastChannel
from sssn.core.system import BaseSystem


class TrivialRobotNode(BaseSystem):
    async def setup(self) -> None:
        self.sensor = BroadcastChannel(id="sensor-data", name="Sensor", description="")
        self.add_channel(self.sensor)

    async def step(self) -> None:
        self.stop()


@pytest.mark.asyncio
async def test_kernel_processes_capability_request_without_productive_suite():
    kernel = await bootstrap_kernel(AAAXConfig(id="test-kernel", name="Test"), start_channels=True)
    robot = TrivialRobotNode(id="robot-1", name="Robot")
    await kernel.dock(robot)

    await robot.write_channel(
        "aaax.capability-request",
        data={
            "resource": "executor:web-research",
            "access": "execute",
        },
    )
    await kernel._process_capability_requests()

    replies = await robot.read_channel("aaax.kernel-replies", limit=10)
    assert replies
    assert replies[0].content.data["type"] == "capability_grant"
    assert kernel._constellation.get("robot-1") is not None
