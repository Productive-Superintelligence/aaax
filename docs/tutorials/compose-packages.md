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
`echo` from `analyst-pack` becomes `analyst.echo`.

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

Prefixes use dots in local names. FastAPI path variables preserve those names.
