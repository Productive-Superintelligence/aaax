# Strategy Resources

`StrategyResource` is the public record for one mounted resource:

```python
from aaax import StrategyResource


resource = StrategyResource(
    kind="tactic",
    name="review",
    ref="lllm://demo/analyst-pack/tactics/review",
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
: The local name used in the shell and HTTP paths. It is unique in the
  strategy and a path segment: no whitespace, `/`, `:`, `\`, or `%`, and not
  `.` or `..`.

`ref`
: The stable package or service ref. Package imports preserve `lllm://` refs.

`entrypoint`
: Optional Python import path. Tactics use this to bind local handlers.

`description`
: Short human-readable description.

`metadata`
: Structured hints copied from package resources, such as runtime, schema refs,
  examples, config defaults, service transport, package version, or package card.

## Local Name Versus Ref

The same package resource can have different local names in different shells:

```python
from aaax import Strategy


shell = Strategy("analysis-shell")
shell.use_package("packages/review", prefix="analysts")
```

The tactic named `review` in the package becomes `analysts.review` locally, but
its ref remains:

```text
lllm://demo/review/tactics/review
```

This lets a shell compose multiple packages without rewriting their package
identity.

## Handler Binding

Resources are metadata by default. They become executable when AAAX stores a
handler under the same local name:

```python
shell.tactic(
    "echo",
    ref="lllm://demo/tools/tactics/echo",
    handler=lambda input_value, context=None: {"echo": input_value},
)
```

Handlers may be synchronous or asynchronous. A handler receives `context` only
if it declares it (or `**kwargs`), and the input only if it has a positional
parameter besides `context`.

A tactic resource's handler is an LLLM tactic: a `Tactic` is used as it is, and
a plain function is wrapped with `lllm.as_tactic`. It is served at
`/tactics/{name}/` and receives the request context as an LLLM `CallContext`.
`add_tactic` mounts an LLLM tactic and fills in the record from its info:

```python
from lllm import as_tactic


shell.add_tactic(as_tactic(lambda text: text.upper(), name="shout"))
```

Other resources' handlers receive the context as a plain dict, and a channel
resource without a handler is backed by the strategy's channel store (see
[Channels And Services](channels-services.md)).
