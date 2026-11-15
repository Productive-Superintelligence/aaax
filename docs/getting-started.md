# Getting Started

AAAX starts like a shell: point it at something package-shaped, inspect what it
can mount, then serve the command surface. Use a package folder when one package
already describes the system. Use a strategy file when you want a shell script
that mounts several packages or adds a top-level `/run` command.

## Install

```bash
python -m pip install aaax
```

AAAX is built on LLLM: this installs `lllm-core` with its FastAPI server and
adds `lllm shell` to the `lllm` command. From the LLLM side,
`pip install "lllm-core[shell]"` installs the same thing.

Channel resources are stored by SSSN. The package below declares a channel, so
install the `channels` extra to serve it:

```bash
python -m pip install "aaax[channels]"
```

## Mount And Serve A Package

Create a minimal LLLM package:

```text
analyst-pack/
  lllm.toml
  demo/
    __init__.py
    tactics.py
```

```toml title="analyst-pack/lllm.toml"
[package]
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

`lllm shell inspect analyst-pack` and `lllm shell serve analyst-pack` run the
same commands.

Call it:

```bash
curl -X POST http://127.0.0.1:8400/tactics/echo/run \
  -H 'content-type: application/json' \
  -d '{"input": {"text": "hello"}, "context": {"metadata": {"request": "quickstart"}}}'
```

```json
{"output": {"echo": {"text": "hello"}, "metadata": {"request": "quickstart"}}, "request_id": "...", "tactic": "echo"}
```

The tactic route is LLLM's tactic service: `context` has the shape of an LLLM
`CallContext`, and the tactic receives one. Put your own values in its
`metadata`; other keys that are not `CallContext` fields are dropped.

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

Prefixes keep mounted names distinct while preserving original `lllm://` refs
in metadata. A strategy can also mount LLLM tactics directly with
`add_tactic`; see [Use with LLLM](guides/lllm.md).

## Inspect Before Serving

```bash
aaax inspect analyst-pack
aaax inspect strategy.py --json
```

Inspection is the shell habit: check the local names before you run anything.
Those names become `/resources/{name}/invoke`, `/tactics/{name}/run`, and
`/channels/{name}/events`. Inspecting a package neither imports its code nor
creates its channel store; serving does both.
