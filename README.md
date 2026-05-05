<div align="center">
  <!-- <img src="https://raw.githubusercontent.com/Productive-Superintelligence/aaax/main/docs/assets/aaax-logo-text-black.png" alt="AAAX Logo" width="600"/> -->
  <img src="docs/assets/aaax-logo-text-black.png" alt="AAAX Logo" width="600" />
  <br>
  <h1>Advanced Autonomous Agentic ICS (AAAX)</h1>
  <h4>Exokernel for agentic information and computing services.</h4>
</div>

<p align="center">
  <a href="https://aaax.one">
    <img alt="Docs" src="https://img.shields.io/badge/docs-aaax.one-black">
  </a>
  <a href="https://pypi.org/project/aaax/">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/aaax.svg">
  </a>
  <a href="https://github.com/Productive-Superintelligence/aaax/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/Productive-Superintelligence/aaax">
  </a>
</p>

> ⚠️ In active development. Not ready for production use.

AAAX stands for **Advanced Autonomous Agentic ICS** — **Information and Computing Services**. It sits above `sssn` and `lllm` and gives a shell-like control plane inspired by Exokernel and ROS:

- dock and wire modules into a governed constellation
- issue and revoke capabilities for mediated resources
- authorize side effects through an action gate
- manage lifecycle events like revoke, pause, resume, and drain.

The current codebase is the first kernel slice: bootstrap, governance channels, policy engine, module loading, lifecycle control, and a minimal LLLM bridge are implemented and tested. 

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
