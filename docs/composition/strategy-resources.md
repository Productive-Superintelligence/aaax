# Strategy Resources

`StrategyResource` is the public resource record:

```python
from aaax import StrategyResource


resource = StrategyResource(
    kind="tactic",
    name="review",
    ref="psi://demo/analyst-pack/tactics/review",
    entrypoint="demo.tactics:review",
    description="Review one record batch.",
    metadata={"runtime": "python"},
)
```

## Fields

`kind`
: The resource category. Built-in values are `tactic`, `channel`, `service`,
  `schema`, `package`, `run`, `config`, `doc`, `example`, `snapshot`, `asset`,
  and `custom`.

`name`
: The local name used in the strategy and HTTP paths.

`ref`
: The stable package or service ref. Package imports preserve `psi://` refs.

`entrypoint`
: Optional Python import path. Tactics use this to bind local handlers.

`description`
: Short human-readable description.

`metadata`
: Structured hints copied from package resources, such as runtime, schema refs,
  examples, config defaults, service transport, package version, or package card.

## Local Name Versus Ref

The same package resource can have different local names in different
strategies:

```python
strategy.use_package("packages/review", prefix="analysts")
```

The tactic named `review` in the package becomes `analysts.review` locally, but
its ref remains:

```text
psi://demo/review/tactics/review
```

This lets a strategy compose multiple packages without rewriting their package
identity.

## Handler Binding

Resources are metadata by default. They become executable when AAAX stores a
handler under the same local name:

```python
strategy.tactic(
    "echo",
    ref="psi://demo/tools/tactics/echo",
    handler=lambda input_value, context=None: {"echo": input_value},
)
```

Handlers may be synchronous or asynchronous. If they accept a `context` keyword,
AAAX passes the request context.
