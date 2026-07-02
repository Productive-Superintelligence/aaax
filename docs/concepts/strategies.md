# Strategies

A `Strategy` is an AAAX shell session. It is a mounted resource table plus an
optional top-level command. The table describes resources; handlers make selected
resources executable.

```python
from aaax import Strategy


shell = Strategy("analyst-shell")
shell.tactic(
    "review",
    ref="psi://society/analysts/tactics/review",
    description="Review one record batch.",
)
shell.channel(
    "events",
    ref="psi://society/source/channels/events",
    description="Incoming source events.",
)
```

## Resource Records

Each resource has:

- `kind`: package, tactic, channel, service, schema, run, config, doc, example,
  snapshot, asset, or custom.
- `name`: the local shell name used by endpoints.
- `ref`: the stable external ref, usually a `psi://` ref.
- `entrypoint`: the Python import target when a package resource is executable.
- `description`: human-facing text.
- `metadata`: package, runtime, schema, examples, card, and other structured hints.

Names are local. Refs are stable. This distinction lets one shell mount two
packages that both contain `events` by naming them `source.events` and
`review.events` locally while retaining their package refs.

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

If no runner is set, AAAX returns a shell pack containing the input and mounted
resource list. That default makes inspection and early integration useful before
the shell has a custom workflow.

## Resource Invocation

Every mounted resource can be invoked:

```bash
curl -X POST http://127.0.0.1:8400/resources/review/invoke \
  -H 'content-type: application/json' \
  -d '{"input": {"records": []}}'
```

When a resource has no handler, AAAX returns the resource metadata, input, and
context. When a handler is bound, AAAX calls it and returns the output envelope.
