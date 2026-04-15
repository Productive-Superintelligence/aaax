# AAAX Productive Suite (AAAX-PS) — Design Note

> High-level architecture and specification for the AAAX Productive Suite,
> the flagship application built on the AAAX Agent OS Kernel.
> Companion document to the AAAX Kernel Design Note.

---

## 1. Overview

The AAAX Productive Suite (AAAX-PS) is a configurable, multi-role autonomous system for societal analysis, scientific research, and operational coordination. It is the first and flagship application built on the AAAX kernel — the cardinal application that validates the kernel's abstractions and demonstrates the full stack (SSSN + AAAX + LLLM) in production.

### The Organism

The Productive Suite is one system with three facets:

- **Analysis** — the brain. Understands the world, evaluates situations, makes judgments. Covers finance, economics, policy, supply chain, business intelligence, culture.
- **Research** — the curiosity. Explores, discovers, generates new knowledge, evolves strategies. Covers automated hypothesis generation, experiment design, literature analysis, discovery.
- **Operations** — the body. Senses the physical world and coordinates action. Provides the planning layer for IoT sensors, robotic actuators, and cyber-physical systems. Does not replace low-level control loops — it plans and coordinates at the decision level.

These branches are interconnected: analysis drives research (what questions to ask), research improves analysis (better reasoning strategies), and both drive operations (what actions to take). A supply chain analysis agent doesn't just recommend "reroute shipments" — it coordinates with warehouse IoT sensors for current inventory, with logistics systems for the reroute, and with market analysis agents to understand why.

### Name

"Productive" matches the PSI (Productive Superintelligence) mission: the suite thinks (analysis), explores (research), and does (operations). It is a productive system, not just a thinking tool. The name allows other suites to be built on the same kernel — a Robotics Suite, a Creative Suite, a Metaverse Suite — while the Productive Suite remains the flagship.

### Structural Relationship to AAAX

```
┌─────────────────────────────────────────────────┐
│  AAAX Productive Suite                          │  ← What users see
│  Expert roles, configurations, CLI/GUI          │
├─────────────────────────────────────────────────┤
│  LLLM + Modules (LibOS)                        │  ← Reconfigurable logic
│  Vanilla modules (default) or Advanced modules  │
├─────────────────────────────────────────────────┤
│  AAAX Kernel                                    │  ← Protection & governance
│  Capability binding, action gating, bootstrap   │
├─────────────────────────────────────────────────┤
│  SSSN Network                                   │  ← Communication fabric
│  Channels, systems, transport, discovery        │
└─────────────────────────────────────────────────┘
```

The suite is a LibOS — it imports from the kernel but the kernel has zero imports from the suite. Every suite-specific concept (expert roles, domain templates, world models) lives entirely in this layer. The kernel remains application-agnostic.

As the first citizen of AAAX, the suite is also the first citizen of the default LLLM LibOS. That means module activation is intentionally explicit: `lllm pkg install` makes a package available on disk, but the suite selects modules through config and AAAX boots LLLM in strict mode so nothing is activated implicitly from cwd or shared-package discovery.

### Capability Model

The suite is **fully capable** — it can analyze, research, plan, coordinate, and execute actions in the real world. What any given deployment is *allowed* to do is a **policy decision**, not an architectural constraint. In current AAAX/SSSN terms, governance happens through topology-scoped local channel wiring, mediated capability grants for remote resources or executors, and action-gated execution through AAAX-owned proxies or executors:

- A personal finance deployment might restrict to analysis-only (no trade execution) to avoid regulatory complexity.
- A supply chain deployment might allow full execution (trigger reorders, reroute shipments) with human-in-the-loop for high-value decisions.
- A research deployment might allow arbitrary code execution through an AAAX-owned interpreter or sandbox executor.
- A robotics-integrated deployment might authorize actuator commands with escalation for irreversible actions.

The architecture doesn't prescribe. The policy and executor bindings do.

---

## 2. The Problem

### Why Autonomous Analysis Agents?

Users across domains face three common problems:

1. **Knowledge gap.** No single person has expertise across all the domains that affect their decisions — macro, sector, policy, geopolitics, consumer trends.
2. **Continuous effort.** Analysis is not one-time. The world changes daily. Staying informed is a full-time job, and things are still missed.
3. **Scale mismatch.** One person cannot cover it all. Each analysis task requires a different combination of experts.

### Why Not Just Build Another Agent?

Existing AI analysis tools (OpenAI Deep Research, Perplexity, OpenClaw, Hermes) share a structural limitation: they are monolithic agents with fixed designs. **Imitation is not thinking.** These systems mimic analyst workflows through prompting without principled reasoning, uncertainty quantification, or the ability to improve over time. When a better monolith appears, the old one dies — the replacement cycle repeats.

### What's Needed

- **Configurable** expert roles — composable modules, not one agent with different prompts
- **Heterogeneous communication** — LLM agents and quantitative models as equal citizens
- **Governed** — topology-scoped local access, capability-gated mediated resources, action authorization, configurable safety policies
- **Improvable** — the system gets better over time, not just when the next model drops

---

## 3. Composition Model

Every expert in the Productive Suite is a composition of four module types:

```
Role Template  +  Data Channels  +  Reasoning Engine  +  Extensions  =  Expert
```

- **Role Template:** Workflow definition, system prompts, agent wiring (LLLM Tactic)
- **Data Channels:** Domain-specific feeds and data sources (SSSN Channels)
- **Reasoning Engine:** Analysis method (LLLM Prompts + tools)
- **Extensions:** Additional tools, skills, integrations (LLLM packages)

### Concrete Examples

| Expert | Role Template | Data Channels | Reasoning Engine | Extensions |
|---|---|---|---|---|
| AI Energy Analyst | Equity workflow | Oil + macro feeds | LLM reasoning (vanilla) or Analytica (advanced) | Alert system |
| AI Chip SCM Expert | SCM workflow | Semiconductor + trade | LLM + factor hybrid | Risk monitor |
| AI Manufacturing BI | BI workflow | Demand + commodity | Trend analysis | Report generator |
| AI Research Assistant | Research workflow | Papers + experiments | Evolutionary discovery (Genesys) | LaTeX writer |

### N-to-N Reuse

The same experts serve multiple analysis tasks in different combinations:

- **Energy Stock Analysis** needs: Equity Analyst + Commodity Expert + Policy Analyst + Macro Economist + Geopolitics
- **Chip Supply Chain Analysis** needs: Sector Specialist + Policy Analyst + Commodity Expert + Trade Analyst + Macro Economist
- **Manufacturing BI** needs: Macro Economist + Commodity Expert + Consumer/Trend + Sector Specialist + Policy Analyst

Same experts, different combinations. Each task is a unique configuration — not a unique agent.

### Three Ways to Use

1. **Use built-in templates.** Pre-configured experts that work out of the box with vanilla modules.
2. **Customize existing roles.** Swap data channels, reasoning engines, or tools. Drop in advanced modules for specific domains.
3. **Build entirely new roles.** Developers create novel expert configurations from scratch.

---

## 4. Module System

### 4.1 Vanilla Modules (Ship with v1)

The suite ships with **vanilla modules** that work immediately using standard LLM capabilities. These prove the composition model without requiring specialized research components.

| Module | Type | Description |
|---|---|---|
| **Standard Reasoning** | Reasoning Engine | LLM-based analysis with structured prompting, chain-of-thought, tool use |
| **Basic Memory** | Extensions | Conversation-based context management, simple retrieval |
| **Web Research** | Extensions | Web search, news retrieval, document reading |
| **Data Connector** | Data Channels | Adapters for common data sources (RSS feeds, APIs, CSV imports) |
| **Report Generator** | Extensions | Structured output formatting (markdown, PDF, dashboards) |
| **Standard Templates** | Role Templates | Pre-built workflows for common roles (analyst, researcher, monitor) |

Vanilla modules are **intentionally simple** — they demonstrate that the composition model works and that expert roles can be configured, recombined, and governed by the kernel. They establish the baseline that advanced modules improve upon.

### 4.2 Advanced Modules (Research-Backed, Installable)

Advanced modules are optimized replacements for vanilla modules, backed by peer-reviewed research. They are distributed as LLLM packages and can be **dropped in** wherever a vanilla module is used — the interface is the same, the quality is dramatically better.

**Neurosymbolic Reasoning** — *drop-in replacement for Standard Reasoning*

| Module | Venue | Replaces | Improvement |
|---|---|---|---|
| **Analytica** | ICLR '26 | Standard Reasoning | Soft propositional logic with calibrated uncertainty — principled hypothesis evaluation instead of prompt-based guessing |
| **TDL** | ICLR '24 | (theoretical foundation) | Proves neural-symbolic completeness — justifies why the neurosymbolic approach works |

Why upgrade: interpretable reasoning chains, reduced hallucination, integrates with quantitative models.

**Evolutionary Discovery** — *drop-in replacement for static analysis*

| Module | Venue | Replaces | Improvement |
|---|---|---|---|
| **Genesys** | NeurIPS '25 Spotlight | Static analysis workflows | Distributed evolutionary discovery — agents actively seek patterns instead of waiting to be asked |
| **AlphaWorld** | Planned | Standard world model | AlphaEvolve-style evolution of world foundation models for physical AI |

Why upgrade: foundation-model agnostic improvement, non-invasive (no retraining), scalable distributed evolution.

**Societal Analysis** — *drop-in replacement for Basic Memory + Data Connector*

| Module | Venue | Replaces | Improvement |
|---|---|---|---|
| **SocioDojo** | ICLR '24 Spotlight | Data Connector + Standard Templates | Lifelong societal environment backbone — continuous learning from news, time series, and knowledge across finance, economics, politics, culture |
| **AAPM** | FinAI @ ICLR '25 | Basic Memory | Alpha-seeking long-term memory — tracks what actually mattered, measured by excess returns |

Why upgrade: real-world tested across 30K+ time series, event-driven continuous learning, principled information advantage tracking.

**Agentic System** — *extends the composition model itself*

| Module | Venue | Replaces | Improvement |
|---|---|---|---|
| **Apeiron** | In progress | Static configuration | Closed-loop adaptation — the system evolves to match user needs over time |
| **ASDS** | In progress | Manual role design | Systematic design space exploration for LLM agent architectures |

### 4.3 Upgrade Path

The composition model makes upgrades seamless:

```bash
# Start with vanilla
aaax build ps --template energy-analyst --name my-suite

# Later: install Analytica
lllm pkg install ./releases/analytica-v1.zip --scope project
# Edit my-suite.toml:
# [suite.analysis.reasoning]
# engine = "analytica"

# Later: install AAPM
lllm pkg install ./releases/aapm-v1.zip --scope project
# [suite.analysis.reasoning]
# memory = "aapm"

# Later: add evolutionary discovery
lllm pkg install ./releases/genesys-v1.zip --scope project
# [suite.research]
# enabled = true
# engine = "genesys"
```

Same expert constellation. Same data channels. Same kernel governance. Better reasoning, memory, and discovery — module by module.

Install is not activation. The Productive Suite treats installed LLLM packages as available inventory; activation happens only through suite configuration and AAAX module loading. That keeps upgrades deliberate and reproducible.

---

## 5. Three Branches

### 5.1 Analysis Branch — The Mind

**Scope:** Finance, economics, policy, supply chain management, business intelligence, culture, society, and scientific analysis.

**Core capability:** Continuous monitoring, hypothesis evaluation, and decision support across societal and scientific domains. Individual research tasks — literature review, hypothesis evaluation, experiment design, report writing — are analysis tasks performed by appropriately configured expert roles. With vanilla modules: structured LLM analysis with web research. With advanced modules: lifelong societal environment model (SocioDojo), alpha-seeking memory (AAPM), soft-logic reasoning (Analytica).

**Example roles:** AI Economist, AI Equity Analyst, AI Commodity Expert, AI Policy Analyst, AI Consumer Trend Analyst, AI Macro Strategist, AI Research Analyst, AI Literature Reviewer.

### 5.2 Operations Branch — The Body

**Scope:** Planning and coordination for IoT sensors, robotic actuators, cyber-physical systems. Does not replace low-level control loops. Provides the decision and planning layer.

**Core capability:** Translates analysis-driven decisions into coordination signals for physical systems. Sensor data enters as SSSN channels. Planning outputs route through the action gate to AAAX-owned executors or otherwise authorized endpoints.

**Example roles:** AI Logistics Coordinator, AI Supply Chain Planner, AI Facility Monitor, AI Robot Planner.

**Architecture:** The intelligence lives upstream in Analysis and Research. Operations is primarily channel adapters and action translators. A sensor publishes to a channel. A planning agent reads analysis outputs and sensor data, produces an action plan. The action plan routes through AAAX's action gate. What happens next depends on the configured policy and which executor bindings the deployment allows.

### 5.3 Research Branch — The Phylogenetics

**Scope:** Community-level evolutionary discovery and long-term system improvement.

**Core distinction:** Individual research tasks (analyzing a paper, evaluating a hypothesis, designing an experiment) are **Analysis branch** activities — they are performed by expert roles configured for research domains. The Research branch is something fundamentally different: it is the **evolutionary process** by which the entire suite's strategies, models, and reasoning improve over time. It is phylogenetic intelligence — many agents exploring in parallel, competing, sharing discoveries, and propagating the best strategies across the population.

**Core capability:** The Research branch connects many analysis agents into a distributed evolutionary community, naturally supported by SSSN's network model. Each agent variant operates as a SSSN System. Candidate strategies propagate through BroadcastChannels. Evaluation results flow through WorkQueues. The evolutionary controller (Genesys) manages the population, selects the fittest, and spawns the next generation — all as standard SSSN system-of-systems coordination, not a special-purpose mechanism.

This mirrors how real scientific communities work: individual researchers do analysis (the Mind), but science as a whole advances through the evolutionary dynamics of a community — variation (many researchers exploring different directions), selection (peer review, replication, citation), and propagation (publications, adoption). The Research branch is the community, not the individual researcher.

**What evolves:**
- **Analysis strategies** — how experts reason about problems. The Research branch discovers and propagates better reasoning approaches across the constellation.
- **World models** — how the system understands its environment. AlphaWorld uses AlphaEvolve-style methods to evolve better societal world models through population-based search.
- **Role configurations** — which module combinations work best for which domains. The Research branch can discover that a particular combination of reasoning engine + memory + data channels outperforms others for a specific analysis task.

**Architecture:** A Research branch deployment is a population of AAAX-governed constellations connected through SSSN:

```text
Genesys controller
├── constellation-a  (candidate strategy A)
├── constellation-b  (candidate strategy B)
└── constellation-n  (candidate strategy N)
```

Candidate strategies, evaluation jobs, and selection signals move over ordinary SSSN channels. AAAX governs each local constellation; SSSN connects the larger evolutionary population.

This federation model depends on SSSN's public-channel transport being trustworthy. Current SSSN now tests the HTTP path directly and preserves typed `MessageContent` payloads over transport, so research populations can exchange typed strategies and evaluation signals without ad hoc serialization wrappers.


---

## 6. User Interface

### 6.1 CLI

```bash
# Build a new suite configuration from a template
aaax build ps --template energy-stock-analysis --name "my-energy-suite"

# Build interactively
aaax build ps --interactive

# Launch a configured suite
aaax launch my-energy-suite.toml

# Publish to the SSSN network
aaax launch my-energy-suite.toml --publish

# List available templates
aaax templates

# Install advanced modules
lllm pkg install ./releases/analytica-v1.zip --scope project
lllm pkg install ./releases/sociodojo-v1.zip --scope project
lllm pkg install ./releases/genesys-v1.zip --scope project

# Then edit the suite config to select modules and channels:
# [suite.analysis]
# roles = ["equity-analyst", "commodity-expert", "policy-analyst", "macro-economist", "forex-analyst"]
# [suite.analysis.reasoning]
# engine = "analytica"
# [suite.analysis.data]
# channels = ["sssn://news-provider/market-news", "market-data", "economic-indicators"]
```

### 6.2 Suite Configuration

```toml
[suite]
name = "Energy Stock Analysis"
type = "ps"

[suite.analysis]
roles = ["equity-analyst", "commodity-expert", "policy-analyst", "macro-economist"]

[suite.analysis.data]
channels = ["news-feed", "market-data", "economic-indicators"]

[suite.analysis.reasoning]
engine = "standard"  # vanilla default; change to "analytica" after installing
memory = "basic"     # vanilla default; change to "aapm" after installing

[suite.research]
enabled = false  # enable later with Genesys
# engine = "genesys"
# evolution_interval = "daily"

[suite.operations]
enabled = false  # enable when IoT integration is needed

[suite.policy]
# Action gate policy — what this deployment is allowed to do
execution = "analysis-only"  # or "full", "sandbox", "human-in-the-loop"
# This is a deployment decision, not an architectural constraint

[suite.network]
publish = false
# port = 8200
```

### 6.3 GUI (Future)

A GUI would add visual constellation editing, real-time monitoring, and a configuration wizard. The CLI is complete — GUI is a convenience layer.

---

## 7. Stakeholder Model

### Developers (Build with LLLM)
- Create reusable Tactics, Prompts, Agents, and tools
- Build new expert roles by composing modules
- Distribute as LLLM package zips or shared packages
- Publish advanced modules that upgrade vanilla components

### Providers (Publish on SSSN)
- News providers push articles via BroadcastChannel
- Market data vendors stream prices as periodic feeds
- Cloud providers expose compute as SSSN Systems
- Tool providers expose channels or executor endpoints that AAAX can mediate
- Any provider can join the open network

### Users (Use through AAAX)
- Install expert modules from LLLM package zips or shared package directories
- Subscribe to data channels and services from SSSN providers
- Configure and launch via `aaax build ps` / `aaax launch`
- Upgrade incrementally: vanilla → advanced, module by module

**Flow:** Developers create modules → Providers publish channels → Users compose and launch.

---

## 8. Comparison with Others

### Core Insight: Imitation Is Not Thinking

| Dimension | Existing (OpenClaw, Hermes, Deep Research...) | AAAX Productive Suite |
|---|---|---|
| **Architecture** | Fixed monolithic agent | Modular OS, configurable, upgradable |
| **Reasoning** | Prompt-based imitation | Vanilla LLM (default) → Neurosymbolic (advanced) |
| **Improvement** | Static — waits for next model | Vanilla (default) → Evolutionary discovery (advanced) |
| **Multi-system** | Single agent or homogeneous crew | Heterogeneous network (SSSN) |
| **Longevity** | Each release replaces the last | Kernel persists, modules upgrade |
| **Upgrade path** | Replace everything | Swap modules one at a time |

The structural difference: monolithic agents have a shelf-life. An OS gets upgraded.

---

## 9. Extensibility

The Productive Suite is the flagship, not the only possible suite. The AAAX kernel is application-agnostic. Other suites can be built for:

- **Robotics Suite** — full autonomy (needs SSSN low-latency transport)
- **Creative Suite** — AI filmmaking, game design, generative art (needs engine adapters)
- **Metaverse Suite** — persistent multi-agent worlds (excellent kernel fit)
- **Blockchain/DeFi Suite** — trustless coordination (needs on-chain capabilities)

The Operations branch of the Productive Suite serves as a bridge — proving the kernel can handle physical-world coordination before a dedicated Robotics Suite is built.

**Validation:** If another suite can be built without modifying the kernel, the kernel's abstractions are right.

---

## 10. Implementation Roadmap

### Phase 1: Foundation (Vanilla)
- CLI: `aaax build ps`, `aaax launch <suite-config>`, `aaax templates`
- Vanilla modules: Standard Reasoning, Basic Memory, Web Research, Data Connector, Report Generator
- Built-in templates: equity analyst, macro analyst, general researcher
- Test: single-expert and three-expert constellations running via CLI

### Phase 2: Multi-Role Composition
- Multi-expert networks (energy stock, chip SCM, manufacturing BI examples)
- Data channel subscriptions from external providers
- Heterogeneous systems (LLM agents + quantitative pipelines in same constellation)
- Test: five-expert constellation with shared channels

### Phase 3: Advanced Module Integration
- Package and distribute advanced modules as LLLM packages
- Demonstrate drop-in upgrade: vanilla → Analytica, Basic Memory → AAPM, etc.
- Integrate SocioDojo as advanced world model option
- Test: measurable quality improvement from vanilla to advanced

### Phase 4: Research Branch
- Integrate Genesys for evolutionary discovery
- Implement strategy evolution loop
- Connect research outputs to analysis branch
- Test: suite that demonstrably improves over time

### Phase 5: Operations Branch and Ecosystem
- Sensor channel adapters, planning output routing
- Provider integration templates
- Advanced module marketplace via LLLM packages
- GUI development

---

## Appendix A: Module Reference

### Vanilla Modules (v1)

| Module | Type | Status |
|---|---|---|
| Standard Reasoning | Reasoning Engine | Phase 1 |
| Basic Memory | Extensions | Phase 1 |
| Web Research | Extensions | Phase 1 |
| Data Connector | Data Channels | Phase 1 |
| Report Generator | Extensions | Phase 1 |
| Standard Templates | Role Templates | Phase 1 |

### Advanced Modules (Research-Backed)

| Module | Type | Venue | Replaces | Status |
|---|---|---|---|---|
| Analytica | Reasoning Engine | ICLR '26 | Standard Reasoning | Phase 3 |
| TDL | Foundation | ICLR '24 | — | Published |
| Genesys | Reasoning + Extensions | NeurIPS '25 Spotlight | Static workflows | Phase 4 |
| AlphaWorld | Reasoning Engine | — | Standard world model | Proposed |
| SocioDojo | Role Template + Data | ICLR '24 Spotlight | Data Connector + Templates | Phase 3 |
| AAPM | Data + Extensions | FinAI @ ICLR '25 | Basic Memory | Phase 3 |
| Apeiron | Extensions | — | Static config | In progress |
| ASDS | Role Templates | — | Manual design | In progress |

## Appendix B: PSI Organization Context

**Organization:** Productive Superintelligence (PSI)

**Mission:** To realize and maintain a state of equilibrium through an autonomous AI-agentic society, eliminating all systemic friction to optimize human welfare.

**Stack:**

```
PSI (organization)              — mission: autonomous AI-agentic society
├── AAAX (kernel)               — the OS, domain-agnostic
├── SSSN (network)              — the communication fabric
├── LLLM (framework)            — the development framework
└── AAAX-PS (flagship app)      — Productive Suite
     ├── Analysis branch        — the brain
     ├── Research branch        — the curiosity
     └── Operations branch      — the body
```

## Appendix C: References

- Junyan Cheng et al. "SocioDojo: Building Lifelong Analytical Agents with Real-world Text and Time Series." ICLR 2024 (Spotlight).
- Junyan Cheng et al. "Bridging Neural and Symbolic Representations with Transitional Dictionary Learning." ICLR 2024.
- Junyan Cheng et al. "AAPM: Large Language Model Agent-based Asset Pricing Models." FinAI @ ICLR 2025.
- Junyan Cheng et al. "Analytica: Soft Propositional Reasoning for Robust and Scalable LLM-Driven Analysis." ICLR 2026.
- Junyan Cheng et al. "Genesys: Language Modeling by Language Models." NeurIPS 2025 (Spotlight).
- Junyan Cheng et al. "Apeiron: A Scalable LLM-agentic Framework for Autonomous Full-lifecycle Demand-optimized Application Synthesis." ACL 2026 Findings.
- AAAX Kernel Design Note. (companion document)
- SSSN. https://sssn.one/
- LLLM. https://lllm.one/
