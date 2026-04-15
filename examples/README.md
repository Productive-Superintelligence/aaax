# AAAX Examples

These examples match the current first kernel slice. They are intentionally small and runnable.

Run commands from the repository root unless a README says otherwise.

## CLI Entry

AAAX currently exposes a command-line interface, not an interactive shell.

```bash
aaax --help
python -m aaax --help
aaax modules list
```

The main long-running command is:

```bash
aaax launch <config_path>
```

If you want a one-shot CLI inspection instead of the long-running loop:

```bash
aaax launch <config_path> --once
```

## Examples

| Directory | What it shows | How to run |
| --- | --- | --- |
| `minimal-kernel/` | Minimal config, one-shot bootstrap, `aaax launch --once`, and the long-running `aaax launch` path | `python examples/minimal-kernel/run_once.py` |
| `capability-roundtrip/` | Dock a system, request a capability, then request an action through AAAX | `python examples/capability-roundtrip/run_demo.py` |
| `public-channels/` | Run AAAX with a docked system that exposes a `PUBLIC` SSSN channel over HTTP | `python examples/public-channels/run_server.py` |

## Monorepo Setup

If you are running the examples from this checkout, install the repo once first:

```bash
pip install -e ./sssn
pip install -e ./lllm
pip install --no-deps -e .
pip install -r requirements-monorepo.txt
```

If you already installed `aaax` from PyPI in another environment, that is also fine.
