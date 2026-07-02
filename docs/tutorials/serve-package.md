# Serve A Package

This tutorial creates a tiny package and serves it through AAAX.

## 1. Create Files

```bash
mkdir -p analyst-pack/demo
touch analyst-pack/demo/__init__.py
```

```python title="analyst-pack/demo/tactics.py"
def echo(input_value, *, context=None):
    metadata = getattr(context, "metadata", {})
    return {"echo": input_value, "metadata": metadata}
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

[card]
summary = "Small local package for AAAX."
tags = ["demo", "analysis"]
suggested_commands = ["aaax serve ."]

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

## 2. Inspect

```bash
aaax inspect analyst-pack
```

Expected resources include package, tactic, channel, service, and run records.

## 3. Serve

```bash
aaax serve analyst-pack --port 8400
```

## 4. Call

```bash
curl -X POST http://127.0.0.1:8400/tactics/echo/run \
  -H 'content-type: application/json' \
  -d '{"input": {"text": "hello"}, "context": {"request": "tutorial"}}'
```

The output should echo your input and include the context metadata.
