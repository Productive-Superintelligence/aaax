import pytest

from aaax.bootstrap import bootstrap_kernel
from aaax.config import AAAXConfig
from aaax.kernel import ACTION_GATE_ID, CAPABILITY_REQUEST_ID, KERNEL_REPLIES_ID
from sssn.channels.broadcast import BroadcastChannel
from sssn.core.system import BaseSystem


class ProviderSystem(BaseSystem):
    async def setup(self) -> None:
        self.sensor = BroadcastChannel(id="sensor-data", name="Sensor", description="")
        self.add_channel(self.sensor)

    async def step(self) -> None:
        self.stop()


class ConsumerSystem(BaseSystem):
    async def step(self) -> None:
        self.stop()


@pytest.mark.asyncio
async def test_dock_registers_protocol_and_provided_channels():
    kernel = await bootstrap_kernel(AAAXConfig())
    provider = ProviderSystem(id="provider", name="Provider")

    await kernel.dock(provider)

    assert CAPABILITY_REQUEST_ID in provider.channel_directory
    assert ACTION_GATE_ID in provider.channel_directory
    assert KERNEL_REPLIES_ID in provider.channel_directory
    assert kernel._constellation.get("provider") is not None
    assert kernel._constellation.resolve_channel("sensor-data") is provider.sensor
    assert "sensor-data" in kernel.channel_directory


@pytest.mark.asyncio
async def test_dock_can_wire_existing_local_channel_to_second_system():
    kernel = await bootstrap_kernel(AAAXConfig())
    provider = ProviderSystem(id="provider", name="Provider")
    consumer = ConsumerSystem(id="consumer", name="Consumer")

    await kernel.dock(provider)
    await kernel.dock(consumer, channels=["sensor-data"])

    assert "sensor-data" in consumer.channel_directory
