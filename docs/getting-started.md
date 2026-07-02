# Getting Started

AAAX starts like a shell: point it at something package-shaped, inspect what it
can mount, then serve the command surface. Use a package folder when one package
already describes the system. Use a strategy file when you want a shell script
that mounts several packages or adds a top-level `/run` command.

## Install

```bash
python -m pip install aaax
```

For package and channel binding, install the PSI stack integration packages:

```bash
python -m pip install "aaax[integrations]" lllm-core sssn psihub
```

## Mount And Serve A Package

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

Enter the shell:

```bash
aaax inspect analyst-pack
aaax serve analyst-pack --port 8400
```

Call it:

```bash
curl -X POST http://127.0.0.1:8400/tactics/echo/run \
  -H 'content-type: application/json' \
  -d '{"input": {"text": "hello"}, "context": {"request": "quickstart"}}'
```

## Write A Shell Script

When one package is not enough, use a strategy file:

```python title="strategy.py"
from aaax import Strategy


def build_strategy() -> Strategy:
    shell = Strategy(
        "analysis-shell",
        description="Mount source channels and analyst tactics.",
    )
    shell.use_package("packages/source-channels", prefix="sources")
    shell.use_package("packages/analyst-tactics", prefix="analysts")

    @shell.runner
    def run(input_value, *, context=None):
        return {
            "input": input_value,
            "resources": [resource.ref for resource in shell.resources],
            "context": context or {},
        }

    return shell
```

```bash
aaax serve strategy.py --port 8400
```

Prefixes keep mounted names distinct while preserving original `psi://` refs in
metadata.

## Inspect Before Serving

```bash
aaax inspect analyst-pack
aaax inspect strategy.py --json
```

Inspection is the shell habit: check the local names before you run anything.
Those names become `/resources/{name}/invoke`, `/tactics/{name}/run`, and
`/channels/{name}/events`.
