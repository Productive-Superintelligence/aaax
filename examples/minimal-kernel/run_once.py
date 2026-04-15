from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aaax import AAAXConfig, bootstrap_kernel


async def main() -> None:
    config_path = Path(__file__).with_name("aaax.toml")
    config = AAAXConfig.from_file(config_path)
    kernel = await bootstrap_kernel(config, start_channels=True)
    await kernel.step()

    print(f"kernel_id={kernel.id}")
    print("channels:")
    for channel in kernel.all_channels:
        print(f"  - {channel.id}")
    print(f"docked_systems={kernel._constellation.system_ids()}")


if __name__ == "__main__":
    asyncio.run(main())
