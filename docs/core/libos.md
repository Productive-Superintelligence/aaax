# LibOS Bridge

AAAX treats LLLM as the default LibOS. The bridge is intentionally thin and AAAX-owned.

## DefaultLibOS

`DefaultLibOS` is responsible for one thing: building an LLLM runtime under AAAX’s boot policy.

The bridge currently:

- sets `LLLM_AUTO_INIT=0` by default
- calls `lllm.load_runtime(...)`
- uses `strict_boot` to disable ambient cwd discovery
- optionally allows shared package discovery when configured

## Why strict boot matters

AAAX wants deterministic kernel boot. Ambient auto-discovery is convenient for standalone experiments, but it is the wrong default for a governed kernel that is supposed to know exactly which modules it is loading.

## TacticSystem

`TacticSystem` is the current SSSN wrapper around an LLLM runtime:

- it owns an AAAX module ID
- it loads its `lllm.toml` during `setup()`
- it is the seam where future tactic invocation will be attached

The current implementation is intentionally minimal because the kernel contract matters more than prematurely committing to an execution model.

## Future direction

This bridge is the place to add:

- explicit tactic invocation routing
- AAAX-owned executor mediation
- better runtime lifecycle integration
- adapter support for additional LibOS choices

## Runtime model

AAAX does not run as a detached kernel with the application somewhere else. In the current model, the kernel, the default LibOS bridge, and the docked application systems run together as one AAAX constellation.

When `AAAXKernel.publish(...)` is called, AAAX starts that runtime and attaches HTTP transport to `PUBLIC` channels. What becomes visible on the network are those channels, not “the kernel” as a separate published artifact.
