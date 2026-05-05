# Getting Started

AAAX, short for **Advanced Autonomous Agentic ICS** — **Information and Computing Services**, is a normal Python package with a console entry point. The default installation model assumes `sssn` and `lllm-core` are available through PyPI and pulled in as dependencies.

## Install

```bash
pip install aaax
```

You can verify the install with:

```bash
aaax --version
python -m aaax --version
```

## Create a kernel config

Start from the repository example:

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

[[aaax.modules]]
id = "example-agent"
framework = "custom"
channels = []
executors = []
remote_channels = []
```

This boots a local kernel with the default LibOS bridge enabled and a single placeholder module.

## Launch the kernel

```bash
aaax launch aaax.toml
```

AAAX currently exposes one primary command group:

- `aaax launch <config_path>` to start a kernel from TOML
- `aaax modules list` as the future entry point for persistent registry commands

## Bootstrap from Python

```python
import asyncio

from aaax import AAAXConfig, bootstrap_kernel


async def main() -> None:
    config = AAAXConfig.from_file("aaax.toml")
    kernel = await bootstrap_kernel(config, start_channels=True)
    await kernel.step()


asyncio.run(main())
```

This is useful if your application wants to embed the kernel rather than shell out to the CLI.

## Add an LLLM-backed module

Set `framework = "lllm"` and point the module at its `lllm.toml`:

```toml
[[aaax.modules]]
id = "research-analyst"
framework = "lllm"
lllm_toml = "packages/research_analyst/lllm.toml"
channels = ["market-data"]
executors = ["analysis.executor"]
remote_channels = ["sssn://news-provider/market-news"]
```

At boot, AAAX will:

1. evaluate the module under policy
2. instantiate the default LibOS bridge
3. dock the module into the kernel constellation
4. issue mediated capabilities for requested executors and remote channels

## Expose public channels over HTTP

If you want to run an AAAX system with HTTP transport for selected public channels, either set `[aaax.network] publish = true` in your config and launch through your own code path, or call:

```python
await kernel.publish(host="0.0.0.0", port=8100)
```

This does not publish the kernel as a standalone object. It runs the AAAX constellation and attaches HTTP transport to channels whose SSSN visibility is `PUBLIC`.

Only public channels are attached to HTTP transport. Internal governance channels remain kernel-local.
