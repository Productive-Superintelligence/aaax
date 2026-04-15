# Kernel Functions

The kernel implementation maps directly to six responsibilities.

## 1. Constellation management

`AAAXKernel.dock()` and `AAAXKernel.undock()` manage the living constellation of docked systems. The kernel wires:

- common protocol channels for all docked systems
- optional requested local channels
- privileged protocol channels for trusted systems
- subsystem-owned channels back into the kernel client

The `ConstellationManager` tracks which systems are present, which wiring they received, and their status.

## 2. Capability issuance

The `CapabilityManager` issues AAAX-local tokens for mediated resources. A capability request arrives on `aaax.capability-request`, is evaluated by policy, and, if allowed, becomes a token bound to:

- `system_id`
- `resource`
- `access`
- `expires_at`

These are not meant to replace SSSN topology wiring. They are meant to govern resources AAAX mediates.

## 3. Action authorization

The `ActionGate` processes messages on `aaax.action-gate`. It requires a valid execute capability and then classifies the request through policy:

- approve
- deny
- escalate

This makes AAAX the policy checkpoint for side-effecting operations routed through AAAX-owned executors.

## 4. Module loading

The `ModuleLoader` turns config or protocol manifests into docked systems. For now it supports:

- placeholder systems for non-LLLM modules
- LLLM-backed `TacticSystem` modules through the default LibOS bridge

Initial executor and remote-channel capabilities are issued during module docking.

## 5. Lifecycle control

The `LifecycleManager` handles:

- `revoke`
- `pause`
- `resume`
- `drain`

These are cooperative semantics aligned with current SSSN behavior. `pause()` and `resume()` are marker-style controls unless the underlying system implements stronger behavior.

## 6. Bootstrap

Bootstrap creates the kernel-owned governance channels and the default LibOS:

- internal registry channels
- capability request queue
- action gate queue
- module loader queue
- lifecycle queue
- kernel reply mailbox
- heartbeat broadcast

This is what `bootstrap_kernel()` gives you as the stable starting point for applications.
