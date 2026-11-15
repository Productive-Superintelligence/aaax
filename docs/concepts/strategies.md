# Strategies

A `Strategy` is an AAAX shell session. It is a mounted resource table plus an
optional top-level command. The table describes resources; handlers make selected
resources executable.

The table and the call envelopes are Pydantic models, and the executable parts
are LLLM's: a tactic resource is an LLLM tactic, served with LLLM's tactic
service, and a package resource comes from an LLLM package. A strategy can
still be just a table with a few local handlers; SSSN joins only when channel
resources need a store.

```python
from aaax import Strategy


shell = Strategy("analyst-shell")
shell.tactic(
    "review",
    ref="lllm://society/analysts/tactics/review",
    description="Review one record batch.",
)
shell.channel(
    "events",
    ref="lllm://society/source/channels/events",
    description="Incoming source events.",
)
```

## Resource Records

Each resource has:

- `kind`: package, tactic, channel, service, schema, run, config, doc, example,
  snapshot, asset, or custom.
- `name`: the local shell name used by endpoints.
- `ref`: the stable external ref, usually an `lllm://` ref.
- `entrypoint`: the Python import target when a package resource is executable.
- `description`: human-facing text.
- `metadata`: package, runtime, schema, examples, card, and other structured hints.

Names are local. Refs are stable. This distinction lets one shell mount two
packages that both contain `events` by naming them `source.events` and
`review.events` locally while retaining their package refs.

A name is unique in the strategy and is a path segment: no whitespace, `/`,
`:`, `\`, or `%`, and not `.` or `..`. The strategy's own name follows the same
rule, so `Strategy("My Strategy")` raises `ValueError`.

## Runner

A runner is the shell's top-level `/run` command:

```python
@shell.runner
def run(input_value, *, context=None):
    return {
        "input": input_value,
        "resource_count": len(shell.resources),
        "context": context or {},
    }
```

The runner may be sync or async and is called as
`runner(input_value, context=...)`. It receives `context`, as a plain dict,
only if it declares that parameter (or `**kwargs`), and the input only if it
has a positional parameter besides `context` (or `*args`): `def run(*,
context=None)` is called without the input. Handlers follow the same rules.

If no runner is set, AAAX returns a shell pack containing the strategy name,
the input, and the mounted resource list. That default makes inspection and
early integration useful before the shell has a custom workflow.

## Resource Invocation

Every mounted resource can be invoked:

```bash
curl -X POST http://127.0.0.1:8400/resources/review/invoke \
  -H 'content-type: application/json' \
  -d '{"input": {"records": []}}'
```

When a resource has no handler, AAAX returns the resource metadata, input, and
context. When a handler is bound, AAAX calls it and returns the output envelope:

- A tactic resource runs exactly as `POST /tactics/{name}/run` runs it: the
  `context` has the shape of an LLLM `CallContext`, and the tactic receives
  one.
- Other handlers receive the `context` as a plain dict.
- A channel resource without a handler is served by the strategy's channel
  store, when it has one: the input names an `op`, `append`, `query` (the
  default), or `info`.

`await strategy.arun(input_value, context=None)` and
`await strategy.invoke_resource(name, input_value, context=None)` do the same
from Python; an unknown name raises `ResourceNotFoundError`, a `KeyError`.
