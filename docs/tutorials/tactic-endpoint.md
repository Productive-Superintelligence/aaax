# Tactic Endpoint

Tactics are the most direct executable resources mounted in the AAAX shell.

## 1. Write A Tactic

```python title="demo/tactics.py"
def classify(input_value, *, context=None):
    text = input_value.get("text", "")
    label = "empty" if not text.strip() else "text"
    return {"label": label, "text": text}
```

## 2. Declare It

```toml title="psi.toml"
[tactics.classify]
entry = "demo.tactics:classify"
runtime = "python"
description = "Classify one input payload."
```

## 3. Serve The Shell And Call

```bash
aaax serve . --port 8400
```

```bash
curl -X POST http://127.0.0.1:8400/tactics/classify/run \
  -H 'content-type: application/json' \
  -d '{"input": {"text": "hello"}}'
```

## Context

Request context is passed as LLLM `CallContext.metadata` when LLLM is installed:

```bash
curl -X POST http://127.0.0.1:8400/tactics/classify/run \
  -H 'content-type: application/json' \
  -d '{
    "input": {"text": "hello"},
    "context": {"request": "trace-me"}
  }'
```

Plain callables can accept `context=None`; LLLM tactic subclasses receive the
same context through their `run` or `arun` boundary.
