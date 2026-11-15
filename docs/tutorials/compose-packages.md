# Compose Packages

Use a strategy file when the shell needs more than one package or custom
top-level behavior.

## 1. Import Packages

```python title="strategy.py"
from aaax import Strategy


def build_strategy() -> Strategy:
    shell = Strategy(
        "analysis-shell",
        description="Mount source channels and analyst tactics.",
    )
    shell.use_package("packages/source-pack", prefix="source")
    shell.use_package("packages/analyst-pack", prefix="analyst")
    return shell
```

The resource `events` from `source-pack` becomes `source.events`. The resource
`echo` from `analyst-pack` becomes `analyst.echo`. Both keep their package
refs, such as `lllm://demo/analyst-pack/tactics/echo`. Without the prefixes,
the second package would be rejected if its names clashed with the first's.

Both packages share the strategy's one channel store, at
`packages/source-pack/.lllm/network`: the first package with channels picks
it, and `source.events` is its channel there. Install `aaax[channels]` to
serve channels.

## 2. Add A Runner

```python title="strategy.py"
from aaax import Strategy


def build_strategy() -> Strategy:
    shell = Strategy("analysis-shell")
    shell.use_package("packages/source-pack", prefix="source")
    shell.use_package("packages/analyst-pack", prefix="analyst")

    @shell.runner
    def run(input_value, *, context=None):
        return {
            "task": input_value,
            "resources": [resource.name for resource in shell.resources],
            "context": context or {},
        }

    return shell
```

## 3. Serve The Shell And Call

```bash
aaax serve strategy.py --port 8400
```

```bash
curl -X POST http://127.0.0.1:8400/run \
  -H 'content-type: application/json' \
  -d '{"input": {"task": "review"}}'
```

Call a prefixed tactic:

```bash
curl -X POST http://127.0.0.1:8400/tactics/analyst.echo/run \
  -H 'content-type: application/json' \
  -d '{"input": {"text": "hello"}}'
```

Prefixes use dots in local names. FastAPI path variables preserve those names,
and the tactic still reports its package ref in `/tactics/analyst.echo/info`.

To mount an LLLM tactic of your own next to the packages, add it in
`build_strategy` with `shell.add_tactic(tactic)`; see
[Use with LLLM](../guides/lllm.md#mount-lllm-tactics).
