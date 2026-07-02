# Getting Started

AAAX can start from either a package manifest or a strategy file. Use a package
folder when one package already describes the application. Use a strategy file
when you want to compose several packages or add a custom top-level runner.

## Install

```bash
python -m pip install aaax
```

For package and channel binding, install the PSI stack integration packages:

```bash
python -m pip install "aaax[integrations]" lllm-core sssn psihub
```

## Serve A Package

Create a minimal package:

```text
analyst-pack/
  psi.toml
  demo/
    __init__.py
    tactics.py
```

```toml title="analyst-pack/psi.toml"
[package]
psi_version = "0.1"
org = "demo"
name = "analyst-pack"
version = "0.1.0"
kind = "app"
primary = "runs.local"
description = "Demo analyst package."

[tactics.echo]
entry = "demo.tactics:echo"
runtime = "python"
description = "Echo one payload."

[channels.events]
form = "log"
description = "Application event stream."

[services.api]
tactic = "echo"
transport = "fastapi"
description = "HTTP-facing echo service."

[runs.local]
tactics = ["echo"]
channels = ["events"]
services = ["api"]
```

```python title="analyst-pack/demo/tactics.py"
def echo(input_value, *, context=None):
    metadata = getattr(context, "metadata", {})
    return {"echo": input_value, "metadata": metadata}
```

Serve it:

```bash
aaax serve analyst-pack --port 8400
```

Call it:

```bash
curl -X POST http://127.0.0.1:8400/tactics/echo/run \
  -H 'content-type: application/json' \
  -d '{"input": {"text": "hello"}, "context": {"request": "quickstart"}}'
```

## Compose Packages

When one package is not enough, use a strategy file:

```python title="strategy.py"
from aaax import Strategy


def build_strategy() -> Strategy:
    strategy = Strategy(
        "analysis-workbench",
        description="Combine source channels and analyst tactics.",
    )
    strategy.use_package("packages/source-channels", prefix="sources")
    strategy.use_package("packages/analyst-tactics", prefix="analysts")

    @strategy.runner
    def run(input_value, *, context=None):
        return {
            "input": input_value,
            "resources": [resource.ref for resource in strategy.resources],
            "context": context or {},
        }

    return strategy
```

```bash
aaax serve strategy.py --port 8400
```

The prefixes keep local resource names distinct while preserving original
`psi://` refs in metadata.

## Inspect Before Serving

```bash
aaax inspect analyst-pack
aaax inspect strategy.py --json
```

Inspection is useful when a package imports many resources. It shows the names
that will appear under `/resources/{name}/invoke`, `/tactics/{name}/run`, and
`/channels/{name}/events`.
