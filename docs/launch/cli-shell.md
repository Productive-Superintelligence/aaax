# CLI Shell

The CLI shell is the human-facing AAAX surface. It keeps the workflow close to
a normal shell habit: inspect what is mounted, then serve the same strategy for
other callers.

## Inspect

```bash
aaax inspect packages/analyst-pack
aaax inspect strategy.py
```

Inspection prints the local shell names, resource kinds, and original `psi://`
refs. Use it before running a package so name collisions, prefixes, and missing
handlers are visible.

## Serve

```bash
aaax serve strategy.py --host 127.0.0.1 --port 8400
aaax serve packages/analyst-pack --port 8400
```

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
