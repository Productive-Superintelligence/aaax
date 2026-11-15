# CLI Shell

The CLI shell is the human-facing AAAX surface. It keeps the workflow close to
a normal shell habit: inspect what is mounted, then serve the same strategy for
other callers. It runs as `aaax` and, inside the LLLM command, as
`lllm shell`; the two are the same CLI.

## Inspect

```bash
aaax inspect packages/analyst-pack
aaax inspect strategy.py
```

Inspection prints the local shell names, resource kinds, and original `lllm://`
refs. Use it before running a package so name collisions, prefixes, and missing
handlers are visible. Inspecting a package neither imports its code nor creates
its channel store; serving does both.

## Serve

```bash
aaax serve strategy.py --host 127.0.0.1 --port 8400
aaax serve packages/analyst-pack --port 8400
lllm shell serve packages/analyst-pack --port 8400
```

`serve` builds the strategy app and runs it with Uvicorn. A strategy with
channels needs SSSN for its store; without it, `serve` stops with
`Channel stores need the sssn package: pip install sssn`.

`launch` is currently an alias for `serve`:

```bash
aaax launch packages/analyst-pack --port 8400
```

## Script Shape

For multi-package systems, a `strategy.py` file is the shell script:

```python
from aaax import Strategy


def build_strategy() -> Strategy:
    shell = Strategy("analysis-shell")
    shell.use_package("packages/source-channels", prefix="sources")
    shell.use_package("packages/analyst-tactics", prefix="analysts")
    return shell
```

The CLI does not hide the package model. It makes the mounted strategy visible
enough for a human to decide what to call next.
