# Productive Suite

Productive Suite is the first citizen of AAAX. That does not mean it lives inside the kernel. It means AAAX’s default contracts should be strong enough that Productive Suite can be built on top of them without special-case hacks.

## Layering

```text
Productive Suite
      |
    AAAX
      |
  LLLM + SSSN
```

The suite is therefore:

- not imported by the kernel
- free to evolve as an application
- the reference workload that keeps the kernel honest

## What the suite expects from AAAX

- stable boot and module docking
- policy-driven capability issuance
- mediated action authorization
- coherent lifecycle control
- a default LibOS path for LLLM-backed modules

## What AAAX should not do for the suite

- hard-code suite-specific role semantics into the kernel
- make Productive Suite a required dependency
- collapse package install, activation, and policy approval into one hidden step

## Why “first citizen” matters

This is the same design logic that makes LLLM the first LibOS in AAAX. The first citizen defines quality pressure and real-world requirements. It should not define the lower layer’s entire identity.

That is why the suite belongs in AAAX documentation and roadmap discussion, while still remaining outside the kernel package itself.
