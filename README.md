  


# Advanced Autonomous Agent eXecutor (AAAX)

#### Exokernel for agentic information and computing services.



> ⚠️ In active development. Not ready for production use.

It sits above `sssn` and `lllm` and gives a shell-like control plane inspired by Exokernel and ROS:

- dock and wire modules into a governed constellation
- issue and revoke capabilities for mediated resources
- authorize side effects through an action gate
- manage lifecycle events like revoke, pause, resume, and drain.

The current codebase is the first kernel slice: bootstrap, governance channels, policy engine, module loading, lifecycle control, and a minimal LLLM bridge are implemented and tested. 

1. It is used with lllm, or any other agentic frameworks, it provides a module protocol, defines ways to compose modules into agents
2. It also guards low-level



## Install

```bash
pip install aaax
```

AAAX targets Python 3.10+ and installs its framework dependencies through PyPI:

- `sssn` for the network substrate
- `lllm-core` for the default LibOS bridge

## Quick Start

Create a minimal kernel config:

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

Launch the kernel:

```bash
aaax launch aaax.toml
```

Or from Python:

```python
import asyncio

from aaax import AAAXConfig, bootstrap_kernel


async def main() -> None:
    config = AAAXConfig.from_file("aaax.toml")
    kernel = await bootstrap_kernel(config, start_channels=True)
    await kernel.step()


asyncio.run(main())
```

## Architecture Stack

- `SSSN` the transport and topology substrate.
- `LLLM` the LibOS and package/runtime layer.
- `AAAX` owns governance, module trust, capability issuance, action authorization, and lifecycle.

## Project Layout

```text
aaax/                  Python package
docs/                  MkDocs site for aaax.one
examples/              Runnable AAAX examples with per-example READMEs
notes/                 design and implementation notes
sssn/                  vendored local framework source for development
lllm/                  vendored local framework source for development
```

## Documentation

Full documentation is published at [aaax.one](https://aaax.one).

- Getting started: installation, config, and first launch
- Architecture: kernel functions, framework boundaries, Productive Suite positioning
- Core reference: config, governance, module loading, and LibOS bridge
- API reference: public AAAX Python entry points





## Roadmap

[ ] Hypervisor layer

