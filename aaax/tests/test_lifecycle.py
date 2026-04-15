import pytest

from aaax.capability import CapabilityManager
from aaax.constellation import ConstellationManager
from aaax.lifecycle import LifecycleManager
from sssn.core.system import BaseSystem, SystemState


class DrainableSystem(BaseSystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.drained = False

    async def drain(self, timeout: float = 30.0) -> None:
        self.drained = True
        self.stop()

    async def step(self) -> None:
        self.stop()


def register_system(system_id: str = "worker-1"):
    manager = ConstellationManager()
    system = DrainableSystem(id=system_id, name="Worker")
    manager.register(system)
    return manager, system


def test_pause_and_resume_are_recorded_in_constellation():
    constellation, system = register_system()
    lifecycle = LifecycleManager()

    lifecycle.pause(system.id, constellation)
    assert constellation.get(system.id).status == "paused"
    assert system.state == SystemState.PAUSED

    lifecycle.resume(system.id, constellation)
    assert constellation.get(system.id).status == "running"
    assert system.state == SystemState.RUNNING


@pytest.mark.asyncio
async def test_drain_uses_system_drain_when_available():
    constellation, system = register_system()
    lifecycle = LifecycleManager()

    await lifecycle.drain(system.id, constellation, timeout=1.0)

    assert system.drained is True
    assert constellation.get(system.id).status == "drained"


def test_revoke_all_is_left_to_capability_manager():
    capabilities = CapabilityManager()
    constellation, system = register_system()
    lifecycle = LifecycleManager()

    capabilities._by_system[system.id] = {"token-1"}
    capabilities._capabilities["token-1"] = None  # type: ignore[assignment]
    lifecycle.pause(system.id, constellation)

    assert constellation.get(system.id).status == "paused"
