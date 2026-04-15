# AAAX — Implementation Note

> Project structure, code organization, and engineering guide.
> Companion to the AAAX Kernel Design Note and AAAX-PS Design Note.

---

## 1. What AAAX Actually Is

### 1.1 The One-Sentence Answer

**AAAX is a managed umbrella System.** It wraps SSSN's raw Systems and Channels into a governed constellation — handling registration, topology-scoped local wiring, mediated capability binding, side-effect routing, and lifecycle for everything inside it.

### 1.2 Without AAAX vs. With AAAX

Without AAAX, you use SSSN directly:
- Manually create Systems
- Manually create Channels
- Manually call `add_subsystem(system, channels=[...])`
- Manually implement access control per channel
- Manually manage lifecycle, restart, and coordination
- Write custom bootstrap scripts per deployment

With AAAX:
```python
kernel = AAAXKernel(config)
await kernel.setup()             # Creates all governance channels
    await kernel.dock(my_system)     # Registers, wires, grants mediated capabilities
await kernel.launch()            # Starts everything
```

One TOML file describes an entire constellation. `aaax launch config.toml` and it's running.

**The analogy:** SSSN gives you building materials (Systems and Channels). AAAX is the construction manager that takes a blueprint (config.toml) and builds the thing — with governance, dynamic loading, and managed lifecycle.

### 1.3 The Six Kernel Functions

Everything AAAX provides passes one test: **"if any docked system could do this itself, would things break?"** If yes, it's a kernel function. If no, it belongs in user space.

| # | Function | Why it must be in the kernel |
|---|---|---|
| **1** | **Constellation management** | A system would dock unauthorized members. Someone must control who exists in the constellation. |
| **2** | **Capability management** | A system would grant itself unlimited access. Someone must be the access authority. |
| **3** | **Action gate** | A system would bypass safety restrictions. Someone must checkpoint side effects. |
| **4** | **Module loading with verification** | A system would load unverified modules. Someone must check manifests against policy. |
| **5** | **Revocation and lifecycle** | A misbehaving system wouldn't revoke its own access. Someone must be able to force-revoke, pause, resume, and drain. |
| **6** | **Bootstrap** | Someone has to be PID 1 — read the config, create the constellation, start everything. |

**What is NOT in the kernel:**

| Function | Why it's user space |
|---|---|
| Package format and installation | File management — any system can do it. LLLM handles this. |
| Package discovery / marketplace | A browsable catalog is an application, not a kernel function. |
| Monitoring dashboard | Just reading heartbeat channels. Build it as a docked System. |
| Logging and audit | Reading channel history. A user-space concern. |
| Scheduling / prioritization | Each system controls its own tick rate. |
| Domain-specific reasoning | The entire point of the LibOS split. |

### 1.4 Comparison with ROS and Exokernel

| | ROS (roscore/DDS) | Aegis (Exokernel) | AAAX |
|---|---|---|---|
| **Core function** | Discovery + Communication + Config | Secure bindings + Revocation + Abort | Constellation + Capabilities + Action gate + Module loading + Revocation + Bootstrap |
| **Everything else** | User-space packages | LibOS | LibOS (LLLM) + Productive Suite |
| **Design test** | "Can a node do this?" | "Can a LibOS do this?" | "Can a docked system do this safely?" |
| **Unique to AAAX** | — | — | Action gate (LLM agents hallucinate and act autonomously — ROS nodes and traditional programs don't) |

### 1.5 Package Management Layering

Following Apple's macOS/iOS design:

| Layer | macOS | AAAX Stack |
|---|---|---|
| **Package system** | `pkg/installer`, `brew` | LLLM (`lllm.toml`, `lllm pkg install`, shared package dirs, dependency resolution) |
| **Trust boundary** | Gatekeeper (code signing, notarization check) | AAAX module loader (manifest verification against policy at dock time) |
| **App Store** | App Store app (discovery, browsing, reviews) | Future marketplace app (a SSSN System or web service, not kernel) |

```bash
# LLLM handles packages (like brew/apt)
lllm pkg install ./releases/analytica.zip --scope project
lllm pkg list                                  # List installed packages
lllm pkg export analytica ./releases/analytica-v1.zip

# AAAX handles trust and runtime (like Gatekeeper + launchctl)
aaax modules list                              # What's currently docked
aaax modules load analytica                    # Verify → create System → wire → grant mediated caps
aaax modules unload analytica                  # Revoke capabilities → undock

# Convenience: both in one step
aaax install ./releases/analytica.zip          # lllm pkg install + aaax modules load
```

`lllm pkg install` installs a package zip into `lllm_packages/` or `~/.lllm/packages/`. `aaax modules load` reads the manifest, verifies against policy, creates the SSSN System, wires approved local channels, and grants mediated capabilities for remote resources or AAAX-owned executors. Two separate operations, two separate concerns.

AAAX bootstrap should not rely on LLLM's ambient cwd/shared-package discovery. The default LibOS should always create runtimes explicitly with `discover_cwd=False`, and it should enable shared-package loading only when the AAAX config intentionally asks for it.

---

## 2. Repository Structure

### 2.1 Monorepo Layout

```
aaax/
├── README.md
├── pyproject.toml                # Root package config
├── aaax.toml.example             # Example kernel config
├── aaax_cli.py                   # Root CLI entry point (composes kernel + suite)
│
├── aaax/                         # ── AAAX Kernel ──
│   ├── __init__.py
│   ├── kernel.py                 # AAAXKernel(BaseSystem) — the six functions
│   ├── constellation.py          # Dock, undock, registry, discovery
│   ├── capability.py             # Token issuance, validation, expiry
│   ├── action_gate.py            # Side-effect authorization
│   ├── module_loader.py          # Manifest parsing, verification, system creation
│   ├── lifecycle.py              # Revocation, pause, resume, drain
│   ├── policy.py                 # Policy interface + default rule engine
│   ├── bootstrap.py              # Config-driven initialization (PID 1)
│   ├── cli_kernel.py             # Kernel-only CLI commands
│   ├── config.py                 # TOML config schemas (Pydantic)
│   ├── protocols/                # Protocol message schemas
│   │   ├── __init__.py
│   │   ├── capability.py         # CapabilityRequest, CapabilityGrant, ...
│   │   ├── action.py             # ActionRequest, ActionApproved, ...
│   │   ├── module.py             # ModuleRegister, ModuleAccepted, ...
│   │   └── lifecycle.py          # RevokeRequest, PauseRequest, ...
│   ├── libos/                    # ── Default LibOS (thin LLLM bridge) ──
│   │   ├── __init__.py
│   │   ├── bridge.py             # LLLM Tactic ↔ AAAX protocol adapter
│   │   ├── capability_mixin.py   # Auto capability negotiation for mediated resources
│   │   └── action_mixin.py       # Route side effects through AAAX-owned executors
│   └── tests/
│       ├── test_kernel.py
│       ├── test_constellation.py
│       ├── test_capability.py
│       ├── test_action_gate.py
│       ├── test_lifecycle.py
│       ├── test_module_loader.py
│       ├── test_bootstrap.py
│       └── test_non_ps.py        # ← CRITICAL: kernel without PS
│
├── ps/                           # ── Productive Suite ──
│   ├── __init__.py
│   ├── suite.py                  # ProductiveSuite orchestrator
│   ├── cli.py                    # PS-specific CLI (aaax build ps, etc.)
│   ├── config.py                 # Suite config schema
│   ├── branches/
│   │   ├── __init__.py
│   │   ├── analysis.py           # Analysis branch coordinator
│   │   ├── research.py           # Research/evolution branch
│   │   └── operations.py         # Operations branch
│   ├── roles/
│   │   ├── __init__.py
│   │   ├── base.py               # BaseRole — common interface
│   │   ├── analyst.py            # Generic analyst template
│   │   ├── researcher.py         # Generic researcher template
│   │   ├── monitor.py            # Generic monitor template
│   │   └── templates/            # Built-in TOML templates
│   │       ├── equity-analyst.toml
│   │       ├── macro-economist.toml
│   │       ├── commodity-expert.toml
│   │       ├── policy-analyst.toml
│   │       ├── scm-planner.toml
│   │       └── research-assistant.toml
│   ├── modules/                  # ── Vanilla modules ──
│   │   ├── __init__.py
│   │   ├── interfaces.py         # ABCs for drop-in replacement
│   │   ├── reasoning/
│   │   │   ├── __init__.py
│   │   │   └── standard.py       # LLM chain-of-thought
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   └── basic.py          # Conversation context
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   └── connector.py      # RSS, API, CSV adapters
│   │   └── extensions/
│   │       ├── __init__.py
│   │       ├── web_research.py   # Search + document reading
│   │       └── report.py         # Markdown, PDF output
│   └── tests/
│       ├── test_suite.py
│       ├── test_roles.py
│       ├── test_composition.py
│       └── test_vanilla_modules.py
│
├── examples/
│   ├── single_analyst/           # One expert, vanilla
│   ├── energy_network/           # Five-expert constellation
│   ├── scm_network/              # Reconfigured from energy → SCM
│   └── minimal_kernel/           # Kernel without PS (proves agnosticism)
│
├── docs/
│   ├── kernel-design-note.md
│   ├── ps-design-note.md
│   └── implementation-note.md
│
└── scripts/
    ├── dev_setup.sh
    ├── run_tests.sh
    └── check_independence.sh     # Enforces no PS imports in kernel
```

### 2.2 Structural Independence Rule

```
aaax/     MAY import from:  sssn, lllm, stdlib
aaax/     MUST NOT import:  ps/

ps/       MAY import from:  aaax/, sssn, lllm, stdlib

aaax_cli.py  MAY import from: aaax/, ps/, stdlib
```

Enforced by:
1. CI script: `rg -n "from ps|import ps" aaax/ && exit 1`
2. `test_non_ps.py` — boots a kernel with a non-PS System
3. Code review

### 2.3 Package Configuration

```toml
# pyproject.toml
[project]
name = "aaax"
version = "0.1.0"
dependencies = [
    "sssn==0.0.1",
    "lllm-core==0.1.1",
    "tomli>=2.0",
    "pydantic>=2.0",
    "click>=8.0",
]

[project.optional-dependencies]
ps = ["httpx>=0.27", "feedparser>=6.0"]

[project.scripts]
aaax = "aaax_cli:main"
```

Pin framework dependencies exactly. AAAX is the first citizen of the default LibOS, and the Productive Suite is the first citizen of AAAX, so kernel-critical behavior should depend on explicit versions or workspace paths, not floating `>=` ranges.

### 2.4 Framework Contract Policy

AAAX should treat `sssn` and `lllm` as explicit contracts:

- **SSSN contract:** topology is the local authority model; HTTP transport is the remote authority model; `pause()` is marker-only unless overridden; work queues are reclaimable rather than exactly-once.
- **LLLM contract:** managed AAAX runtimes boot in strict mode; package install is separate from activation; AAAX adapters use public runtime APIs rather than LLLM private internals.
- **Upgrade policy:** changes to either framework are accepted only behind AAAX contract tests. If a framework changes in a way AAAX does not want, AAAX fixes or forks it rather than weakening its own contract.

---

## 3. Core Implementation: The Six Kernel Functions

The sketches below are source-grounded pseudocode. They intentionally follow current SSSN/LLLM behavior: local in-process access is primarily topology-wired via `add_subsystem(...)`, HTTP transport is where SSSN's JWT enforcement becomes real, and AAAX-mediated side effects must run through AAAX-owned executors or proxies.

### 3.1 AAAXKernel — The Umbrella System

```python
from sssn.core.system import BaseSystem
from sssn.channels.work_queue import WorkQueueChannel
from sssn.channels.broadcast import BroadcastChannel
from sssn.channels.mailbox import MailboxChannel
from sssn.core.channel import Visibility

from aaax.constellation import ConstellationManager
from aaax.capability import CapabilityManager
from aaax.action_gate import ActionGate
from aaax.module_loader import ModuleLoader
from aaax.lifecycle import LifecycleManager
from aaax.policy import PolicyEngine
from aaax.config import AAAXConfig


class AAAXKernel(BaseSystem):
    """
    The AAAX exokernel. A SSSN System that provides six functions:
    1. Constellation management (dock, undock, registry)
    2. Capability management (issue, validate, expire mediated tokens)
    3. Action gate (authorize and route side effects through AAAX-owned executors)
    4. Module loading (manifest verification, system creation)
    5. Revocation and lifecycle (force-revoke, pause, resume, drain)
    6. Bootstrap (config-driven initialization)
    """

    def __init__(self, config: AAAXConfig):
        super().__init__(id=config.id, name=config.name)
        self.config = config

        # The six functions
        self._constellation = ConstellationManager()
        self._capabilities = CapabilityManager()
        self._action_gate = ActionGate()
        self._module_loader = ModuleLoader()
        self._lifecycle = LifecycleManager()
        self._policy = PolicyEngine.from_config(config.policy)

    async def setup(self):
        """Bootstrap: create channels, load LibOS, load initial modules."""

        # ── Private internal channels (never exposed) ──
        self._capability_registry = BroadcastChannel(
            id="aaax.internal.capability-registry",
            name="Capability Registry",
            visibility=Visibility.PRIVATE,
        )
        self.add_channel(self._capability_registry)

        self._module_registry = BroadcastChannel(
            id="aaax.internal.module-registry",
            name="Module Registry",
            visibility=Visibility.PRIVATE,
        )
        self.add_channel(self._module_registry)

        self._policy_store = BroadcastChannel(
            id="aaax.internal.policy-store",
            name="Policy Store",
            visibility=Visibility.PRIVATE,
        )
        self.add_channel(self._policy_store)

        # ── Common protocol channels (wired to ordinary subsystems) ──
        self._cap_request_ch = WorkQueueChannel(
            id="aaax.capability-request",
            name="Capability Requests",
        )
        self.add_channel(self._cap_request_ch)

        self._action_gate_ch = WorkQueueChannel(
            id="aaax.action-gate",
            name="Action Gate",
        )
        self.add_channel(self._action_gate_ch)

        self._kernel_reply_ch = MailboxChannel(
            id="aaax.kernel-replies",
            name="Kernel Replies",
        )
        self.add_channel(self._kernel_reply_ch)

        # ── Privileged protocol channels (supervisors/bootstrap only) ──
        self._module_loader_ch = WorkQueueChannel(
            id="aaax.module-loader",
            name="Module Loader",
        )
        self.add_channel(self._module_loader_ch)

        self._lifecycle_ch = WorkQueueChannel(
            id="aaax.lifecycle",
            name="Lifecycle Commands",
        )
        self.add_channel(self._lifecycle_ch)

        self._heartbeat_ch = BroadcastChannel(
            id="aaax.heartbeat",
            name="Heartbeat",
        )
        self.add_channel(self._heartbeat_ch)

        # ── Load default LibOS ──
        from aaax.libos.bridge import DefaultLibOS
        self._libos = DefaultLibOS(kernel=self, config=self.config.libos)

        # ── Load initial modules from config ──
        for mod_conf in self.config.modules:
            await self._module_loader.load_from_config(
                kernel=self, config=mod_conf, policy=self._policy,
            )

    async def step(self):
        """Main loop: process all protocol queues."""
        await self._process_capability_requests()
        await self._process_action_gate()
        await self._process_module_loader()
        await self._process_lifecycle()
        await self._publish_heartbeat()
        self._capabilities.expire_stale()

    # ════════════════════════════════════════════
    # Function 1: Constellation Management
    # ════════════════════════════════════════════

    async def dock(
        self,
        system: BaseSystem,
        channels: list[str] | None = None,
        privileged: bool = False,
    ):
        """Dock a subsystem into the managed constellation."""
        common_protocol_channels = [
            "aaax.capability-request",
            "aaax.action-gate",
            "aaax.kernel-replies",
            "aaax.heartbeat",
        ]
        privileged_protocol_channels = [
            "aaax.module-loader",
            "aaax.lifecycle",
        ]

        all_channels = common_protocol_channels + (channels or [])
        if privileged:
            all_channels += privileged_protocol_channels

        self.add_subsystem(system, channels=all_channels)
        self._constellation.register(system, channels=all_channels)

    async def undock(self, system_id: str):
        """Remove a subsystem from the constellation."""
        self._capabilities.revoke_all(system_id)
        self._constellation.unregister(system_id)
        # SSSN handles the actual subsystem removal

    # ════════════════════════════════════════════
    # Function 2: Capability Management
    # ════════════════════════════════════════════

    async def _process_capability_requests(self):
        msgs = await self.claim_channel("aaax.capability-request", limit=10)
        for msg in msgs:
            result = await self._capabilities.process_request(msg, self._policy)
            await self._respond(msg, result)
            await self.acknowledge_channel("aaax.capability-request", [msg.id])

    # ════════════════════════════════════════════
    # Function 3: Action Gate
    # ════════════════════════════════════════════

    async def _process_action_gate(self):
        msgs = await self.claim_channel("aaax.action-gate", limit=10)
        for msg in msgs:
            result = await self._action_gate.process(msg, self._policy, self._capabilities)
            await self._respond(msg, result)
            await self.acknowledge_channel("aaax.action-gate", [msg.id])

    # ════════════════════════════════════════════
    # Function 4: Module Loading
    # ════════════════════════════════════════════

    async def _process_module_loader(self):
        msgs = await self.claim_channel("aaax.module-loader", limit=5)
        for msg in msgs:
            result = await self._module_loader.process_request(
                kernel=self, msg=msg, policy=self._policy,
            )
            await self._respond(msg, result)
            await self.acknowledge_channel("aaax.module-loader", [msg.id])

    # ════════════════════════════════════════════
    # Function 5: Revocation and Lifecycle
    # ════════════════════════════════════════════

    async def _process_lifecycle(self):
        msgs = await self.claim_channel("aaax.lifecycle", limit=5)
        for msg in msgs:
            result = await self._lifecycle.process(
                msg, self._constellation, self._capabilities,
            )
            await self._respond(msg, result)
            await self.acknowledge_channel("aaax.lifecycle", [msg.id])

    async def revoke(self, system_id: str):
        """Force-revoke all capabilities for a system."""
        self._capabilities.revoke_all(system_id)

    async def pause(self, system_id: str):
        """Pause a docked subsystem."""
        self._lifecycle.pause(system_id, self._constellation)

    async def resume(self, system_id: str):
        """Resume a paused subsystem."""
        self._lifecycle.resume(system_id, self._constellation)

    async def drain(self, system_id: str, timeout: float = 30.0):
        """Gracefully drain a subsystem before removal."""
        await self._lifecycle.drain(system_id, self._constellation, timeout)
        await self.undock(system_id)

    # ════════════════════════════════════════════
    # Function 6: Bootstrap (handled in setup() above)
    # ════════════════════════════════════════════

    async def _publish_heartbeat(self):
        await self.write_channel("aaax.heartbeat", data={
            "status": "running",
            "modules": self._constellation.list_systems(),
            "capabilities_active": self._capabilities.active_count(),
        })

    async def _respond(self, request_msg, result):
        reply_channel = request_msg.reply_to
        if reply_channel and self._constellation.is_valid_reply_target(
            request_msg.sender_id, reply_channel,
        ):
            await self.write_channel(reply_channel, data=result)
            return

        await self.write_channel(
            "aaax.kernel-replies",
            data=result,
            recipient_id=request_msg.sender_id,
        )
```

### 3.2 Constellation Manager

```python
from dataclasses import dataclass, field
from sssn.core.system import BaseSystem


@dataclass
class SystemRecord:
    system_id: str
    name: str
    system: BaseSystem | None = None
    channels: list[str] = field(default_factory=list)
    status: str = "running"  # running | paused | draining | drained | revoked


class ConstellationManager:
    """Tracks what's docked, what channels each system has, current status."""

    def __init__(self):
        self._systems: dict[str, SystemRecord] = {}

    def register(self, system: BaseSystem, channels: list[str] = None):
        self._systems[system.id] = SystemRecord(
            system_id=system.id,
            name=system.name,
            system=system,
            channels=list(channels or []),
        )

    def unregister(self, system_id: str):
        self._systems.pop(system_id, None)

    def get(self, system_id: str) -> SystemRecord | None:
        return self._systems.get(system_id)

    def list_systems(self) -> list[dict]:
        return [
            {"id": r.system_id, "name": r.name, "status": r.status}
            for r in self._systems.values()
        ]

    def set_status(self, system_id: str, status: str):
        if system_id in self._systems:
            self._systems[system_id].status = status

    def is_valid_reply_target(self, system_id: str, channel_id: str) -> bool:
        record = self._systems.get(system_id)
        return record is not None and channel_id in record.channels
```

### 3.3 Capability Manager

```python
import time
import uuid
from dataclasses import dataclass, field
from aaax.policy import PolicyEngine


@dataclass
class Capability:
    token: str
    system_id: str
    resource: str
    access: str          # read | write | execute
    issued_at: float
    expires_at: float
    scope: dict = field(default_factory=dict)


ACCESS_LEVELS = {"read": 0, "write": 1, "execute": 2}


class CapabilityManager:
    """
    Issues AAAX-local bearer tokens for mediated resources.

    Local in-process SSSN channel access remains topology-based via
    add_subsystem(...). Use these tokens for remote HTTP channels,
    AAAX-owned executors, and external services.
    """

    def __init__(self):
        self._capabilities: dict[str, Capability] = {}
        self._by_system: dict[str, set[str]] = {}  # system_id → set of tokens

    async def process_request(self, msg, policy: PolicyEngine) -> dict:
        content = msg.content.data
        system_id = content["from"]
        resource = content["resource"]
        access = content["access"]
        scope = content.get("scope", {})
        context = content.get("context", {})

        decision = await policy.evaluate_capability(
            system_id=system_id, resource=resource,
            access=access, context=context,
        )

        if not decision.allowed:
            return {"type": "capability_deny", "resource": resource, "reason": decision.reason}

        return await self.issue(
            system_id=system_id,
            resource=resource,
            access=access,
            scope=scope,
        )

    async def issue(self, system_id: str, resource: str, access: str, scope: dict | None = None) -> dict:
        scope = scope or {}
        ttl = scope.get("ttl", 3600)
        token = uuid.uuid4().hex

        cap = Capability(
            token=token, system_id=system_id, resource=resource,
            access=access, issued_at=time.time(),
            expires_at=time.time() + ttl, scope=scope,
        )
        self._capabilities[token] = cap
        self._by_system.setdefault(system_id, set()).add(token)

        return {
            "type": "capability_grant", "resource": resource,
            "token": token, "expires": cap.expires_at,
        }

    def validate(self, system_id: str, token: str, resource: str, access: str) -> bool:
        cap = self._capabilities.get(token)
        if not cap or cap.expires_at < time.time():
            self._capabilities.pop(token, None)
            return False
        if cap.system_id != system_id:
            return False
        if cap.resource != resource:
            return False
        return ACCESS_LEVELS.get(cap.access, -1) >= ACCESS_LEVELS.get(access, 0)

    def revoke_all(self, system_id: str):
        """Force-revoke all capabilities for a system (Aegis abort protocol)."""
        tokens = self._by_system.pop(system_id, set())
        for token in tokens:
            self._capabilities.pop(token, None)

    def expire_stale(self):
        now = time.time()
        expired = [k for k, v in self._capabilities.items() if v.expires_at < now]
        for k in expired:
            cap = self._capabilities.pop(k)
            self._by_system.get(cap.system_id, set()).discard(k)

    def active_count(self) -> int:
        return len(self._capabilities)
```

### 3.4 Action Gate

```python
from aaax.policy import PolicyEngine
from aaax.capability import CapabilityManager


class ActionGate:
    """
    Policy-configurable authorization and routing for side-effecting operations.

    Approval authorizes an AAAX-owned executor/proxy to act; it does not permit
    the requesting subsystem to bypass the kernel.
    """

    async def process(self, msg, policy: PolicyEngine, capabilities: CapabilityManager) -> dict:
        content = msg.content.data
        system_id = content["from"]
        action = content["action"]
        executor = content["executor"]
        target = content["target"]
        payload = content["payload"]
        cap_token = content.get("capability")
        risk_level = content.get("risk_level", "medium")

        if not cap_token:
            return {
                "type": "action_denied", "request_id": msg.id,
                "reason": "Missing execute capability token",
            }

        if not capabilities.validate(system_id, cap_token, executor, "execute"):
            return {
                "type": "action_denied", "request_id": msg.id,
                "reason": "Invalid or expired capability token",
            }

        decision = await policy.evaluate_action(
            system_id=system_id,
            action=action,
            executor=executor,
            target=target,
            payload=payload,
            risk_level=risk_level,
        )

        if decision.escalate:
            return {
                "type": "action_escalated", "request_id": msg.id,
                "reason": decision.reason, "escalated_to": decision.escalate_to,
            }
        if not decision.allowed:
            return {
                "type": "action_denied", "request_id": msg.id,
                "reason": decision.reason,
            }
        return {
            "type": "action_approved", "request_id": msg.id,
            "executor": executor,
            "modified_payload": decision.modified_payload or payload,
        }
```

### 3.5 Module Loader

```python
from sssn.core.system import BaseSystem
from aaax.policy import PolicyEngine
from aaax.config import ModuleConfig


class ModuleLoader:
    """
    Manifest verification + system creation + channel wiring.
    This is AAAX's Gatekeeper: the trust boundary for loading modules.
    
    LLLM handles package format and installation (files on disk).
    AAAX handles verification, local channel wiring, and issuance of
    mediated capabilities (runtime trust).
    """

    async def load_from_config(self, kernel, config: ModuleConfig, policy: PolicyEngine):
        """Load a module from bootstrap config."""
        manifest = self._parse_manifest(config)
        await self._verify_and_dock(kernel, manifest, policy)

    async def process_request(self, kernel, msg, policy: PolicyEngine) -> dict:
        """Process a runtime module load request."""
        content = msg.content.data
        manifest = content["manifest"]
        module_id = content["module_id"]

        # Verify manifest against policy
        decision = await policy.evaluate_module(manifest)
        if not decision.allowed:
            return {
                "type": "module_rejected", "module_id": module_id,
                "reason": decision.reason,
            }

        system = await self._create_system(manifest, libos=kernel._libos)
        await kernel.dock(system, channels=manifest.get("requires_channels", []))
        capabilities = await self._issue_initial_capabilities(kernel, manifest)

        return {
            "type": "module_accepted", "module_id": module_id,
            "system_id": system.id,
            "granted_wiring": manifest.get("requires_channels", []),
            "granted_capabilities": capabilities,
        }

    def _parse_manifest(self, config: ModuleConfig) -> dict:
        """Parse module config into a manifest dict."""
        return {
            "module_id": config.id,
            "framework": config.framework,
            "lllm_toml": config.lllm_toml,
            "requires_channels": config.channels,
            "requires_executors": config.executors,
            "requires_remote_channels": config.remote_channels,
            "provides_channels": [],
            "risk_profile": "low",
        }

    async def _verify_and_dock(self, kernel, manifest: dict, policy: PolicyEngine):
        """Verify manifest against policy, create system, dock."""
        decision = await policy.evaluate_module(manifest)
        if not decision.allowed:
            raise PermissionError(f"Module {manifest['module_id']} rejected: {decision.reason}")
        system = await self._create_system(manifest, libos=kernel._libos)
        await kernel.dock(system, channels=manifest.get("requires_channels", []))
        await self._issue_initial_capabilities(kernel, manifest)

    async def _create_system(self, manifest: dict, libos=None) -> BaseSystem:
        """Create a SSSN System from a manifest."""
        # For LLLM modules, import and instantiate the Tactic as a System
        framework = manifest.get("framework", "lllm")
        if framework == "lllm":
            from aaax.libos.bridge import TacticSystem
            return TacticSystem(
                id=manifest["module_id"],
                name=manifest["module_id"],
                manifest=manifest,
                libos=libos,
            )
        else:
            # Generic: create a base system placeholder
            system = BaseSystem(id=manifest["module_id"], name=manifest["module_id"])
            return system

    async def _issue_initial_capabilities(self, kernel, manifest: dict) -> list[dict]:
        """Pre-issue capabilities for mediated requirements only."""
        capabilities = []
        for executor in manifest.get("requires_executors", []):
            capabilities.append(
                await kernel._capabilities.issue(
                    system_id=manifest["module_id"],
                    resource=executor,
                    access="execute",
                    scope={"issued_by": "module_loader"},
                )
            )
        for channel in manifest.get("requires_remote_channels", []):
            capabilities.append(
                await kernel._capabilities.issue(
                    system_id=manifest["module_id"],
                    resource=channel,
                    access="read",
                    scope={"issued_by": "module_loader"},
                )
            )
        return capabilities
```

### 3.5A Default LibOS Bridge

```python
from lllm import load_runtime


class DefaultLibOS:
    """
    Thin AAAX-owned bridge to LLLM.

    AAAX is responsible for deterministic runtime creation. It should never
    depend on ambient cwd discovery or import-time LLLM auto-init.
    """

    def __init__(self, kernel, config):
        self.kernel = kernel
        self.config = config

    def build_runtime(self, module_id: str, toml_path: str):
        return load_runtime(
            toml_path=toml_path,
            name=f"aaax:{module_id}",
            discover_cwd=not self.config.strict_boot,
            discover_shared_packages=self.config.discover_shared_packages,
        )


class TacticSystem(BaseSystem):
    def __init__(self, id: str, name: str, manifest: dict, libos: DefaultLibOS | None = None):
        super().__init__(id=id, name=name)
        self.manifest = manifest
        self._libos = libos

    async def setup(self):
        runtime = self._libos.build_runtime(
            module_id=self.id,
            toml_path=self.manifest["lllm_toml"],
        )
        # Instantiate tactic/agents from the explicit runtime here.
```

If AAAX launches helper subprocesses that import `lllm` directly, set `LLLM_AUTO_INIT=0` in those processes as well so import-time discovery never bypasses kernel policy.

### 3.6 Lifecycle Manager

```python
import asyncio
import inspect


class LifecycleManager:
    """
    Revocation, pause, resume, drain.

    These controls are cooperative. Current SSSN exposes a PAUSED state marker
    and channel-level drain helpers, but it does not suspend a system's run loop
    or provide a built-in system-wide drain primitive.
    """

    async def process(self, msg, constellation, capabilities) -> dict:
        content = msg.content.data
        command = content["command"]  # revoke | pause | resume | drain
        target = content["system_id"]
        timeout = content.get("timeout", 30.0)

        if constellation.get(target) is None:
            return {"type": "lifecycle_error", "reason": f"Unknown system: {target}"}

        if command == "revoke":
            capabilities.revoke_all(target)
            constellation.set_status(target, "revoked")
            return {"type": "lifecycle_ok", "command": command, "system_id": target}

        elif command == "pause":
            self.pause(target, constellation)
            return {"type": "lifecycle_ok", "command": command, "system_id": target}

        elif command == "resume":
            self.resume(target, constellation)
            return {"type": "lifecycle_ok", "command": command, "system_id": target}

        elif command == "drain":
            await self.drain(target, constellation, timeout)
            return {"type": "lifecycle_ok", "command": command, "system_id": target}

        return {"type": "lifecycle_error", "reason": f"Unknown command: {command}"}

    def pause(self, system_id: str, constellation):
        record = constellation.get(system_id)
        if record and record.system is not None:
            record.system.pause()  # Marker-only in current SSSN unless overridden
        constellation.set_status(system_id, "paused")

    def resume(self, system_id: str, constellation):
        record = constellation.get(system_id)
        if record and record.system is not None:
            record.system.resume()
        constellation.set_status(system_id, "running")

    async def drain(self, system_id: str, constellation, timeout: float):
        record = constellation.get(system_id)
        if record is None:
            return

        constellation.set_status(system_id, "draining")
        system = record.system
        if system is None:
            constellation.set_status(system_id, "drained")
            return

        drain_fn = getattr(system, "drain", None)
        if callable(drain_fn):
            result = drain_fn(timeout=timeout)
            if inspect.isawaitable(result):
                await asyncio.wait_for(result, timeout=timeout)
        else:
            system.stop()  # Best-effort fallback; BaseSystem has no built-in drain

        constellation.set_status(system_id, "drained")
```

### 3.7 Policy Engine

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str = ""
    escalate: bool = False
    escalate_to: str = ""
    modified_payload: dict | None = None


class PolicyEngine(ABC):
    """Abstract policy interface. Pluggable — swap implementations."""

    @abstractmethod
    async def evaluate_capability(self, system_id, resource, access, context) -> PolicyDecision: ...

    @abstractmethod
    async def evaluate_action(self, system_id, action, executor, target, payload, risk_level) -> PolicyDecision: ...

    @abstractmethod
    async def evaluate_module(self, manifest: dict) -> PolicyDecision: ...

    @classmethod
    def from_config(cls, config) -> "PolicyEngine":
        if config == "default" or config is None:
            return DefaultRulePolicy()
        if isinstance(config, str) and config.endswith(".toml"):
            return DefaultRulePolicy.from_file(config)
        return DefaultRulePolicy()


class DefaultRulePolicy(PolicyEngine):
    """Simple rule-based policy loaded from TOML."""

    def __init__(self, rules: dict = None):
        self._rules = rules or {
            "default_capability": "allow",
            "default_action": {"low": "allow", "medium": "allow", "high": "deny", "irreversible": "escalate"},
            "default_module": "allow",
        }

    async def evaluate_capability(self, system_id, resource, access, context):
        return PolicyDecision(allowed=True)

    async def evaluate_action(self, system_id, action, executor, target, payload, risk_level):
        rule = self._rules.get("default_action", {}).get(risk_level, "deny")
        if rule == "allow":
            return PolicyDecision(allowed=True)
        elif rule == "escalate":
            return PolicyDecision(allowed=False, escalate=True,
                reason=f"Risk '{risk_level}' requires escalation", escalate_to="human")
        return PolicyDecision(allowed=False, reason=f"Denied for risk '{risk_level}'")

    async def evaluate_module(self, manifest):
        return PolicyDecision(allowed=True)

    @classmethod
    def from_file(cls, path: str) -> "DefaultRulePolicy":
        import tomli
        with open(path, "rb") as f:
            return cls(rules=tomli.load(f))
```

### 3.8 CLI

```python
# aaax_cli.py
import click

from aaax.cli_kernel import install, launch, modules
from ps.cli import build, templates


@click.group()
def main():
    """AAAX CLI entry point."""
    pass


main.add_command(launch)
main.add_command(modules)
main.add_command(install)
main.add_command(build)
main.add_command(templates)
```

`aaax/cli_kernel.py` owns kernel-only commands such as `launch`, `modules`, and the convenience `install` wrapper (`lllm pkg install <zip>` followed by `aaax modules load <package-name>`). `ps/cli.py` owns suite builders and template listing. The root `aaax_cli.py` composes them into one CLI without introducing a kernel → suite import.

---

## 4. Productive Suite Implementation

### 4.1 Suite Orchestrator (`ps/suite.py`)

```python
from aaax.kernel import AAAXKernel
from aaax.config import AAAXConfig
from ps.config import SuiteConfig
from ps.branches.analysis import AnalysisBranch
from ps.branches.research import ResearchBranch
from ps.branches.operations import OperationsBranch


class ProductiveSuite:
    """Creates an AAAX kernel and docks configured branches."""

    def __init__(self, suite_config: SuiteConfig):
        self.suite_config = suite_config
        self.kernel: AAAXKernel = None
        self.branches = {}

    async def setup(self):
        from aaax.bootstrap import bootstrap_kernel

        kernel_config = AAAXConfig(
            id=f"aaax-ps-{self.suite_config.name}",
            name=f"PS: {self.suite_config.name}",
            policy=self.suite_config.policy.execution if self.suite_config.policy else "default",
        )
        self.kernel = await bootstrap_kernel(kernel_config)

        # Analysis (always active)
        if self.suite_config.analysis:
            branch = AnalysisBranch(self.suite_config.analysis)
            await branch.setup()
            for system, channels in branch.get_systems():
                await self.kernel.dock(system, channels)
            self.branches["analysis"] = branch

        # Research (optional)
        if self.suite_config.research and self.suite_config.research.enabled:
            branch = ResearchBranch(self.suite_config.research)
            await branch.setup()
            for system, channels in branch.get_systems():
                await self.kernel.dock(system, channels)
            self.branches["research"] = branch

        # Operations (optional)
        if self.suite_config.operations and self.suite_config.operations.enabled:
            branch = OperationsBranch(self.suite_config.operations)
            await branch.setup()
            for system, channels in branch.get_systems():
                await self.kernel.dock(system, channels)
            self.branches["operations"] = branch

    async def launch(self):
        await self.kernel.launch()

    async def publish(self, host: str, port: int):
        await self.kernel.publish(host=host, port=port)
```

### 4.2 Module Interfaces (`ps/modules/interfaces.py`)

```python
from abc import ABC, abstractmethod
from typing import Any


class ReasoningEngine(ABC):
    """Vanilla: StandardReasoning. Advanced: Analytica."""
    @abstractmethod
    async def analyze(self, query: str, context: dict) -> dict: ...
    @abstractmethod
    async def evaluate_hypothesis(self, hypothesis: str, evidence: list) -> dict: ...


class MemoryModule(ABC):
    """Vanilla: BasicMemory. Advanced: AAPM."""
    @abstractmethod
    async def store(self, key: str, content: Any, metadata: dict = None): ...
    @abstractmethod
    async def retrieve(self, query: str, limit: int = 10) -> list: ...
    @abstractmethod
    async def get_relevant(self, context: dict) -> list: ...


class DataSource(ABC):
    """Vanilla: DataConnector. Advanced: SocioDojo."""
    @abstractmethod
    async def subscribe(self, channel_id: str): ...
    @abstractmethod
    async def get_latest(self, channel_id: str, limit: int = 20) -> list: ...


class ExtensionModule(ABC):
    @abstractmethod
    def get_tools(self) -> list: ...
```

### 4.3 Role Base Class (`ps/roles/base.py`)

```python
from sssn.core.system import BaseSystem
from ps.modules.interfaces import ReasoningEngine, MemoryModule


class BaseRole(BaseSystem):
    """Every expert role is a SSSN System with a reasoning engine and memory."""

    def __init__(self, id: str, name: str, reasoning: ReasoningEngine, memory: MemoryModule, tools: list = None):
        super().__init__(id=id, name=name)
        self.reasoning = reasoning
        self.memory = memory
        self.tools = tools or []

    async def analyze(self, query: str) -> dict:
        relevant = await self.memory.get_relevant({"query": query})
        context = {"memory": relevant, "role": self.id}
        result = await self.reasoning.analyze(query, context)
        await self.memory.store(key=f"analysis:{self.id}", content=result, metadata={"query": query})
        return result
```

### 4.4 Advanced Module Package Structure

Advanced modules are distributed as ordinary LLLM packages:

```
analytica/
├── lllm.toml
├── prompts/
├── tactics/
├── configs/
├── analytica/
│   ├── __init__.py
│   └── engine.py          # Implements ps.modules.interfaces.ReasoningEngine
└── README.md
```

```toml
# lllm.toml
[package]
name = "analytica"
version = "0.1.0"
description = "Advanced reasoning module for AAAX Productive Suite"

[prompts]
paths = ["prompts"]

[tactics]
paths = ["tactics"]

[configs]
paths = ["configs"]
```

```bash
lllm pkg export analytica ./releases/analytica-v1.zip
lllm pkg install ./releases/analytica-v1.zip --scope project
# Then select it in the suite config:
# [suite.analysis.reasoning]
# engine = "analytica"
```

Package replacement semantics live in AAAX/PS configuration, not in the current LLLM package loader.

---

## 5. Configuration Schemas

### 5.1 Kernel Config

```python
# aaax/config.py
from pydantic import BaseModel, Field

class NetworkConfig(BaseModel):
    publish: bool = False
    host: str = "0.0.0.0"
    port: int = 8100

class LibOSConfig(BaseModel):
    name: str = "lllm"
    strict_boot: bool = True
    discover_shared_packages: bool = False

class ModuleConfig(BaseModel):
    id: str
    framework: str = "lllm"
    lllm_toml: str | None = None
    channels: list[str] = Field(default_factory=list)
    executors: list[str] = Field(default_factory=list)
    remote_channels: list[str] = Field(default_factory=list)

class AAAXConfig(BaseModel):
    id: str = "aaax-main"
    name: str = "AAAX Kernel"
    policy: str | None = "default"
    libos: LibOSConfig = Field(default_factory=LibOSConfig)
    modules: list[ModuleConfig] = Field(default_factory=list)
    network: NetworkConfig = Field(default_factory=NetworkConfig)

    @classmethod
    def from_file(cls, path: str) -> "AAAXConfig":
        import tomli
        with open(path, "rb") as f:
            return cls(**tomli.load(f).get("aaax", {}))
```

### 5.2 Suite Config

```python
# ps/config.py
from pydantic import BaseModel, Field

class AnalysisDataConfig(BaseModel):
    channels: list[str] = Field(default_factory=list)

class AnalysisReasoningConfig(BaseModel):
    engine: str = "standard"
    memory: str = "basic"

class AnalysisConfig(BaseModel):
    roles: list[str] = Field(default_factory=lambda: ["analyst"])
    data: AnalysisDataConfig = Field(default_factory=AnalysisDataConfig)
    reasoning: AnalysisReasoningConfig = Field(default_factory=AnalysisReasoningConfig)

class ResearchConfig(BaseModel):
    enabled: bool = False
    engine: str = "standard"
    evolution_interval: str = "daily"

class OperationsConfig(BaseModel):
    enabled: bool = False
    sensors: list[str] = Field(default_factory=list)
    actuators: list[str] = Field(default_factory=list)

class SuitePolicyConfig(BaseModel):
    execution: str = "default"

class SuiteNetworkConfig(BaseModel):
    publish: bool = False
    port: int | None = None

class SuiteConfig(BaseModel):
    name: str = "my-suite"
    type: str = "ps"
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    research: ResearchConfig | None = None
    operations: OperationsConfig | None = None
    policy: SuitePolicyConfig = Field(default_factory=SuitePolicyConfig)
    network: SuiteNetworkConfig = Field(default_factory=SuiteNetworkConfig)

    @classmethod
    def from_file(cls, path: str) -> "SuiteConfig":
        import tomli
        with open(path, "rb") as f:
            return cls(**tomli.load(f).get("suite", {}))
```

---

## 6. Testing Strategy

### 6.1 Test Categories

| Category | Location | Purpose |
|---|---|---|
| Kernel unit tests | `aaax/tests/` | Each of the six functions in isolation |
| Domain agnosticism | `aaax/tests/test_non_ps.py` | Kernel boots with a non-PS system |
| PS unit tests | `ps/tests/` | Composition, vanilla modules, roles |
| Integration | `ps/tests/test_composition.py` | Full stack end-to-end |
| Examples | `examples/` | Runnable smoke tests |

### 6.2 Domain Agnosticism Test

```python
# aaax/tests/test_non_ps.py
"""MUST NOT import anything from ps/."""
import asyncio
from sssn.core.system import BaseSystem
from sssn.channels.broadcast import BroadcastChannel
from aaax.bootstrap import bootstrap_kernel
from aaax.config import AAAXConfig


class TrivialRobotNode(BaseSystem):
    async def setup(self):
        self.sensor = BroadcastChannel(id="sensor-data", name="Sensor")
        self.add_channel(self.sensor)
    async def step(self):
        await self.write_channel("sensor-data", data={"temperature": 22.4})


async def test_kernel_without_ps():
    config = AAAXConfig(id="test-kernel", name="Test")
    kernel = await bootstrap_kernel(config)
    robot = TrivialRobotNode(id="robot-1", name="Robot")
    await robot.setup()
    await kernel.dock(robot, channels=["sensor-data"])
    assert kernel._constellation.get("robot-1") is not None
    # Kernel works without any PS involvement
```

---

## 7. Dependency Map

```
External (pip installable):
  sssn ← Systems, Channels, Security, Transport
  lllm ← Tactic, Agent, Prompt, Dialog, package system

                    sssn ──────► aaax/kernel ──────► aaax/libos
                      │              │                    │
                      │              │                    ▼
                      └──────────────┼──────────────► ps/suite
                                     │                    │
                    lllm ────────────┘                    ▼
                                                  ps/modules (vanilla)
                                                         ▲
                                                  advanced modules
                                                  (separate LLLM pkgs)
```

**Import direction is strictly one-way.** Arrows point from dependent to dependency. There is no cycle and no reverse arrow from ps/ to aaax/.

---

## 8. Development Workflow

```bash
# Setup
git clone https://github.com/Productive-Superintelligence/aaax && cd aaax
python -m venv .venv && source .venv/bin/activate
pip install -e ".[ps]"
pip install sssn lllm

# Test kernel (must pass independently)
python -m pytest aaax/tests/ -v

# Verify framework contracts before changing AAAX assumptions
( cd sssn && python -m pytest -q )
( cd lllm && python -m pytest -q tests/units )   # run in env with LLLM deps installed

# Test PS
python -m pytest ps/tests/ -v

# Check structural independence
bash scripts/check_independence.sh

# Run examples
python -m examples.single_analyst
python -m examples.minimal_kernel
```

---

## 9. Phase 1 Deliverables

- [ ] **Kernel: 6 functions**
  - [ ] `aaax/kernel.py` — AAAXKernel with setup/step and all six function methods
  - [ ] `aaax/constellation.py` — dock, undock, registry
  - [ ] `aaax/capability.py` — issue, validate, expire, revoke_all
  - [ ] `aaax/action_gate.py` — process with risk levels
  - [ ] `aaax/module_loader.py` — manifest verification, system creation
  - [ ] `aaax/lifecycle.py` — revoke, pause, resume, drain
  - [ ] `aaax/policy.py` — interface + DefaultRulePolicy
  - [ ] `aaax/bootstrap.py` — config-driven init
  - [ ] `aaax/config.py` — Pydantic schemas
  - [ ] `aaax/protocols/` — message schemas
- [ ] **Default LibOS**
  - [ ] `aaax/libos/bridge.py` — LLLM ↔ AAAX adapter with strict deterministic runtime boot
- [ ] **CLI**
  - [ ] `aaax launch`, `aaax build ps`, `aaax templates`
  - [ ] `aaax modules list/load/unload`, `aaax install`
- [ ] **Productive Suite: vanilla**
  - [ ] `ps/suite.py` — orchestrator
  - [ ] `ps/modules/interfaces.py` — ABCs
  - [ ] `ps/modules/reasoning/standard.py` — vanilla reasoning
  - [ ] `ps/modules/memory/basic.py` — vanilla memory
  - [ ] `ps/roles/base.py` + `ps/roles/analyst.py`
  - [ ] `ps/roles/templates/equity-analyst.toml`
- [ ] **Tests**
  - [ ] `aaax/tests/test_non_ps.py` — domain agnosticism proof
  - [ ] `aaax/tests/` — all six kernel functions
  - [ ] `ps/tests/` — composition, vanilla modules
- [ ] **Examples**
  - [ ] `examples/single_analyst/` — one expert, vanilla, end-to-end
  - [ ] `examples/minimal_kernel/` — kernel without PS
- [ ] **CI**
  - [ ] Structural independence check
  - [ ] Framework contract checks: strict LLLM boot and SSSN transport/lifecycle assumptions
  - [ ] All tests green
