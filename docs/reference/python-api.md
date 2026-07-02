# Python API

AAAX's public Python API is intentionally compact.

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

Common methods:

- `strategy.tactic(name, **kwargs)`
- `strategy.channel(name, **kwargs)`
- `strategy.service(name, **kwargs)`
- `strategy.package(name, **kwargs)`
- `strategy.snapshot(name, **kwargs)`
- `strategy.resource(kind, name, **kwargs)`
- `strategy.add_resource(resource, handler=None)`
- `strategy.use_package(path, prefix=None, store=None, bind=True)`
- `strategy.runner(fn)`
- `await strategy.arun(input_value=None, context=None)`
- `await strategy.invoke_resource(name, input_value=None, context=None)`

## Models

```python
from aaax import StrategyResource, StrategyInfo
from aaax import StrategyRunRequest, StrategyRunResponse
```

`StrategyResource` describes one resource. `StrategyInfo` describes a full
strategy. `StrategyRunRequest` and `StrategyRunResponse` are the HTTP envelopes.

## Loading

```python
from aaax import load_strategy, strategy_from_package
```

`load_strategy(target)` accepts:

- a directory containing `strategy.py`;
- a directory containing `aaax.py`;
- a directory containing `psi.toml`;
- a direct Python file;
- a direct `psi.toml` file;
- a `module:attribute` target.

`strategy_from_package(path, name=None, prefix=None, store=None, bind=True)`
creates a strategy directly from one PsiHub package.

## Package Composition

```python
from aaax import add_package
```

`add_package(strategy, path, prefix=None, store=None, bind=True)` mutates and
returns the given strategy.

## FastAPI

```python
from aaax import create_strategy_app


app = create_strategy_app(strategy)
```

The app stores the original strategy at `app.state.aaax_strategy`.
