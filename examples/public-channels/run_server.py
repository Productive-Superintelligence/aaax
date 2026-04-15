from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aaax import AAAXConfig, bootstrap_kernel
from sssn.channels.broadcast import BroadcastChannel
from sssn.core.channel import Visibility
from sssn.core.system import BaseSystem


class PublicEventSource(BaseSystem):
    def __init__(self, id: str, name: str) -> None:
        super().__init__(id=id, name=name)
        self.counter = 0

    async def setup(self) -> None:
        self.events = BroadcastChannel(
            id="demo-events",
            name="Demo Events",
            description="Public event stream from the AAAX example.",
            visibility=Visibility.PUBLIC,
        )
        self.add_channel(self.events)

    async def step(self) -> None:
        await self.write_channel(
            "demo-events",
            data={
                "counter": self.counter,
                "source": self.id,
                "kind": "demo-event",
            },
        )
        self.counter += 1


async def main() -> None:
    config = AAAXConfig.from_file(Path(__file__).with_name("aaax.toml"))
    kernel = await bootstrap_kernel(config)
    source = PublicEventSource(id="public-source", name="Public Source")
    await kernel.dock(source)

    print("Starting AAAX public channel demo on http://127.0.0.1:8100")
    print("Try:")
    print('  curl -H "Authorization: Bearer demo-reader" "http://127.0.0.1:8100/channels/demo-events?limit=5"')
    await kernel.publish(host=config.network.host, port=config.network.port)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped AAAX public channel demo.")
