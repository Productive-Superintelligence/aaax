# 1. First Kernel

This walkthrough boots the smallest useful AAAX kernel.

## 1. Write a config

Create `aaax.toml`:

```toml
[aaax]
id = "aaax-main"
name = "AAAX Kernel"
policy = "default"

[aaax.libos]
name = "lllm"
strict_boot = true
discover_shared_packages = false

[aaax.network]
publish = false
host = "0.0.0.0"
port = 8100
```

No modules are required for the first boot.

## 2. Bootstrap from Python

```python
import asyncio

from aaax import AAAXConfig, bootstrap_kernel


async def main() -> None:
    config = AAAXConfig.from_file("aaax.toml")
    kernel = await bootstrap_kernel(config, start_channels=True)
    print([channel.id for channel in kernel.all_channels])


asyncio.run(main())
```

You should see the kernel governance channels, including:

- `aaax.capability-request`
- `aaax.action-gate`
- `aaax.kernel-replies`
- `aaax.module-loader`
- `aaax.lifecycle`
- `aaax.heartbeat`

## 3. Step the kernel once

```python
import asyncio

from aaax import AAAXConfig, bootstrap_kernel


async def main() -> None:
    config = AAAXConfig.from_file("aaax.toml")
    kernel = await bootstrap_kernel(config, start_channels=True)
    await kernel.step()


asyncio.run(main())
```

This processes any pending governance work and emits a heartbeat if that channel is active.

## 4. Use the CLI

```bash
aaax launch aaax.toml
```

That starts the kernel run loop. Use the Python path when you want embedding and programmatic control; use the CLI when you want a standalone kernel process.
