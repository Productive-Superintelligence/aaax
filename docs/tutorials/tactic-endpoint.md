# Tactic Endpoint

Tactics are the most direct executable resources mounted in the AAAX shell.
Each one is served as an LLLM tactic service at `/tactics/{name}/`.

## 1. Write A Tactic

```python title="demo/tactics.py"
def classify(input_value, *, context=None):
    text = input_value.get("text", "")
    label = "empty" if not text.strip() else "text"
    return {"label": label, "text": text}
```

## 2. Declare It

```toml title="lllm.toml"
[package]
org = "demo"
name = "classify-pack"
version = "0.1.0"
kind = "app"
description = "Classify payloads."

[tactics.classify]
entry = "demo.tactics:classify"
runtime = "python"
description = "Classify one input payload."
```

The package has no channels, so it serves without SSSN.

## 3. Serve The Shell And Call

```bash
aaax serve . --port 8400
```

```bash
curl -X POST http://127.0.0.1:8400/tactics/classify/run \
  -H 'content-type: application/json' \
  -d '{"input": {"text": "hello"}}'
```

```json
{"output": {"label": "text", "text": "hello"}, "request_id": "...", "tactic": "classify"}
```

## Context

The request `context` has the shape of an LLLM `CallContext`, and the tactic
receives one. Put your own values in `metadata`, and pass a `request_id` to
trace the call; keys that are not `CallContext` fields are dropped.

```bash
curl -X POST http://127.0.0.1:8400/tactics/classify/run \
  -H 'content-type: application/json' \
  -d '{
    "input": {"text": "hello"},
    "context": {"metadata": {"request": "trace-me"}, "request_id": "trace-1"}
  }'
```

The response carries the same `request_id`. Plain callables can accept
`context=None` and read `context.metadata`; LLLM tactic subclasses receive the
same context through their `run` or `arun` boundary.

## A Typed LLLM Tactic

An LLLM `Tactic` subclass declares its input and output types, which the
service validates and publishes:

```python title="demo/tactics.py"
from pydantic import BaseModel

from lllm import Tactic


class Text(BaseModel):
    text: str


class Label(BaseModel):
    label: str
    text: str


class Classify(Tactic[Text, Label]):
    name = "classify"
    description = "Classify one input payload."
    input_type = Text
    output_type = Label

    def _run(self, input_value, *, context=None):
        label = "empty" if not input_value.text.strip() else "text"
        return Label(label=label, text=input_value.text)
```

Point the manifest at the class, `entry = "demo.tactics:Classify"`, and AAAX
instantiates it. Now `{"input": {"text": 3}}` is a `400` with a `SchemaError`,
and `GET /tactics/classify/info` returns the description, the input and output
schemas, and the tactic's ref, `lllm://demo/classify-pack/tactics/classify`.
