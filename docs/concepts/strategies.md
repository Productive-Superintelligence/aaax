# Strategies

A `Strategy` is AAAX's application boundary. It is a small registry plus an
optional runner. The registry describes resources; handlers make selected
resources executable.

```python
from aaax import Strategy


strategy = Strategy("analyst-system")
strategy.tactic(
    "review",
    ref="psi://society/analysts/tactics/review",
    description="Review one record batch.",
)
strategy.channel(
    "events",
    ref="psi://society/source/channels/events",
    description="Incoming source events.",
)
```

## Resource Records

Each resource has:

- `kind`: package, tactic, channel, service, schema, run, config, doc, example,
  snapshot, asset, or custom.
- `name`: the local strategy name used by endpoints.
- `ref`: the stable external ref, usually a `psi://` ref.
- `entrypoint`: the Python import target when a package resource is executable.
- `description`: human-facing text.
- `metadata`: package, runtime, schema, examples, card, and other structured hints.

Names are local. Refs are stable. This distinction lets one strategy import two
packages that both contain `events` by naming them `source.events` and
`review.events` locally while retaining their package refs.

## Runner

A runner is the top-level `/run` behavior:

```python
@strategy.runner
def run(input_value, *, context=None):
    return {
        "input": input_value,
        "resource_count": len(strategy.resources),
        "context": context or {},
    }
```

If no runner is set, AAAX returns a strategy pack containing the input and
resource list. That default makes inspection and early integration useful before
an application has a custom workflow.

## Resource Invocation

Every resource can be invoked:

```bash
curl -X POST http://127.0.0.1:8400/resources/review/invoke \
  -H 'content-type: application/json' \
  -d '{"input": {"records": []}}'
```

When a resource has no handler, AAAX returns the resource metadata, input, and
context. When a handler is bound, AAAX calls it and returns the output envelope.
