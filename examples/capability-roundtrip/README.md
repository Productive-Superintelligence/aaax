# Capability Roundtrip

This example shows a complete one-shot AAAX control flow:

1. boot a kernel
2. dock a small client system
3. request an execute capability
4. use that capability to request an action through the AAAX action gate
5. print both replies

## Files

- `run_demo.py` — complete runnable roundtrip

## Run

From the repo root:

```bash
python examples/capability-roundtrip/run_demo.py
```

The script exits on its own after printing the granted capability and the action-gate response.

## Enter the CLI

AAAX does not have an interactive shell yet. The CLI entry point is:

```bash
aaax --help
python -m aaax --help
```

This specific example is Python-first because the current CLI does not yet provide a one-shot request shell for capability and action-gate flows.
