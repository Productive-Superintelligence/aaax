# Python API

AAAX's public Python API is intentionally compact. The objects still use the
name `Strategy`, but conceptually a strategy is the shell session: a mounted
resource table plus an optional top-level command.

## Strategy

```python
from aaax import Strategy
```

Constructor:

```python
Strategy(
    name: str,
    *,
    description: str = "",
    resources=(),
    runner=None,
    metadata=None,
)
```

`name` must be a path segment (no whitespace, `/`, `:`, `\`, or `%`, and not
`.` or `..`), or the constructor raises `ValueError`.

Common methods:

- `strategy.tactic(name, **kwargs)`
- `strategy.channel(name, **kwargs)`
- `strategy.service(name, **kwargs)`
- `strategy.package(name, **kwargs)`
- `strategy.snapshot(name, **kwargs)`
- `strategy.resource(kind, name, **kwargs)`
- `strategy.add_resource(resource, handler=None)`
- `strategy.add_tactic(tactic, name=None, ref=None, description=None, metadata=None)`
- `strategy.use_package(path, prefix=None, store=None, bind=True)`
- `strategy.attach_store(store)`
- `strategy.runner(fn)`
- `strategy.tactics()`
- `await strategy.arun(input_value=None, context=None)`
- `await strategy.invoke_resource(name, input_value=None, context=None)`

The resource helpers take `ref`, `entrypoint`, `description`, `metadata`, and
an optional `handler`, and return the strategy, so calls chain. A name that is
already taken raises `ValueError`.

`add_tactic` mounts an LLLM tactic; `strategy.tactics()` returns every tactic
resource that has a handler as an LLLM `Tactic` (plain functions are wrapped
with `lllm.as_tactic`, package tactics are loaded).

`strategy.store` is the channel store behind the channel resources, a
`StrategyStore` (from `aaax.strategy`) that opens the store on first use and
forwards store methods to it, or `None`. `attach_store(store)` sets it, from an
SSSN `LocalStore` or `RemoteStore`; a strategy has one store, and attaching a
different one raises `ValueError`.

`invoke_resource` raises `aaax.strategy.ResourceNotFoundError`, a `KeyError`,
for an unknown name.

## Models

```python
from aaax import StrategyResource, StrategyInfo
from aaax import StrategyRunRequest, StrategyRunResponse
```

`StrategyResource` describes one mounted resource. `StrategyInfo` describes a
full shell session. `StrategyRunRequest` and `StrategyRunResponse` are the HTTP
envelopes of the shell routes.

## Loading

```python
from aaax import load_strategy, strategy_from_package
```

`load_strategy(target)` accepts:

- a directory containing `strategy.py`;
- a directory containing `shell.py`, the name LLLM 0.3's `lllm shell` used;
- a directory containing `lllm.toml`;
- a direct Python file, with a `build_strategy()` factory or a `strategy`
  object;
- a direct `lllm.toml` file;
- a `module:attribute` target, a `Strategy` or a no-argument factory that
  returns one, imported from the working directory.

A directory is checked in that order, so a strategy file wins over the
package manifest next to it.

Don't name a strategy file `aaax.py`: in its folder that file shadows the
`aaax` package, so `lllm shell` and `python -m aaax` fail there. An `aaax.py`
from AAAX 0.2 still loads, with a `FutureWarning` that says to rename it to
`strategy.py`; in a directory it comes after `shell.py`.

`strategy_from_package(path, name=None, prefix=None, store=None, bind=True)`
creates a shell directly from one LLLM package, with the package card and
version in its metadata.

## Package Composition

```python
from aaax import add_package
```

`add_package(strategy, path, prefix=None, store=None, bind=True)` mutates and
returns the given strategy; `strategy.use_package` calls it. `prefix` names
resources `<prefix>.<name>`, `store` picks the store folder for a strategy
that has no store yet, and `bind=False` mounts metadata only.

## FastAPI

```python
from aaax import Strategy, create_strategy_app


strategy = Strategy("analysis-shell")
app = create_strategy_app(strategy)
```

The app stores the original strategy at `app.state.aaax_strategy`. Building it
mounts every tactic with LLLM's `create_tactic_app` and, for a strategy with a
store, opens the store and mounts SSSN's store API; without SSSN installed,
that raises `ImportError`.

## Command Line

```python
from aaax.cli import main


main(["inspect", "packages/analyst-pack"])
```

`aaax.cli.main(argv)` is the CLI that `aaax`, `python -m aaax`, and
`lllm shell` run.
