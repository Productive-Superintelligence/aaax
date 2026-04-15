# Overview

## The stack

```text
Productive Suite and other AAAX applications
                  |
                AAAX
                  |
      LLLM and other LibOS adapters
                  |
                SSSN
```

AAAX, short for **Advanced Autonomous Agentic ICS** — **Information and Computing Services**, is the kernel layer for autonomous information and computing services:

- `SSSN` is the network substrate.
- `LLLM` is the default LibOS.
- `AAAX` is the governance and lifecycle kernel.
- `Productive Suite` is the first citizen application layer.

## Why AAAX is separate

If you push governance directly into `sssn`, the network substrate stops being simple. If you push it directly into `lllm`, the runtime layer stops being general. AAAX preserves both lower abstractions and adds the missing operating contract above them.

## AAAX as a kernel, not a framework replacement

AAAX is responsible for:

- deciding which modules may dock
- determining which resources are capability-mediated
- authorizing side-effect requests
- coordinating module lifecycle
- standardizing how applications talk to the default LibOS

AAAX is not responsible for:

- redefining SSSN channel or transport behavior
- redefining LLLM package semantics
- providing hard local sandboxing by itself
- turning the kernel into a separately publishable artifact apart from the running application constellation

## Stability strategy

AAAX treats `sssn` and `lllm` as upstream frameworks with explicit contracts:

- prefer public APIs and adapters over internal imports
- force deterministic LLLM boot
- describe SSSN local security honestly as topology-based
- keep AAAX’s public contract at the kernel layer so framework changes stay behind the bridge

That is what allows AAAX to be the application contract even while the lower frameworks continue to evolve.
