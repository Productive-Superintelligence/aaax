# AAAX

AAAX is the PSI strategy layer.

A `Strategy` is a small application pack that names the LLLM tactics, SSSN
channels, service endpoints, package refs, and local runner that together form
one useful system. The first public surface is a FastAPI server. Agent files,
coding-agent skills, and IDE/subagent projections can be generated later from
the same strategy metadata.

## Install

```bash
python -m pip install aaax
```

For local composition with the PSI stack:

```bash
python -m pip install "aaax[integrations]" lllm-core sssn psihub
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
- `POST /run`
- `POST /resources/{name}/invoke`

AAAX does not replace LLLM, SSSN, or PsiHub. It is the layer that packages
their modules into one application strategy and exposes that strategy as a
normal service.
