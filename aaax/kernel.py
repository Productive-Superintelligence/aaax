from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from aaax._vendor import ensure_vendor_paths
from aaax.action_gate import ActionGate
from aaax.capability import CapabilityManager
from aaax.config import AAAXConfig
from aaax.constellation import ConstellationManager
from aaax.lifecycle import LifecycleManager
from aaax.module_loader import ModuleLoader
from aaax.policy import PolicyEngine

ensure_vendor_paths()

from sssn.channels.broadcast import BroadcastChannel
from sssn.channels.mailbox import MailboxChannel
from sssn.channels.work_queue import WorkQueueChannel
from sssn.core.channel import ChannelMessage, GenericContent, Visibility
from sssn.core.system import BaseSystem


CAPABILITY_REGISTRY_ID = "aaax.internal.capability-registry"
MODULE_REGISTRY_ID = "aaax.internal.module-registry"
POLICY_STORE_ID = "aaax.internal.policy-store"
CAPABILITY_REQUEST_ID = "aaax.capability-request"
ACTION_GATE_ID = "aaax.action-gate"
KERNEL_REPLIES_ID = "aaax.kernel-replies"
MODULE_LOADER_ID = "aaax.module-loader"
LIFECYCLE_ID = "aaax.lifecycle"
HEARTBEAT_ID = "aaax.heartbeat"

COMMON_PROTOCOL_CHANNELS = (
    CAPABILITY_REQUEST_ID,
    ACTION_GATE_ID,
    KERNEL_REPLIES_ID,
    HEARTBEAT_ID,
)
PRIVILEGED_PROTOCOL_CHANNELS = (
    MODULE_LOADER_ID,
    LIFECYCLE_ID,
)


class AAAXKernel(BaseSystem):
    """AAAX exokernel implemented as a managed SSSN umbrella system."""

    def __init__(self, config: AAAXConfig) -> None:
        super().__init__(id=config.id, name=config.name)
        self.config = config
        self._constellation = ConstellationManager()
        self._capabilities = CapabilityManager()
        self._action_gate = ActionGate()
        self._module_loader = ModuleLoader()
        self._lifecycle = LifecycleManager()
        self._policy = PolicyEngine.from_config(config.policy)
        self._libos = None
        self._subsystem_tasks: dict[str, asyncio.Task] = {}

    async def setup(self) -> None:
        self._capability_registry = BroadcastChannel(
            id=CAPABILITY_REGISTRY_ID,
            name="Capability Registry",
            visibility=Visibility.PRIVATE,
        )
        self.add_channel(self._capability_registry)

        self._module_registry = BroadcastChannel(
            id=MODULE_REGISTRY_ID,
            name="Module Registry",
            visibility=Visibility.PRIVATE,
        )
        self.add_channel(self._module_registry)

        self._policy_store = BroadcastChannel(
            id=POLICY_STORE_ID,
            name="Policy Store",
            visibility=Visibility.PRIVATE,
        )
        self.add_channel(self._policy_store)

        self._cap_request_ch = WorkQueueChannel(
            id=CAPABILITY_REQUEST_ID,
            name="Capability Requests",
        )
        self.add_channel(self._cap_request_ch)

        self._action_gate_ch = WorkQueueChannel(
            id=ACTION_GATE_ID,
            name="Action Gate",
        )
        self.add_channel(self._action_gate_ch)

        self._kernel_reply_ch = MailboxChannel(
            id=KERNEL_REPLIES_ID,
            name="Kernel Replies",
        )
        self.add_channel(self._kernel_reply_ch)

        self._module_loader_ch = WorkQueueChannel(
            id=MODULE_LOADER_ID,
            name="Module Loader",
        )
        self.add_channel(self._module_loader_ch)

        self._lifecycle_ch = WorkQueueChannel(
            id=LIFECYCLE_ID,
            name="Lifecycle Commands",
        )
        self.add_channel(self._lifecycle_ch)

        self._heartbeat_ch = BroadcastChannel(
            id=HEARTBEAT_ID,
            name="Heartbeat",
        )
        self.add_channel(self._heartbeat_ch)

        from aaax.libos.bridge import DefaultLibOS

        self._libos = DefaultLibOS(kernel=self, config=self.config.libos)

        for module in self.config.modules:
            await self._module_loader.load_from_config(
                kernel=self,
                config=module,
                policy=self._policy,
            )

    async def start_owned_channels(self) -> None:
        await self._start_channels(self.all_channels)

    async def _start_channels(self, channels) -> None:
        for channel in channels:
            if getattr(channel, "_is_running", False):
                continue
            await channel.start()

    async def launch(self) -> None:
        if not self._setup_done:
            await self.setup()
            self._setup_done = True

        await self.start_owned_channels()
        for record in self._constellation.systems():
            await self._start_channels(record.system.all_channels)

        tasks = [record.system.run() for record in self._constellation.systems()]
        tasks.append(self.run())
        await asyncio.gather(*tasks)

    async def publish(self, host: str = "0.0.0.0", port: int = 8100) -> None:
        if not self._setup_done:
            await self.setup()
            self._setup_done = True

        from sssn.core.transport import HttpTransport
        from sssn.infra.server import ChannelServer

        server = ChannelServer(host=host, port=port)

        for channel in self.all_channels:
            if channel.visibility == Visibility.PUBLIC:
                channel.attach_transport(HttpTransport(server=server))
        await self.start_owned_channels()

        for record in self._constellation.systems():
            for channel in record.system.all_channels:
                if channel.visibility == Visibility.PUBLIC:
                    channel.attach_transport(HttpTransport(server=server))
            await self._start_channels(record.system.all_channels)

        tasks = [record.system.run() for record in self._constellation.systems()]
        tasks.append(self.run())
        tasks.append(server.start())
        await asyncio.gather(*tasks)

    async def step(self) -> None:
        await self._process_capability_requests()
        await self._process_action_gate()
        await self._process_module_loader()
        await self._process_lifecycle()
        await self._publish_heartbeat()
        self._capabilities.expire_stale()

    async def dock(
        self,
        system: BaseSystem,
        channels: list[str] | None = None,
        privileged: bool = False,
    ) -> None:
        if not system._setup_done:
            await system.setup()
            system._setup_done = True

        if system not in self._subsystems:
            self.add_subsystem(system)

        grants = list(COMMON_PROTOCOL_CHANNELS)
        grants.extend(channels or [])
        if privileged:
            grants.extend(PRIVILEGED_PROTOCOL_CHANNELS)

        for channel_id in grants:
            channel = self._resolve_channel(channel_id)
            if channel is None:
                raise KeyError(f"Channel '{channel_id}' is not available for docking.")
            system.client.connect(channel_id, channel)

        for channel in system.all_channels:
            self.client.connect(channel.id, channel)

        self._constellation.register(system, grants, privileged=privileged)

        if self._is_running:
            await self._start_channels(system.all_channels)
            self._subsystem_tasks[system.id] = asyncio.create_task(system.run())

    async def undock(self, system_id: str) -> None:
        self._capabilities.revoke_all(system_id)
        record = self._constellation.unregister(system_id)
        task = self._subsystem_tasks.pop(system_id, None)
        if task is not None:
            task.cancel()
        if record is None:
            return
        record.system.stop()

    def _resolve_channel(self, channel_id: str):
        for channel in self.all_channels:
            if channel.id == channel_id:
                return channel
        return self._constellation.resolve_channel(channel_id)

    async def _process_capability_requests(self) -> None:
        messages = await self.claim_channel(CAPABILITY_REQUEST_ID, limit=10)
        for message in messages:
            result = await self._capabilities.process_request(message, self._policy)
            await self._respond(message, result)
            await self.acknowledge_channel(CAPABILITY_REQUEST_ID, [message.id])

    async def _process_action_gate(self) -> None:
        messages = await self.claim_channel(ACTION_GATE_ID, limit=10)
        for message in messages:
            result = await self._action_gate.process(message, self._policy, self._capabilities)
            await self._respond(message, result)
            await self.acknowledge_channel(ACTION_GATE_ID, [message.id])

    async def _process_module_loader(self) -> None:
        messages = await self.claim_channel(MODULE_LOADER_ID, limit=10)
        for message in messages:
            result = await self._module_loader.process_request(self, message, self._policy)
            await self._respond(message, result)
            await self.acknowledge_channel(MODULE_LOADER_ID, [message.id])

    async def _process_lifecycle(self) -> None:
        messages = await self.claim_channel(LIFECYCLE_ID, limit=10)
        for message in messages:
            result = await self._lifecycle.process(message, self._constellation, self._capabilities)
            await self._respond(message, result)
            await self.acknowledge_channel(LIFECYCLE_ID, [message.id])

    async def _publish_heartbeat(self) -> None:
        if not getattr(self._heartbeat_ch, "_accepting_writes", False):
            return
        await self.write_channel(
            HEARTBEAT_ID,
            data={
                "kernel_id": self.id,
                "timestamp": time.time(),
                "systems": self._constellation.system_ids(),
                "capabilities_active": self._capabilities.active_count(),
            },
        )

    async def _respond(self, request_msg, payload: dict[str, Any]) -> None:
        recipient_id = request_msg.sender_id
        response = ChannelMessage(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            sender_id=self.id,
            content=GenericContent(data=payload),
            correlation_id=request_msg.id,
            recipient_id=recipient_id,
        )
        target_channel = self._kernel_reply_ch
        if not getattr(target_channel, "_accepting_writes", False):
            await target_channel.start()
        await target_channel.write(self.id, response, direct=True)
