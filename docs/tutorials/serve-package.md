# Serve A Package

This tutorial creates a tiny LLLM package, mounts it in the AAAX shell, and
serves it. The package declares a channel, so install the channels extra
first:

```bash
python -m pip install "aaax[channels]"
```

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

```toml title="analyst-pack/lllm.toml"
[package]
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

```text
analyst-pack: Demo analyst package.
package analyst-pack lllm://demo/analyst-pack
tactic echo lllm://demo/analyst-pack/tactics/echo
channel events lllm://demo/analyst-pack/channels/events
service api lllm://demo/analyst-pack/services/api
run local lllm://demo/analyst-pack/runs/local
```

This is the shell's first move: list what is mounted before you run it.
Inspecting reads only the manifest; it imports no package code and creates no
channel store.

## 3. Open The Shell Surface

```bash
aaax serve analyst-pack --port 8400
```

Serving imports the tactic and creates the channel store at
`analyst-pack/.lllm/network`.

## 4. Call

```bash
curl -X POST http://127.0.0.1:8400/tactics/echo/run \
  -H 'content-type: application/json' \
  -d '{"input": {"text": "hello"}, "context": {"metadata": {"request": "tutorial"}}}'
```

The output echoes your input and the context metadata:

```json
{"output": {"echo": {"text": "hello"}, "metadata": {"request": "tutorial"}}, "request_id": "...", "tactic": "echo"}
```
