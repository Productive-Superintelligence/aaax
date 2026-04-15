from __future__ import annotations

from aaax.config import AAAXConfig
from aaax.kernel import AAAXKernel


async def bootstrap_kernel(config: AAAXConfig, *, start_channels: bool = False) -> AAAXKernel:
    kernel = AAAXKernel(config)
    await kernel.setup()
    kernel._setup_done = True
    if start_channels:
        await kernel.start_owned_channels()
    return kernel
