# Framework Boundaries

AAAX depends on `sssn` and `lllm`, but it does not collapse into either one. This boundary is the core reliability strategy.

## SSSN boundary

AAAX uses SSSN for:

- systems and channel abstractions
- in-process topology and wiring
- HTTP transport for public channels
- the run loop substrate

AAAX does not assume SSSN gives it:

- hard local capability enforcement
- process isolation
- true exactly-once work delivery
- strong pause semantics

That means AAAX must treat local wiring and mediated capability checks as separate concerns.

## LLLM boundary

AAAX uses LLLM for:

- package loading through `lllm.toml`
- runtime creation
- the default LibOS abstraction
- tactic execution environments

AAAX does not assume LLLM is:

- a kernel
- a security boundary
- an application policy engine

The default bridge forces strict boot and disables ambient auto-init by default.

## Upgrade isolation

AAAX avoids being whipsawed by framework changes with a few hard rules:

1. Keep AAAX’s public contract in AAAX types, protocol channels, and config schema.
2. Put framework-specific behavior behind AAAX-owned adapters.
3. Prefer public framework APIs over deep internal imports.
4. Pin framework versions tightly for releases.
5. Run AAAX contract tests before adopting framework upgrades.

## Monorepo versus published package

Inside this repository, AAAX prefers the local `sssn/` and `lllm/` source trees during development. In the published package, those become normal PyPI dependencies:

- `sssn`
- `lllm-core`

That gives you fast local co-development without changing the install experience for users.
