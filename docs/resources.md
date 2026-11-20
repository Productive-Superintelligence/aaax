# Resources

A resource is one named part of a strategy. Its record, a
`StrategyResource`, says what the part is and where it comes from, and a
handler, when it has one, makes it callable. The two are kept apart on
purpose: a strategy can list parts it does not run itself, such as a doc, a
remote service, or a package mounted for reference, in the same table as
the parts it serves, so a person or an agent reading the table sees the
whole application.

```python title="kinds.py"
from fastapi.testclient import TestClient

from aaax import Strategy, StrategyResource, create_strategy_app


def lookup(order_id: str, context=None) -> dict:
    return {"order": order_id, "context": type(context).__name__}


def refund(order: dict, context=None) -> dict:
    return {"refunded": order["id"], "context": type(context).__name__}


strategy = Strategy("orders")
strategy.add_resource(  # (1)!
    StrategyResource(
        kind="tactic",
        name="lookup",
        ref="lllm://acme/orders/tactics/lookup",
        description="Find an order by id.",
    ),
    handler=lookup,
)
strategy.service("refunds", handler=refund)  # (2)!
strategy.resource(  # (3)!
    "doc",
    "policy",
    description="The refund policy.",
    metadata={"path": "POLICY.md"},
)

client = TestClient(create_strategy_app(strategy))


def invoke(name, value):
    body = {"input": value}
    return client.post(f"/resources/{name}/invoke", json=body).json()


print(invoke("lookup", "A-1001")["output"])  # (4)!
#> {'order': 'A-1001', 'context': 'CallContext'}
print(invoke("refunds", {"id": "A-1001"})["output"])
#> {'refunded': 'A-1001', 'context': 'dict'}
print(invoke("policy", "Can I return shoes?")["output"])  # (5)!
"""
{
    'resource': {
        'name': 'policy',
        'kind': 'doc',
        'ref': None,
        'entrypoint': None,
        'description': 'The refund policy.',
        'metadata': {'path': 'POLICY.md'},
    },
    'input': 'Can I return shoes?',
    'context': {},
}
"""
```

1. The long form: build the record yourself and pass the handler with it.
   The shortcuts on the next lines build the record for you.
2. A service resource with a handler.
3. A doc resource with no handler. It is part of the table all the same.
4. The tactic resource's handler is wrapped as an LLLM tactic, so it
   receives a `CallContext`. The service's handler receives the context as
   a plain dict.
5. A resource without a handler answers with its own record, the input,
   and the context, so calling it still tells the caller what it is.

## The record

| Field | Default | Meaning |
| --- | --- | --- |
| `name` | required | The local name: unique in the strategy, and a path segment |
| `kind` | required | What the resource is, one of the kinds [below](#what-each-kind-does) |
| `ref` | `None` | Its stable identity, usually an `lllm://` ref |
| `entrypoint` | `None` | The `module:attribute` a package resource is loaded from; AAAX does not import it itself |
| `description` | `""` | One line for the people and agents who read the table |
| `metadata` | `{}` | Anything else: package, version, runtime, schemas, card |

Records are frozen Pydantic models, so a record does not change once it is
added, and its name stays taken in that strategy. A kind outside the list,
or a name that is not a path segment, fails validation when the record is
built.

## Local names and refs

A resource's name and its ref answer different questions:

| | Name | Ref |
| --- | --- | --- |
| Answers | Where is it in this strategy? | What is it? |
| Example | `kb.search` | `lllm://acme/knowledge-base/tactics/search` |
| Set by | You, or a package prefix | The package, or you |
| Used by | Routes, `invoke_resource`, the runner | `Resolver` bindings, hub cards, a request's `tactic_ref` |
| Means the same | Only in this strategy | Everywhere |

The name is what callers type. It must be a non-empty path segment (no
whitespace, `/`, `:`, `\`, or `%`, and not `.` or `..`), because it becomes
a URL path such as `/tactics/kb.search/run`. Dots are allowed, and package
prefixes use them.

The ref stays the same wherever the resource is mounted. A package gives
each resource it declares `lllm://ORG/PACKAGE/SECTION/NAME`, and itself
`lllm://ORG/PACKAGE` ([Refs](https://lllm.one/packages/#refs)); for your own
resources you pass `ref=`, or `add_tactic` copies the tactic's
`package_ref`. AAAX keeps refs as they are, so the table can say what each
part is while the names say how to reach it here. A tactic resource also
gives its ref to the tactic it serves, as `package_ref`, when the ref is a
tactic ref, `lllm://ORG/PACKAGE/tactics/NAME`; a package tactic whose code
sets a `package_ref` keeps that one.

## Handlers

A handler is any callable: a function, an async function, or an object
with `__call__`. AAAX looks at its signature and calls it the way it can be
called:

- **The input** is passed as the first positional argument, if the handler
  has a positional parameter besides `context` (or `*args`). A handler
  without one is called without the input.
- **The context** is passed as `context=`, if the handler declares a
  `context` parameter (or `**kwargs`).
- **The result** is returned as is; an awaitable is awaited first. Over
  HTTP, it becomes the response's `output`, encoded with FastAPI's
  `jsonable_encoder`.

```python title="handlers.py"
import asyncio

from aaax import Strategy


def ping():  # (1)!
    return "pong"


async def audit(event: dict, *, context=None):  # (2)!
    return {"event": event["kind"], "by": context["user"]}


strategy = Strategy("ops")
strategy.service("ping", handler=ping)
strategy.service("audit", handler=audit)

print(asyncio.run(strategy.invoke_resource("ping", "ignored")))
#> pong
event, context = {"kind": "refund"}, {"user": "ada"}
audited = strategy.invoke_resource("audit", event, context=context)
print(asyncio.run(audited))
#> {'event': 'refund', 'by': 'ada'}
```

1. No parameters, so the input is not passed.
2. Async, with the input and a keyword-only `context`.

What `context` holds depends on the resource:

| Resource | `context` |
| --- | --- |
| A tactic resource | An LLLM `CallContext`: the handler is wrapped with `lllm.as_tactic`, and a `Tactic` object is used as it is, or as a copy when it was mounted under another name, description, or ref |
| Any other resource | The plain dict the caller sent, or `{}` |
| Any other resource, with a `Tactic` object as handler | A `CallContext` whose `metadata` is that dict |

The runner follows the same rules as the handler of a resource that is not
a tactic.

## What each kind does

The kind decides how a resource is served:

| Kind | Without a handler | With a handler |
| --- | --- | --- |
| `tactic` | Listed, and invoking it echoes the record | An LLLM tactic, served at `/tactics/{name}/` |
| `channel` | Backed by the strategy's store, if it has one; otherwise it echoes | Serves `/channels/{name}/events` and invoke |
| `service` | Echoes | Called with the input and a dict context |
| `package`, `config`, `schema`, `snapshot`, `run`, `doc`, `example`, `asset` | Echoes | Called like a service |
| `custom` | Echoes | Called like a service |

Most kinds come from [packages](packages.md#what-each-manifest-section-becomes):
mounting one adds a resource for each thing its `lllm.toml` declares, and
binds handlers to its tactics, its channels, and services that name one of
its tactics. Use `custom` for anything else. A store-backed channel takes an
`op` (`append`, `query`, or `info`) in its input, as
[Channels](channels.md) explains.

## Resources in `info()` and over HTTP

`strategy.info()` returns a `StrategyInfo`: the strategy's `name`,
`description`, `resources`, and `metadata`. The app serves the same data:

| Route | Returns |
| --- | --- |
| `GET /strategy` | The `StrategyInfo` |
| `GET /resources` | Every record, in the order added |
| `GET /tactics`, `/channels`, `/packages` | The records of one kind |
| `POST /resources/{name}/invoke` | The resource's output, in the strategy's envelope |

`GET /tactics` lists every tactic resource, while only those with a handler
get `/tactics/{name}/` routes; any other name there is a 404 with a
`TacticNotFound`. An unknown name on the invoke route is a 404 with a
`ResourceNotFoundError`, both in LLLM's error envelope. On the command
line, `aaax inspect` prints one line per resource, its kind, name, and ref
(or its entrypoint, when it has no ref), and `--json` prints the whole
`StrategyInfo`. [Serving](serving.md) has the envelopes and status codes.
