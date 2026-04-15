# 2. Expose Public Channels

AAAX can run with SSSN HTTP transport and expose selected `PUBLIC` channels over the network.

That is not the same thing as “publishing a kernel.” In the current model, the kernel, the LibOS bridge, and the docked application systems run together as one AAAX constellation. `publish()` is just the helper that starts that runtime and attaches HTTP transport to public channels.

## 1. Configure network settings

```toml
[aaax.network]
publish = true
host = "0.0.0.0"
port = 8100
```

## 2. Call `publish()`

```python
import asyncio

from aaax import AAAXConfig, bootstrap_kernel


async def main() -> None:
    config = AAAXConfig.from_file("aaax.toml")
    kernel = await bootstrap_kernel(config)
    await kernel.publish(host=config.network.host, port=config.network.port)


asyncio.run(main())
```

## 3. Understand what `publish()` actually does

`AAAXKernel.publish(...)`:

1. ensures the kernel is set up
2. creates the SSSN HTTP server
3. attaches HTTP transport to `PUBLIC` channels in the kernel and docked systems
4. starts the kernel run loop, subsystem run loops, and the HTTP server together

What becomes public is the channel surface of the running AAAX constellation. Internal governance channels remain kernel-local by design.

That means the safe publication pattern is:

1. keep governance and registry channels private
2. explicitly expose only application-facing channels
3. treat AAAX capabilities and SSSN transport security as complementary rather than interchangeable

## 4. Run with HTTP transport from the CLI

The current CLI starts the AAAX runtime and enables HTTP transport with a flag:

```bash
aaax launch aaax.toml --publish
```

This is enough for the first kernel slice. More operational commands can layer on later without changing the basic contract.

## 5. What to think of as “published”

If you need a precise mental model, think of AAAX like this:

- `launch()` runs the AAAX constellation locally
- `publish()` runs the same constellation with HTTP transport attached to selected public channels
- the kernel is part of that running constellation, not a separately published service layer
