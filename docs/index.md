# Welcome to AAAX

<p align="center">
  <img src="assets/aaax-logo-text-black.png#only-light" alt="AAAX Logo" width="600"/>
  <img src="assets/aaax-logo-text-white.png#only-dark" alt="AAAX Logo" width="600"/>
</p>

**AAAX** stands for **Advanced Autonomous Agentic ICS** — **Information and Computing Services**. It is the governed kernel and control plane for autonomous information and computing services built on top of `sssn` and `lllm`.

---

## The Mental Model

```text
          AAAX applications
                  |
                AAAX
                  |
      LLLM and other LibOS adapters
                  |
                SSSN
```

`sssn` gives you systems, channels, topology, and transport. `lllm` gives you packages, runtimes, prompts, and tactics. AAAX sits above both and owns the operating layer that neither lower framework should absorb directly.

---

## The Six Kernel Functions

**Constellation management.**
Dock and undock systems, wire protocol channels, and track constellation state.

**Capability issuance.**
Issue mediated capability tokens for executors and remote resources.

**Action authorization.**
Approve, deny, or escalate side effects through the action gate.

**Module loading.**
Admit modules under policy and dock them into the running constellation.

**Lifecycle control.**
Handle revoke, pause, resume, and drain coherently.

**Bootstrap.**
Start the governance channels and the default LibOS bridge.

---

## Design Principles

**Governance above frameworks.**
AAAX adds control-plane semantics without collapsing `sssn` or `lllm` into AAAX-specific designs.

**Topology is not capability.**
Local SSSN wiring remains topology authority. AAAX capabilities are for mediated resources and AAAX-owned execution paths.

**Deterministic boot.**
The default LLLM bridge runs in strict boot mode so the kernel knows exactly which modules it is loading.

---

## Quick Start

```bash
pip install aaax
aaax launch aaax.toml
```

Or bootstrap from Python:

```python
import asyncio

from aaax import AAAXConfig, bootstrap_kernel


async def main() -> None:
    config = AAAXConfig.from_file("aaax.toml")
    kernel = await bootstrap_kernel(config, start_channels=True)
    await kernel.step()


asyncio.run(main())
```

---

## Current Status

The current package implements the first kernel slice:

- bootstrap, kernel, config, and CLI entry points
- governance channels and mailbox replies
- default rule policy engine
- capability manager and action gate
- module loader with a minimal LLLM-backed `TacticSystem`
- cooperative lifecycle handling
- tests for boot, docking, capability issuance, action gating

---

## Learning Path

| Step | What you'll learn |
|------|-------------------|
| [Getting Started](getting-started.md) | Install AAAX, write a config, boot a kernel |
| [Architecture → Overview](architecture/overview.md) | How AAAX sits above `sssn` and `lllm` |
| [Architecture → Kernel Functions](architecture/kernel-functions.md) | What the kernel owns |
| [Core Reference → Governance](core/governance.md) | Capabilities, actions, lifecycle |
| [Core Reference → Module Loading](core/modules.md) | How manifests become docked systems |
| [API Reference](reference/api.md) | Public Python surface |
