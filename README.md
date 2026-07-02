# AAAX

AAAX is the PSI strategy and launch boundary.

A `Strategy` names the LLLM tactics, SSSN channels, service endpoints, package
refs, configuration, docs, examples, and local runner that together form one
useful system. Its first public surface is a FastAPI server: point AAAX at a
strategy file or a PsiHub package folder and it exposes a small service that
humans, scripts, and future coding-agent workflows can call.

AAAX stays lightweight. It does not replace LLLM, SSSN, PsiHub, Codex, Claude
Code, schedulers, sandboxes, or deployment platforms. It composes resources and
prepares an application-facing environment around them.

## Install

```bash
python -m pip install aaax
```

For local composition with the PSI stack:

```bash
python -m pip install "aaax[integrations]" lllm-core sssn psihub
```

## Load A PsiHub Package

If a folder contains `psi.toml`, AAAX can serve it directly:

```bash
aaax serve packages/analyst-pack --port 8400
```

AAAX reads the manifest and imports these resource types into one strategy:

- package metadata and package card hints
- schemas, tactics, services, runs, and config
- SSSN channels and snapshots
- docs, examples, and assets

Tactics with Python entrypoints are bound to `/tactics/{name}/run`. Channels are
backed by a local SSSN store and exposed through `/channels/{name}/events`.
Services that point at one tactic are also invokable as resources.

```bash
curl -X POST http://127.0.0.1:8400/tactics/finance_baseline/run \
  -H 'content-type: application/json' \
  -d '{"input": {"records": []}, "context": {"request": "demo"}}'
```

Append and query channel events:

```bash
curl -X POST http://127.0.0.1:8400/channels/events/events \
  -H 'content-type: application/json' \
  -d '{"input": {"kind": "record", "payload": {"text": "hello"}}}'

curl http://127.0.0.1:8400/channels/events/events?limit=10
```

## Define A Strategy

```python
from aaax import Strategy


def build_strategy() -> Strategy:
    strategy = Strategy(
        "analyst-system",
        description="Combine source channels and analyst tactics.",
    )
    strategy.channel(
        "events",
        ref="psi://society/source-channels/channels/finance_ticks",
        description="Incoming source records.",
    )
    strategy.tactic(
        "finance_baseline",
        ref="psi://society/analyst-tactics/tactics/finance_baseline",
        description="Deterministic analyst tactic.",
    )

    @strategy.runner
    def run(input_value, *, context=None):
        return {
            "strategy": "analyst-system",
            "input": input_value,
            "resources": [resource.ref for resource in strategy.resources],
        }

    return strategy
```

You can also compose package resources into a custom strategy:

```python
from aaax import Strategy


strategy = Strategy("analysis-workbench")
strategy.use_package("packages/source-channels", prefix="sources")
strategy.use_package("packages/analyst-tactics", prefix="analysts")
```

## Serve It

```bash
aaax serve strategy.py --port 8400
```

Then call the strategy:

```bash
curl -X POST http://127.0.0.1:8400/run \
  -H 'content-type: application/json' \
  -d '{"input": {"task": "summarize"}}'
```

Useful endpoints:

- `GET /health`
- `GET /strategy`
- `GET /resources`
- `GET /packages`
- `GET /tactics`
- `POST /tactics/{name}/run`
- `GET /channels`
- `POST /channels/{name}/events`
- `GET /channels/{name}/events`
- `POST /run`
- `POST /resources/{name}/invoke`
