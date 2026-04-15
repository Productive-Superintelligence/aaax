# Module Loading

AAAX module loading is deliberately narrow at this stage. The loader accepts a manifest, checks it against policy, creates a system, docks it, and grants any initial mediated capabilities.

## Two input paths

- static boot config through `AAAXConfig.modules`
- runtime protocol requests through `aaax.module-loader`

Both end up in the same `ModuleLoader`.

## Manifest shape

Derived manifests currently include:

- `module_id`
- `framework`
- `lllm_toml`
- `requires_channels`
- `requires_executors`
- `requires_remote_channels`
- `provides_channels`
- `risk_profile`

If you need full control, you can pass `manifest` directly in `ModuleConfig`.

## Current system types

### PlaceholderSystem

Used for non-LLLM modules when you want docking behavior without a concrete LibOS adapter yet.

### TacticSystem

Used for `framework = "lllm"` modules. The system:

- requires a `lllm_toml`
- builds a runtime through the default LibOS bridge
- becomes the basis for future tactic execution work

## Docking behavior

Every module receives the common protocol channels:

- `aaax.capability-request`
- `aaax.action-gate`
- `aaax.kernel-replies`
- `aaax.heartbeat`

Privileged systems may also receive:

- `aaax.module-loader`
- `aaax.lifecycle`

Requested local channels are wired in addition to those protocol channels.

## Initial capability grants

The loader automatically grants mediated capabilities for:

- requested executors as `execute`
- requested remote channels as `read`

That means local channel wiring and mediated remote/executor access stay clearly separated.
