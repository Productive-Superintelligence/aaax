# AAAX Kernel — Design Note

> High-level architecture and protocol spec for the AAAX Agent OS Kernel.
> This document captures design intent and core abstractions for further implementation.

---

## 1. Overview

AAAX is a minimal exokernel for agent systems. It provides core protocols and protection mechanisms — nothing more. It does not dictate how agents think, plan, remember, or communicate. Those decisions belong to the LibOS layer.

AAAX is implemented as a **SSSN System** — a root System that manages a constellation of docked subsystems through capability-scoped channel access and action authorization. It is not a separate runtime. It is a specific, privileged System template that operates within the SSSN network.

### Architecture Stack

```
┌─────────────────────────────────────────────────┐
│  LLLM / other compatible libraries              │  ← LibOS
│  (swappable agent logic: tactics, prompts, etc) │
├─────────────────────────────────────────────────┤
│  AAAX                                           │  ← Exokernel
│  (minimal protocols, capability binding,        │
│   action gating, bootstrap)                     │
├─────────────────────────────────────────────────┤
│  SSSN                                           │  ← Network
│  (systems, channels, transport, discovery)      │
└─────────────────────────────────────────────────┘
```

The end-user experience is simple: a CLI/GUI that bootstraps an AAAX instance, loads a suite, and launches the agent constellation. From the user's perspective, it looks like `aaax launch config.toml` — the layering is invisible.

### Cardinal Application

The **AAAX Productive Suite (AAAX-PS)** is the first and flagship application built on the AAAX kernel. It covers societal analysis, scientific research, and operational coordination — functioning as the mind, body and phylogenetics of an autonomous productive system. The Productive Suite is developed simultaneously with the kernel but kept structurally independent: the kernel has zero imports from the suite, and the suite imports from the kernel. The suite's role is to stress-test all kernel mechanisms (reconfigurability, heterogeneous communication, governance) while the kernel remains application-agnostic. See the AAAX-PS Design Note for full specification.

### The Six Kernel Functions

AAAX provides exactly six functions. Each passes the test: **"if any docked system could do this itself, would things break?"**

```
AAAX Kernel provides:
├── 1. Constellation management    (dock, undock, registry)
├── 2. Capability management       (issue, validate, expire)
├── 3. Action gate                 (authorize side effects against policy)
├── 4. Module loading              (manifest verification, system creation, channel wiring)
├── 5. Revocation & lifecycle      (force-revoke, pause, resume, drain)
└── 6. Bootstrap                   (config-driven initialization, PID 1)
```

Everything else — monitoring, logging, scheduling, package management, visualization — can be built as docked Systems using the same primitives. If it can be done in user space, it must be done in user space.

### Design Principles

- **Exokernel-minimal.** AAAX only provides mechanisms that require a trusted authority. All policy lives in the LibOS.
- **Framework-agnostic.** AAAX does not assume LLLM. Any agent library that implements AAAX's protocols can dock with an AAAX instance.
- **SSSN-native.** AAAX is a System. Its abstractions (capabilities, action gates) are implemented as channel protocols, not a separate enforcement layer.
- **Opt-in governance.** SSSN is an open, decentralized network — an internet of AI. AAAX does not control who exists on the network. It controls what happens inside its own boundary. Docking with AAAX is a choice that gives systems managed guarantees.
- **Policy-neutral.** The kernel provides the action gate mechanism but does not prescribe what is allowed or denied. Whether a system can execute trades, send emails, move robot arms, or only produce reports is a policy decision configured per deployment — not a kernel constraint. The kernel enforces the policy; the application defines it.
- **Application-agnostic kernel, application-driven development.** The kernel is developed alongside its cardinal application (Productive Suite) to ensure protocols are practical. But every kernel mechanism must pass the "would a different application need this too?" test. If yes, it belongs in the kernel. If no, it belongs in the suite.

---

## 2. Relationship to SSSN and LLLM

### 2.1 SSSN — the Network

SSSN (Simple System of Systems Network) provides exactly two abstractions: **Systems** (autonomous nodes with lifecycle) and **Channels** (typed, secured, persistent message edges). It is designed as an open, decentralized network — anyone can publish systems, anyone can connect to public channels.

**Core primitives (validated from source):**

- **System lifecycle:** `setup()` → `RUNNING` (step loop at configurable tick rate) → `STOPPED`. Unhandled exceptions in `step()` are caught and logged — the loop never crashes on a single step failure.
- **Channel types:** PassthroughChannel (inline write), BroadcastChannel (fan-out), WorkQueueChannel (competing consumers with claim/ack/nack), MailboxChannel (per-recipient inbox), PeriodicChannel (active poll loop), DiscoveryChannel (service registry with TTL).
- **Six consumption methods:** `read()`, `write()`, `subscribe()`, `unsubscribe()`, `acknowledge()`, `nack()`. Plus three host operations: `clear()`, `evict()`, `remove()`.
- **Topology composition:** `add_subsystem(system, channels=[...])` explicitly wires channel access. **No auto-wiring** — every dependency is declared. A subsystem without explicit channel grants has zero channel access.
- **Transport:** `launch()` for in-process (all channels in-memory), `publish(host, port)` for HTTP (FastAPI + uvicorn). Same code, different deployment. Scale is a deployment decision.
- **Visibility:** Channels default to `Visibility.PRIVATE` (never exposed over HTTP). `Visibility.PUBLIC` channels are exposed when `publish()` is called.
- **Security:** Pluggable `ChannelSecurity` interface with three built-in implementations: `OpenSecurity` (development — everything allowed), `ACLSecurity` (role-based: read/write/admin hierarchy), `JWTChannelSecurity` (cryptographically signed tokens with per-channel scoping and expiry). Custom implementations plug in via a single constructor argument.
- **Message model:** `ChannelMessage` is a frozen Pydantic model with `id`, `timestamp`, `sender_id`, `content` (typed `MessageContent` subclass), plus optional `correlation_id`, `reply_to`, `recipient_id`, and `metadata`.
- **Backpressure:** Write buffer overflow (default 10k items) raises `RuntimeError` immediately.
- **Persistence:** Messages are append-only in `MessageStore`. Never removed by reads — only by explicit host operations (`clear`, `evict`, `remove`). Acts as a truth-log.

**SSSN is not part of the kernel. It is the environment the kernel operates in.** AAAX uses SSSN's primitives but does not extend them. AAAX's contribution is a specific *pattern* of system composition and a set of *protocols* implemented over channels.

**SSSN as the ROS-equivalent:** SSSN's System/Channel model closely mirrors ROS's Node/Topic model (see §3). The key difference is that SSSN is designed for AI agent networks rather than robotic hardware, with richer channel semantics (work queues, mailboxes, discovery) and built-in security.

### 2.2 LLLM — the First LibOS

LLLM (Low-Level Language Model) provides four abstractions: **Tactics** (programs that orchestrate agents), **Agents** (system prompt + model + call loop), **Prompts** (template + parser + tools + handlers), and **Dialogs** (per-agent forkable conversation state).

**Key properties (validated from source):**

- **Dialog isolation.** Each agent maintains its own dialog — a per-agent append-only, forkable message tree. No shared global state. Agents share *information* by passing content between them in the Tactic's `call()` method, not by sharing dialogs.
- **Tactic composability.** Different applications compose different Tactics. Tactics are stateless — each call spins up fresh agent instances. They can be subclassed, shared, and reused like library modules.
- **Package system.** `lllm.toml` manifest, namespaced resources (`my_pkg.prompts:research/system`), `lllm pkg install` for distribution. Multiple packages can declare dependencies on each other.
- **Explicit wiring.** No auto-wiring, no hidden LLM calls. Every dependency is visible. The framework is "low-level by default" — it stops at Tactic as its highest abstraction.
- **Proxy/sandbox system.** Tools are wrapped with rich metadata, documentation, and activation filtering. The proxy system enables composable, testable tool execution.
- **Replayable logging.** Every invocation recorded with enough information to recreate exact execution context — prompts, model arguments, tool results, costs.
- **SSSN integration.** LLLM's architecture overview explicitly states: "Higher-level orchestration — systems of systems, agent networks — is left to the application layer. For those patterns, see the SSSN framework." The two are designed as complementary layers.

**LLLM is the first LibOS, not the only one.** AAAX's protocols must be implementable by any compatible agent library.

### 2.3 Default LibOS and the Productive Suite

AAAX ships with a **default LibOS** in the same repository. This serves three purposes:

1. **Zero-config experience.** Users can `aaax launch` without separately installing a LibOS. The default provides sensible agent primitives out of the box.
2. **Reference implementation.** The default LibOS demonstrates how to implement AAAX's protocols (capability requests, action gate integration, module manifest format) — serving as documentation-by-example for anyone building a custom LibOS.
3. **Dogfooding.** Developing the kernel and a LibOS together ensures the protocol surface stays practical and minimal.

The default LibOS should be LLLM-based, providing a pre-wired Tactic that handles capability negotiation and action gate routing. It should be thin — a bridge between LLLM's abstractions and AAAX's protocols, not a framework of its own.

The **AAAX Productive Suite (AAAX-PS)** is the flagship application built on this default LibOS. It covers three branches: societal analysis (the mind), scientific research (the phylogenetics), and operations (the body — planning for IoT/robotics/CPS). The suite ships with **vanilla modules** (standard LLM-based reasoning, basic memory, simple tool integrations) that work immediately. **Advanced modules** based on peer-reviewed research (SocioDojo, Analytica, Genesys, AAPM, etc.) can be installed as drop-in replacements via the LLLM package system, dramatically improving quality for specific domains. The composition model is the same — vanilla and advanced modules implement the same interfaces and are interchangeable.

The suite and the kernel are developed simultaneously but maintained as structurally independent:
- The kernel has **zero imports** from the suite.
- The suite imports from the kernel.
- Every kernel mechanism must pass the "would a robotics/metaverse/creative application need this too?" test.
- Enforced by CI and a dedicated test (`test_non_ps.py`) that boots a kernel with zero PS involvement.

See the AAAX-PS Design Note for full specification.

### 2.4 OpenClaw — Dockable Application, Not a LibOS

OpenClaw is a popular open-source personal AI agent (160k+ GitHub stars) with a hub-and-spoke architecture: a Gateway (WebSocket server routing messages from WhatsApp/Telegram/Slack/etc.), a Brain (LLM-powered ReAct reasoning loop), Hands (tool execution — shell, browser, file system), Memory (persistent Markdown files), Skills (Markdown + YAML extension system), and a Heartbeat (scheduled proactive tasks). It runs as a single Node.js daemon.

**Can OpenClaw be wrapped as a LibOS?** No — and it shouldn't be. OpenClaw is an **end-user application**, not a development framework. It has strong opinions about its gateway architecture, memory format (Markdown files), skill system (SKILL.md), and deployment model (single daemon). A LibOS provides primitives that developers compose differently; OpenClaw provides a complete, opinionated agent runtime.

**Can OpenClaw be wrapped as a dockable System?** Yes — and this is the right integration path. An AAAX-OpenClaw adapter would:

- Wrap an OpenClaw instance as a SSSN System, exposing its Gateway's capabilities as SSSN channels.
- Route OpenClaw's tool execution through AAAX's action gate, so side-effecting operations are subject to AAAX's authorization policy.
- Register OpenClaw's skills as capabilities in AAAX's module registry, making them discoverable to other docked systems.
- Bridge OpenClaw's memory with SSSN channels, allowing other systems in the constellation to read/write shared context.

This adapter is not a priority for the initial implementation. It belongs in Phase 4 or as a community contribution.

### 2.5 Package Management Layering

Following Apple's macOS/iOS design pattern:

| Layer | macOS | AAAX Stack |
|---|---|---|
| **Package system** | `pkg/installer`, `brew` | LLLM (`lllm.toml`, `lllm pkg install`, dependency resolution) |
| **Trust boundary** | Gatekeeper (code signing, notarization) | AAAX module loader (manifest verification against policy at dock time) |
| **Marketplace** | App Store (user-space app) | Future marketplace app (a SSSN System or web service, not kernel) |

LLLM handles package format, installation, and dependency resolution. AAAX handles the trust boundary: when a module is loaded (from any source), AAAX verifies its manifest against policy before docking it. A future marketplace is a user-space application, not kernel code.

```bash
# LLLM handles packages (like brew/apt)
lllm pkg install psi.advanced:analytica       # Install files to disk
lllm pkg list                                  # List installed packages

# AAAX handles trust and runtime (like Gatekeeper + launchctl)
aaax modules list                              # What's currently docked
aaax modules load psi.advanced:analytica       # Verify → dock → issue capabilities
aaax modules unload analytica                  # Revoke → undock

# Convenience: both in one step
aaax install psi.advanced:analytica            # lllm pkg install + aaax modules load
```

---

## 3. ROS Design Influences

AAAX's architecture draws directly from the Robot Operating System (ROS/ROS 2). This section documents the specific design elements borrowed and how they map to the agent domain.

### 3.1 ROS Architecture Summary

ROS organizes software into a **graph of nodes** connected by **edges** (topics, services, actions):

- **Nodes:** Individual processes handling specific tasks (sensor driver, path planner, motor controller). Each node is independently deployable and crash-isolated.
- **Topics:** Named buses for asynchronous pub/sub messaging. Publishers and subscribers are anonymous to each other. The most common communication pattern.
- **Services:** Synchronous request-response for one-off operations (e.g., capture a single image, compute an inverse kinematics solution).
- **Actions:** Goal-oriented asynchronous operations with periodic feedback and cancellation (e.g., navigate to a waypoint). Unique to ROS 2.
- **ROS Master (ROS 1) / DDS Discovery (ROS 2):** Node registration and discovery. ROS 1 used a central master process; ROS 2 replaced this with decentralized DDS-based discovery, eliminating the single point of failure.
- **Parameter Server:** Shared key-value store for configuration (robot weight, sensor calibration, control gains).
- **Launch system:** Declarative configuration (XML in ROS 1, Python in ROS 2) for starting multiple nodes with parameters and remapped topic names.
- **Packages:** Reusable bundles of nodes, libraries, and configs. Thousands of community packages for SLAM, navigation, manipulation, etc. The fundamental unit of code organization.
- **Lifecycle nodes (ROS 2):** State machine for managed node lifecycle: Unconfigured → Inactive → Active → Finalized. Enables coordinated startup/shutdown of distributed systems.
- **QoS (ROS 2):** Quality of service profiles (reliability, durability, deadline, liveliness) inherited from DDS middleware. Sensor data can be best-effort while commands are reliable.
- **Message types (.msg / .idl):** Standard interface definitions enabling interoperability. Standard message packages (sensor_msgs, geometry_msgs, nav_msgs) allow components from different vendors to communicate.

### 3.2 Mapping to AAAX Stack

| ROS Concept | AAAX Stack Equivalent | Layer |
|---|---|---|
| **Node** | SSSN `BaseSystem` | SSSN |
| **Topic** (pub/sub) | SSSN `BroadcastChannel` | SSSN |
| **Service** (request/response) | SSSN `MailboxChannel` + `correlation_id` / `reply_to` | SSSN |
| **Action** (goal + feedback) | LLLM Tactic (goal-oriented, multi-step, cancellable) | LibOS |
| **ROS Master / DDS Discovery** | SSSN `DiscoveryChannel` + AAAX bootstrap registry | SSSN + AAAX |
| **Parameter Server** | SSSN `PassthroughChannel` as config store, or `lllm.toml` | SSSN / LibOS |
| **Launch system** | AAAX bootstrap config (`aaax.toml`) + `aaax launch` CLI | AAAX |
| **Packages** | LLLM packages (`lllm.toml`, `lllm pkg install`) | LibOS |
| **Lifecycle nodes** | SSSN System state machine (INIT → RUNNING → PAUSED → STOPPED) | SSSN |
| **QoS profiles** | SSSN channel configuration (retention policy, backpressure, period) | SSSN |
| **Message types** | SSSN `MessageContent` subclasses (typed Pydantic models) | SSSN |
| **roslaunch** | `aaax launch config.toml` | AAAX |

### 3.3 Key Differences from ROS

- **Non-deterministic compute.** ROS nodes wrap deterministic algorithms (PID controllers, SLAM, path planners). AAAX systems wrap LLM-based agents whose outputs are non-deterministic. This motivates the action gate — a protection mechanism ROS doesn't need because its nodes don't hallucinate.
- **Mutable "instruction set."** ROS drivers don't change the CPU's behavior. LLM prompting changes agent behavior through context. This motivates Dialog isolation (LLLM) and capability scoping (AAAX) — protection against context pollution.
- **Open network.** ROS typically runs on a local robot or a trusted cluster. SSSN is designed as a decentralized internet of AI. This motivates JWT-based channel security and AAAX's opt-in governance model.
- **Agent diversity.** ROS packages share standard message types (sensor_msgs, geometry_msgs) enabling interoperability. Agent systems have far less standardization — different apps need fundamentally different memory, planning, and reasoning strategies. This motivates the exokernel/LibOS split.
- **No central master.** ROS 1's central master was a single point of failure, addressed in ROS 2 with DDS discovery. SSSN starts decentralized, and AAAX is opt-in governance, not a required master.

---

## 4. Why a New Architecture

### The Problem

LLMs are volatile. Different agent applications require fundamentally different strategies for memory, planning, tool use, and reasoning. There is little in common between agents, making it hard to fix a universal set of component designs.

### Challenge 1: Instability

A CPU deterministically executes a fixed instruction set. An LLM non-deterministically executes arbitrary instructions. The same input can produce different outputs. Frameworks built around deterministic execution pipelines break in subtle ways — retry logic, state management, and error handling all need to account for non-determinism.

### Challenge 2: Side Effects

Programming on a CPU doesn't change the CPU's behavior. Programming an LLM — prompt engineering, fine-tuning, in-context learning — changes how it processes subsequent inputs. The "instruction set" is mutable. Context pollution, stale instructions leaking across tasks, and prompt interference are all manifestations of this — memory protection violations in disguise.

### The Solution

An exokernel / ROS-like architecture where:

- The kernel (AAAX) provides only core protocols and protection mechanisms.
- Agent-specific logic lives in swappable LibOS implementations (LLLM and others).
- Systems run as autonomous service nodes on a decentralized network (SSSN).
- Communication happens through typed channels with capability-scoped access.
- Components can be reconfigured as libraries (LibOS pattern), and run as service nodes using channels for communication.

---

## 5. AAAX as a SSSN System

AAAX is implemented as a SSSN `BaseSystem` — the root System of a managed constellation. It is not a daemon, not a separate process, not a layer below SSSN. It *is* a System, with `setup()`, `step()`, and the standard lifecycle.

### What AAAX Owns

AAAX owns a set of **private internal channels** that implement its kernel protocols. These channels are never exposed externally (using SSSN's `Visibility.PRIVATE` default). Docked subsystems interact with AAAX only through the protocol channels that AAAX explicitly wires to them via `add_subsystem()`.

```
AAAX (root System)
│
├── [PRIVATE] capability_registry    — tracks issued capabilities
├── [PRIVATE] module_registry        — tracks loaded modules and their manifests
├── [PRIVATE] policy_store           — authorization policies
│
├── [wired to subsystems] capability_request  — subsystems request access here
├── [wired to subsystems] action_gate         — subsystems submit actions here
├── [wired to subsystems] module_loader       — subsystems register modules here
├── [wired to subsystems] lifecycle           — revocation, pause, resume commands
├── [wired to subsystems] heartbeat           — liveness and topology awareness
│
└── Docked subsystems (each wired only to granted channels)
    ├── System A  (wired to: capability_request, action_gate, + granted channels)
    ├── System B  (wired to: capability_request, action_gate, + granted channels)
    └── System C  (wired to: capability_request, action_gate, + granted channels)
```

### Protection Model

Protection comes from three mechanisms, all native to SSSN:

1. **Channel visibility.** AAAX's internal registries use `Visibility.PRIVATE`. They are never exposed over HTTP and never accessible to subsystems.

2. **Topology control.** `add_subsystem(system, channels=[...])` explicitly scopes what each subsystem can see. A docked system cannot reference a channel it wasn't given.

3. **Capability tokens.** Channel access beyond the initial wiring requires a capability — requested through AAAX's `capability_request` channel, evaluated against policy, and issued as a scoped token. Builds on SSSN's `JWTChannelSecurity` with application-level capability semantics.

### AAAX on the Open Network

SSSN is designed as an open, decentralized network — an internet of AI. Anyone can publish systems, anyone can connect. AAAX does not control who exists on the network. External systems — other AAAX instances, standalone services, OpenClaw instances, anything — can connect to AAAX's published public channels if AAAX chooses to `publish()` them.

AAAX instances can federate: one AAAX constellation talks to another through SSSN's standard HTTP transport, each managing its own internal subsystems independently.

---

## 6. Core Protocols

AAAX's protocol surface is the set of interactions that docked systems use to operate within the managed environment. These are implemented as message schemas on AAAX-owned channels.

### 6.1 Capability Binding

**Purpose:** A docked system requests access to a resource (a channel, a tool, an external service). AAAX evaluates policy and either grants a scoped capability or rejects.

**Channel:** `capability_request` (WorkQueueChannel — each request claimed and processed once by AAAX)

**Request → AAAX:**

```yaml
type: capability_request
from: system-id
resource: channel-id | tool-id | service-id
access: read | write | execute
scope: {}          # optional constraints (TTL, rate limit, etc.)
context: {}        # optional justification or task context
```

**AAAX → Response (via MailboxChannel or reply_to):**

```yaml
type: capability_grant | capability_deny
resource: channel-id | tool-id | service-id
token: <opaque capability token>   # if granted
expires: <timestamp>               # if granted
reason: <string>                   # if denied
```

**Design notes:**

- Capabilities are time-scoped by default. No permanent grants.
- AAAX evaluates requests against its `policy_store`. The policy evaluation itself may be a LLLM Tactic or a simple rule engine — this is configurable.
- Builds on SSSN's `JWTChannelSecurity.generate_token()` for cryptographic token issuance.

### 6.2 Action Authorization

**Purpose:** A docked system wants to perform a side-effecting operation — call an external API, write to a database, send a message, actuate hardware. Instead of executing directly, it submits the action to AAAX for authorization.

**Channel:** `action_gate` (WorkQueueChannel — sequential processing, exactly-once semantics)

The action gate is **policy-neutral**: it provides the mechanism (risk-level classification, escalation routing, capability verification) but the policy is defined per deployment. A financial analysis deployment might block trade execution. A robotics deployment might allow actuator commands but require human approval for irreversible actions. A research deployment might allow arbitrary code execution within a sandbox. The kernel doesn't care — it enforces whatever policy the application configures.

**Request → AAAX:**

```yaml
type: action_request
from: system-id
action: tool-call | api-call | actuator-command
target: <tool-id or endpoint>
payload: {}
capability: <token>
risk_level: low | medium | high | irreversible
```

**AAAX → Response:**

```yaml
type: action_approved | action_denied | action_escalated
request_id: <id>
reason: <string>
modified_payload: {}   # AAAX may constrain parameters
escalated_to: <system-id>  # if supervisor review needed
```

**Risk levels:**

| Risk Level | Behavior (configurable per deployment) |
|---|---|
| `low` | Auto-approve if capability is valid |
| `medium` | Policy check — may auto-approve or deny |
| `high` | Require explicit policy match or escalation |
| `irreversible` | Default: escalate to supervisor or human-in-the-loop |

### 6.3 Module Loading

**Purpose:** A LibOS implementation registers itself with AAAX, declaring its capabilities and required resources. This is AAAX's **Gatekeeper** — the trust boundary for loading modules, regardless of where the module came from.

**Channel:** `module_loader` (WorkQueueChannel)

**Request → AAAX:**

```yaml
type: module_register
module_id: <namespaced id>       # e.g., "lllm.tactics:research_writer"
framework: lllm | custom | <any>
manifest:
  requires_channels: [...]
  requires_tools: [...]
  provides_channels: [...]
  provides_services: [...]
  risk_profile: <low|medium|high>
```

**AAAX → Response:**

```yaml
type: module_accepted | module_rejected
module_id: <id>
granted_capabilities: [...]
system_id: <assigned system id>
reason: <string>  # if rejected
```

**Design notes:**

- The manifest format is framework-agnostic. LLLM packages use `lllm.toml`; the default LibOS translates this to AAAX's manifest format. Other frameworks provide their own translators.
- Module loading includes creating the SSSN System, wiring it to granted channels via `add_subsystem()`, and starting its lifecycle.
- When a module is accepted, AAAX pre-issues capabilities for what the manifest declared. Additional capabilities can be requested at runtime through the capability protocol.

### 6.4 Revocation and Lifecycle

**Purpose:** Complete the governance loop. Without revocation, a misbehaving system keeps its capabilities until they expire naturally. Without lifecycle transitions, you can only fully start or fully stop a subsystem. This is Aegis's visible revocation + abort protocol mapped to agent systems.

**Channel:** `lifecycle` (WorkQueueChannel)

**Commands:**

- **`revoke`** — Force-revoke all capabilities for a system (Aegis abort protocol). The system loses all access immediately.
- **`pause`** — Suspend a docked subsystem. It remains docked but stops processing.
- **`resume`** — Resume a paused subsystem.
- **`drain`** — Gracefully wind down a subsystem (finish current work, then stop). Used before undocking.

**Kernel methods:**

```python
await kernel.revoke(system_id)              # Force-revoke all capabilities
await kernel.pause(system_id)               # Suspend processing
await kernel.resume(system_id)              # Resume processing
await kernel.drain(system_id, timeout=30)   # Graceful shutdown → undock
```

### 6.5 Bootstrap

Bootstrap is the initialization sequence that runs before any protocol channels exist.

**Sequence:**

```
1. Instantiate AAAX as a BaseSystem
2. setup():
   a. Create internal private channels (capability_registry, module_registry, policy_store)
   b. Create protocol channels (capability_request, action_gate, module_loader, lifecycle, heartbeat)
   c. Load bootstrap policy (from config file or default)
   d. Load default LibOS
   e. Load initial modules from config:
      validate manifest → create subsystem → wire channels → issue capabilities
   f. Register with DiscoveryChannel if publishing to network
3. launch() or publish()
4. step() loop:
   a. Process capability_request queue
   b. Process action_gate queue
   c. Process module_loader queue
   d. Process lifecycle queue
   e. Heartbeat / liveness checks
   f. Capability expiry and revocation
```

**Bootstrap config:**

```toml
[aaax]
id = "aaax-main"
name = "AAAX Kernel Instance"
policy = "default"

[aaax.libos]
framework = "lllm"
# Uses the default LibOS shipped with AAAX

[[aaax.modules]]
id = "my-agent"
framework = "lllm"
channels = ["task-input", "output-feed"]

[aaax.network]
publish = true
host = "0.0.0.0"
port = 8100
```

**CLI:**

```bash
# Launch with config
aaax launch config.toml

# Launch with defaults (default LibOS, no modules, local only)
aaax launch

# Launch and publish to network
aaax launch config.toml --publish
```

---

## 7. OS Concept Mapping

How traditional OS kernel responsibilities map to this architecture:

| OS Kernel | AAAX Stack Equivalent | Layer |
|---|---|---|
| Memory Management | Context window allocation, persistent state, RAG policy | LibOS |
| Process Management | System lifecycle, subsystem spawning, module loading | AAAX + SSSN |
| I/O Devices | Tool calls, sensor streams, actuator commands | LibOS + Action Gate |
| VFS / File Systems | Unified interface over heterogeneous knowledge sources | LibOS |
| IPC | SSSN Channels (broadcast, work queue, mailbox, pub/sub) | SSSN |
| Networking | SSSN transport (in-process + HTTP), federation | SSSN |
| Security | Capability binding, action authorization, topology isolation | AAAX |
| Virtualization | Framework-agnostic module loading, LibOS abstraction | AAAX |

---

## 8. Compatibility with Existing Ecosystem

AAAX is not being built in a vacuum. The AI agent ecosystem in 2026 includes personal assistants (OpenClaw), research agents (AI Scientist, AlphaEvolve), multi-agent orchestration frameworks (LangGraph, CrewAI, AutoGen), and emerging interoperability standards (MCP, A2A). This section maps how each relates to AAAX and what integration looks like.

### 8.1 Integration Model

The key insight is that AAAX operates at a different layer than most existing tools. Agent frameworks (LangGraph, CrewAI, etc.) are LibOS-level — they define how agents think, plan, and coordinate. AAAX is kernel-level — it provides the protection and communication substrate beneath them. This means AAAX doesn't compete with these frameworks. It hosts them.

There are three integration patterns:

- **As a LibOS.** The framework is used directly to build agents that dock with AAAX. Its abstractions become the agent programming model inside AAAX's managed environment. LLLM is the primary example.
- **As a dockable application.** A pre-built agent system is wrapped as a SSSN System and docked into an AAAX constellation, gaining governance guarantees without restructuring its internals. OpenClaw is the primary example.
- **As a protocol peer.** External systems communicate with AAAX-managed systems through standardized protocols (SSSN channels, MCP, A2A) without docking at all. They remain independent on the open network.

### 8.2 OpenClaw — Personal AI Assistant

**What it is:** An open-source personal AI agent (160k+ GitHub stars) running as a local Node.js daemon. Hub-and-spoke architecture: Gateway (WebSocket routing across WhatsApp/Telegram/Slack/etc.), Brain (ReAct reasoning loop), Hands (tool execution), Memory (persistent Markdown files), Skills (Markdown + YAML extensions), Heartbeat (scheduled proactive tasks).

**Integration pattern:** Dockable application. OpenClaw is too opinionated to serve as a LibOS (fixed gateway model, Markdown memory, Node.js runtime), but it represents the exact kind of end-user agent that should benefit from AAAX's governance.

**What AAAX provides to OpenClaw:**

- Tool execution routed through AAAX's action gate — so OpenClaw's shell commands, browser automation, and email sending are subject to authorization policy. This directly addresses OpenClaw's well-documented security concerns (CVE-2026-25253, prompt injection risks, unvetted community skills).
- Capability-scoped access to other systems in the constellation — an OpenClaw instance could request data from a research agent or delegate tasks to a coding agent, with AAAX managing the trust boundary.
- Federation — multiple OpenClaw instances (e.g., for different team members) can coordinate through AAAX-managed channels rather than ad-hoc peer-to-peer connections.

**Implementation:** AAAX-OpenClaw adapter wrapping the Gateway as a SSSN System. Phase 4 priority or community contribution.

### 8.3 AI Scientist (Sakana AI) — Automated Research Agent

**What it is:** An end-to-end automated scientific discovery system (published in Nature, 2025). Given a research direction, it autonomously generates ideas, searches literature, designs and runs experiments (via agentic tree search with parallel execution), generates figures, writes full LaTeX papers, and self-reviews. V2 produced the first fully AI-generated paper accepted through peer review at ICLR 2025.

**Integration pattern:** Dockable application or LibOS (depending on depth of integration).

**Why it fits AAAX well:** AI Scientist is a multi-stage pipeline with high-risk side effects: it executes arbitrary code, runs GPU experiments, writes files, and can consume unbounded compute. These are exactly the operations AAAX's action gate is designed to govern. Its 42% experiment failure rate (per independent evaluation) further motivates sandboxing and governance.

**What AAAX provides to AI Scientist:**

- Action gating on experiment execution — AAAX can enforce compute budgets, sandbox code execution, and require approval for resource-intensive experiments.
- Module loading for the multi-agent pipeline — the idea generator, experiment runner, paper writer, and reviewer can each be separate docked systems with scoped capabilities, rather than a monolithic script.
- Capability-scoped access to external resources — literature search APIs, GPU clusters, LaTeX compilation — each requiring explicit capability grants.
- Audit trail — every experiment run, every code execution, every paper generation tracked through AAAX's channel history, supporting reproducibility.

**Implementation:** A LLLM Tactic wrapping AI Scientist's pipeline stages, with each stage as a docked module. Or an adapter wrapping the existing Python codebase as a SSSN System. Medium-term priority — strong showcase for AAAX's value proposition.

### 8.4 AlphaEvolve / OpenEvolve — Evolutionary Algorithm Discovery

**What it is:** Google DeepMind's evolutionary coding agent (May 2025). Uses an ensemble of LLMs (Gemini Flash for breadth, Gemini Pro for depth) to generate, mutate, and evolve code through an automated evaluation loop. Maintains a versioned database of candidate programs. Has discovered novel matrix multiplication algorithms (breaking a 56-year record), optimized data center scheduling (recovering 0.7% of Google's global compute), improved TPU circuit design, and sped up Gemini training by 1%. OpenEvolve is an open-source reimplementation.

**Integration pattern:** LibOS-level (the evolutionary loop as a Tactic) or dockable application (wrapping OpenEvolve).

**Why it fits AAAX well:** AlphaEvolve's architecture is naturally decomposable into AAAX's model:

- The **prompt sampler** and **LLM ensemble** are agent-level concerns (LibOS).
- The **evaluation sandbox** needs isolated, metered compute — a kernel concern (AAAX action gate + inference gate).
- The **program database** (versioned candidates) maps to a SSSN channel (append-only message store with eviction policy).
- The **evolutionary controller** is orchestration logic (LLLM Tactic or SSSN System step loop).

**What AAAX provides to AlphaEvolve/OpenEvolve:**

- Sandboxed evaluation — each candidate program runs through the action gate, preventing malicious or runaway code from escaping the evaluation environment.
- Compute budget enforcement — evolutionary search can consume unbounded resources; AAAX's optional inference gate meters LLM calls and the action gate can enforce evaluation time limits.
- Distributed evolution — multiple AAAX instances running parallel evolutionary populations, federating through SSSN channels, with the best candidates shared across instances.

### 8.5 Multi-Agent Frameworks (LangGraph, CrewAI, AutoGen)

**What they are:** The dominant agent orchestration frameworks in 2026. LangGraph (LangChain, 47M+ PyPI downloads) models workflows as stateful directed graphs with checkpointing. CrewAI uses role-based agent teams with task delegation. AutoGen/Microsoft Agent Framework uses conversational multi-agent patterns (GroupChat). All are Python-first, model-agnostic, and increasingly production-grade.

**Integration pattern:** LibOS-level — these frameworks would serve as alternative LibOS implementations alongside LLLM.

**Key observation:** These frameworks all solve the same problem LLLM solves — agent orchestration, tool calling, state management, multi-agent coordination. They differ in programming model (graphs vs. roles vs. conversations) but are all LibOS-level concerns. AAAX doesn't need to pick one. It provides the kernel beneath all of them.

**What integration looks like:**

- A **LangGraph adapter** would translate LangGraph's graph-based state machine into a SSSN System, with graph nodes mapping to channel-connected subsystems and checkpoints mapping to channel message history.
- A **CrewAI adapter** would map Crew roles to AAAX modules with scoped capabilities — an agent with the "researcher" role gets read access to search channels but not write access to output channels.
- An **AutoGen adapter** would map GroupChat participants to docked SSSN Systems communicating through a BroadcastChannel.

**What AAAX provides that these frameworks lack natively:**

- Cross-framework interoperability — a LangGraph agent and a CrewAI agent can coexist in the same AAAX constellation, communicating through SSSN channels, without either framework knowing about the other.
- Governance across frameworks — action gating, capability scoping, and audit trails apply uniformly regardless of which LibOS produced the action.
- Network-level coordination — these frameworks are designed for single-process or single-machine deployment. AAAX + SSSN extends them to distributed, federated agent networks.

### 8.6 MCP and A2A Protocol Standards

**MCP** (Model Context Protocol, Anthropic) is an open standard for connecting agents to tools and data sources — often described as "the USB-C of agent tool integration." All major frameworks are adopting it in 2026. **A2A** (Agent-to-Agent Protocol, Google) enables agents from different frameworks to discover and invoke each other through standardized task interfaces.

**Relationship to AAAX:**

- **MCP** operates at the tool-connection layer — how an agent accesses a specific tool. AAAX operates at the governance layer — whether the agent is *allowed* to access that tool. These are complementary. MCP tools can be registered in AAAX's module registry as capabilities requiring explicit grants. An AAAX action gate checks capability tokens before MCP tool calls execute.
- **A2A** operates at the agent-discovery and inter-agent communication layer. SSSN's DiscoveryChannel and typed channels serve a similar purpose within the AAAX ecosystem. For communication with external A2A agents, a bridge adapter translates between A2A task interfaces and SSSN channel messages. This is a federation concern (Phase 4).

**Design principle:** AAAX should not reinvent these standards. Where MCP and A2A are adopted, AAAX provides the governance layer on top of them.

### 8.7 Summary Matrix

| System | Type | Integration Pattern | AAAX Value Add | Priority |
|---|---|---|---|---|
| **LLLM** | Agent framework | Primary LibOS | Native integration, default LibOS | Phase 1 |
| **OpenClaw** | Personal assistant | Dockable application | Action gating, security governance | Phase 4 |
| **AI Scientist** | Research agent | Dockable app / LibOS | Compute budgeting, experiment sandboxing, audit | Phase 3-4 |
| **AlphaEvolve/OpenEvolve** | Evolutionary search | LibOS / Dockable app | Evaluation sandboxing, distributed evolution | Phase 3-4 |
| **LangGraph** | Orchestration framework | Alternative LibOS | Cross-framework interop, governance | Phase 2 |
| **CrewAI** | Orchestration framework | Alternative LibOS | Capability-scoped roles, governance | Phase 2 |
| **AutoGen** | Orchestration framework | Alternative LibOS | Cross-framework interop, governance | Phase 2 |
| **MCP** | Tool protocol standard | Protocol bridge | Governance layer over tool access | Phase 2-3 |
| **A2A** | Agent protocol standard | Protocol bridge | Governance layer over agent discovery | Phase 4 |

---

## 9. Open Design Questions

### 9.1 Capability Enforcement Mechanism

Capabilities are *issued* by AAAX, but how are they *checked*?

- **Option A: Channel middleware.** Extend SSSN's `ChannelSecurity` interface with an AAAX-aware implementation that validates capability tokens on every read/write. Reuses existing infrastructure.
- **Option B: Honor system with audit.** Docked systems present capabilities; AAAX logs compliance. Weaker but simpler.
- **Option C: Proxy channels.** Docked systems get proxy objects that check capabilities on every operation. Aligns with LLLM's proxy pattern.

Recommendation: Start with **Option A** — it reuses SSSN's pluggable security and enforces at the channel level.

### 9.2 Policy Representation

- **Simple rules:** TOML/YAML config mapping system IDs to allowed resources and risk levels. Static, auditable, fast.
- **Tactic-as-policy:** A LLLM Tactic that evaluates requests dynamically. Powerful but introduces non-determinism into the kernel.
- **Hybrid:** Simple rules for fast-path, Tactic escalation for ambiguous cases.

AAAX should define the policy *interface* and let the implementation be pluggable. Default: simple rules. Tactic-as-policy is an advanced opt-in.

### 9.3 Inference Gating

Should AAAX meter and dispatch LLM inference calls?

- **For:** Inference is the primary compute resource. Budget enforcement prevents runaway agents.
- **Against:** If AAAX is truly minimal, metering belongs in the LibOS. LLLM already tracks costs.
- **Compromise:** Optional `inference_gate` channel. Opt-in, consistent with the overall philosophy.

### 9.4 Multi-AAAX Federation

Defer to a later design phase. Open questions: cross-instance capability trust, negotiation protocol, multi-docking.

### 9.5 Graceful Degradation

Capabilities are tokens, not live connections. A subsystem with a valid, unexpired capability continues operating even if AAAX is temporarily unavailable. New requests block until recovery. Follows the Aegis precedent: secure bindings outlive the kernel's active involvement.

---

## 10. Implementation Roadmap

### Phase 1: Core Skeleton

- Implement AAAX as a `BaseSystem` subclass with all six kernel functions
- Implement internal private channels (capability_registry, policy_store)
- Implement protocol channels (capability_request, action_gate, module_loader, lifecycle, heartbeat)
- Implement bootstrap sequence from TOML config
- Basic policy: static rule-based allow/deny
- **Ship default LibOS** (thin LLLM bridge with capability negotiation)
- CLI: `aaax launch config.toml`, `aaax modules list/load/unload`
- Test: dock two simple Systems, demonstrate capability-scoped channel access
- Begin Productive Suite co-development (validate kernel protocols)

### Phase 2: LibOS Integration

- Implement LLLM module adapter (translate `lllm.toml` → AAAX module manifest)
- Implement generic module adapter interface for non-LLLM frameworks
- Demonstrate a LLLM Tactic running as a docked AAAX subsystem
- PS: first working multi-expert constellation with vanilla modules
- Test: multi-module constellation with heterogeneous LibOS implementations

### Phase 3: Action Gating

- Implement risk-level classification
- Implement escalation routing (supervisor system, human-in-the-loop channel)
- Integrate with LLLM proxy/sandbox system for tool execution
- PS: action gate integration with domain-appropriate policies
- Test: agent attempts side-effecting action, AAAX gates and authorizes

### Phase 4: Network and Federation

- Publish AAAX protocol channels over SSSN HTTP transport
- Implement external docking (remote system registers with AAAX over network)
- Implement wrapper/adapter for external applications (e.g., OpenClaw adapter)
- Explore cross-AAAX federation protocol

### Phase 5: Hardening

- Resolve capability enforcement mechanism (§9.1)
- Implement capability expiry and revocation
- Implement graceful degradation (§9.5)
- Lifecycle governance: pause, resume, drain under adversarial conditions
- Stress testing: adversarial subsystems, capability exhaustion, network partition

---

## Appendix A: Terminology

| Term | Definition |
|---|---|
| **AAAX** | Agent OS exokernel. A minimal SSSN System providing six kernel functions: constellation management, capability management, action gate, module loading, revocation/lifecycle, and bootstrap. |
| **LibOS** | A swappable agent logic layer. LLLM is the first LibOS. Any framework implementing AAAX's protocols qualifies. |
| **Default LibOS** | The LLLM-based LibOS shipped with AAAX for zero-config usage and as a reference implementation. |
| **SSSN** | Simple System of Systems Network. The decentralized network of Systems and Channels that AAAX operates within. |
| **AAAX-PS** | AAAX Productive Suite. The flagship application — a configurable multi-role system for societal analysis, scientific research, and operational coordination. Developed simultaneously with the kernel but structurally independent. |
| **Docking** | The act of a System registering with an AAAX instance and accepting its governance. |
| **Capability** | A scoped, time-limited token granting access to a specific resource (channel, tool, service). |
| **Action Gate** | The AAAX protocol through which side-effecting operations are submitted for policy-configurable authorization. |
| **Module** | A LibOS unit (e.g., a LLLM package) loaded into an AAAX instance as a docked subsystem. |
| **Bootstrap** | The initialization sequence that creates AAAX's channels, loads policy, loads the default LibOS, and docks initial modules. |

## Appendix B: Influences

| Influence | What AAAX Borrows |
|---|---|
| **Exokernel / Aegis** (Engler et al., MIT) | Minimal kernel, secure bindings (bind-time check → access-time verify), visible revocation, abort protocol, LibOS pattern. The kernel multiplexes resources safely; all policy lives in the LibOS. |
| **ROS / ROS 2** (Open Robotics) | Node/topic model → SSSN System/Channel. Launch system → AAAX bootstrap. Lifecycle nodes → SSSN state machine. Package system → LLLM packages. DDS discovery → SSSN DiscoveryChannel. QoS → SSSN channel config. Message types → SSSN MessageContent. |
| **Capability-based security** (seL4, EROS, KeyKOS) | Capability tokens as the sole access control mechanism. No ambient authority — a system can only access resources for which it holds a valid capability. |
| **Microkernel** (L4, Mach, QNX) | Services in user space, IPC as the core primitive. Crash isolation — a failing subsystem doesn't take down the kernel. |
| **macOS Gatekeeper** | Trust verification at load time (manifest verification against policy), separate from the package system (LLLM) and the marketplace (future user-space app). |
| **OpenClaw** | Demonstrates the end-user experience AAAX should enable: simple CLI launch, persistent agent with memory and skills, multi-channel access. AAAX provides the governed infrastructure beneath applications like OpenClaw. |

## Appendix C: References

- D. R. Engler, M. F. Kaashoek, J. O'Toole Jr. "Exokernel: An Operating System Architecture for Application-Level Resource Management." SOSP 1995.
- S. Macenski, T. Foote, B. Gerkey, C. Lalancette, W. Woodall. "Robot Operating System 2: Design, Architecture, and Uses in the Wild." Science Robotics, vol. 7, May 2022. https://doi.org/10.1126/scirobotics.abm6074
- ROS 2 Design Documentation. https://design.ros2.org/
- ROS Wiki — Concepts. https://wiki.ros.org/ROS/Concepts
- G. Klein et al. "seL4: Formal Verification of an OS Kernel." SOSP 2009.
- SSSN Documentation. https://sssn.one/
- LLLM Documentation. https://lllm.one/
- LLLM GitHub. https://github.com/Productive-Superintelligence/lllm
- SSSN GitHub. https://github.com/Productive-Superintelligence/sssn
- OpenClaw Documentation. https://docs.openclaw.ai/
- OpenClaw Architecture Overview. https://ppaolo.substack.com/p/openclaw-system-architecture-overview
- AAAX-PS Design Note. (companion document)