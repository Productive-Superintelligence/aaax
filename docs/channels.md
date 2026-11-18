# Channels

A channel is a named, ordered log of events that the parts of a system
share: tickets arrive in one, results go out through another. AAAX does not
implement channels; [SSSN](https://sssn.one/) does. A strategy has one
channel store, every channel resource without a handler is the channel of
the same name in that store, and the store is served at `/network/` next to
the strategy's own routes. Tactics, HTTP clients, SSSN clients, and your
Python code all read and write the same events.

```python title="tickets.py"
from fastapi.testclient import TestClient
from sssn import LocalStore

from aaax import Strategy, create_strategy_app

desk = Strategy("desk", description="A support desk.")
desk.channel("tickets", description="Support tickets.")  # (1)!
desk.attach_store(LocalStore(".lllm/network"))  # (2)!

client = TestClient(create_strategy_app(desk))  # (3)!
ticket = {"kind": "ticket", "payload": {"text": "Checkout is down"}}
response = client.post("/channels/tickets/events", json={"input": ticket})
event = response.json()["output"]  # (4)!
print(event["channel"], event["kind"], event["source"], event["cursor"])
#> tickets ticket aaax 1

response = client.get("/channels/tickets/events")
print([event["payload"] for event in response.json()["output"]])
#> [{'text': 'Checkout is down'}]

response = client.get("/network/events", params={"channel": "tickets"})
print([event["payload"] for event in response.json()])  # (5)!
#> [{'text': 'Checkout is down'}]

print([event.payload for event in desk.store.query_events("tickets")])
#> [{'text': 'Checkout is down'}]
```

1. A channel resource without a handler is backed by the store: the store
   channel of the same name, created with this description.
2. The strategy's one store. SSSN's `LocalStore` keeps channels in a
   folder, in SQLite.
3. Building the app opens the store, creates the declared channels, and
   mounts SSSN's store API at `/network/`.
4. The `input` of an append holds the event's fields. The store fills in
   the rest: an `id`, a `timestamp`, and a `cursor`, the event's position
   in the store.
5. The same event through SSSN's store API, which any SSSN client can
   call. `strategy.store` passes store methods to the store, so the last
   line reads it from Python.

One store means one history per channel, whichever way an event came in.
Channel stores need SSSN: `pip install "aaax[channels]"`. SSSN's guides
explain [channels](https://sssn.one/channels/) and
[stores](https://sssn.one/stores/); this page covers how a strategy uses
them.

## Attach a store

`strategy.attach_store(store)`, or `strategy.store = store`, gives the
strategy its store and declares every channel resource without a handler
in it, including channels you add later.

| Store | For |
| --- | --- |
| `sssn.LocalStore(path)` | A folder on this machine; a package's default is `<package>/.lllm/network` |
| `sssn.RemoteStore(url)` | A store served elsewhere: another strategy's `/network/`, or `lllm network serve` |
| Your own object | Any backend with the four channel methods ([below](#stores-other-than-sssn)) |

`strategy.store` is then a `StrategyStore` (from `aaax.strategy`), and
`None` before. It wraps the store, opens it on first use, and passes every
store method through, so
`desk.store.append_event(...)` works; `desk.store.open()` returns the store
itself. Use a synchronous store: the channel routes and `/network/` do not
work with SSSN's `AsyncRemoteStore`.

A strategy has one store, and it is never replaced or dropped silently.
Attaching the store it already has does nothing, and a store object for
the folder of a package's store takes its place if the strategy has not
opened that folder yet. Attaching any other store, or `None` once there is
a store, raises `ValueError`.

## Package channels share the store

A package's `[channels.NAME]` tables become channel resources backed by the
strategy's store, under their local names, so two packages mounted with
different prefixes never share a channel: `billing.events` and
`shipping.events` are two channels. If the strategy has no store yet, the
first package with channels gives it a `LocalStore` at
`<package>/.lllm/network`, or at the `store=` path you pass, and later
packages share it; a `store=` that names another folder raises
`ValueError`. To pick the store yourself, attach it before mounting
packages.

Each package channel is created with its manifest's `schema`, `form`,
`description`, and `metadata`, and its resource records the store folder
in `metadata["store"]`. Mounting with `bind=False` adds channels as
records only, with nothing in the store behind them.
[Packages](packages.md#channels-share-the-strategys-store) shows a package
giving a strategy its store.

## When the store opens

Building, mounting, and inspecting a strategy never touch the store: no
folder is created and SSSN is not imported. The store opens the first time
it is used:

- when the app is built, by `create_strategy_app` or `aaax serve`;
- when a channel resource is invoked;
- when you call a store method on `strategy.store`.

Opening creates every declared channel. A channel that already exists is
left as it is, with its description and history. Threads can share the
store: it opens once, and each channel is created once. This is why
`aaax inspect` reads a package with channels on a machine without SSSN, and
why building a strategy in a test writes nothing to disk. (A `LocalStore`
you construct yourself creates its folder right away; its channels still
wait for first use.)

## Without SSSN

Without SSSN installed, everything but an SSSN store works: building,
mounting, and inspecting strategies, tactics and other resources, channels
with handlers, and stores that are not SSSN's. The first use of an SSSN
store raises an `ImportError` that says what to install, and `aaax serve`
stops with exit status 2 and the same message:

```text
ImportError: Channel stores need the sssn package: pip install sssn
```

An SSSN older than 0.2 is not used either; the message is then `aaax needs
sssn>=0.2: pip install -U 'aaax[channels]'`.

## Append and read events

| Route | Does |
| --- | --- |
| `POST /channels/{name}/events` | Appends one event; `input` holds its fields |
| `GET /channels/{name}/events` | Reads events; takes `after_cursor` (default 0), `limit` (default 100), and `kind` |
| `POST /resources/{name}/invoke` | Either one, with `"op"` in the input: `append`, `query` (the default), or `info` |

An appended event takes these fields; anything else in the `input` is
ignored:

| Field | Default |
| --- | --- |
| `payload` | `None` |
| `kind` | `"event"` |
| `source` | `"aaax"` |
| `schema`, `correlation_id` | `None` |
| `metadata` | `{}` |
| `parent_ids` | `[]`; ids of events this one follows from |

Pass the last cursor you read as `after_cursor` to get only newer events.
Cursors are positions in the whole store, so they grow across channels and
need not be consecutive within one:

```python title="read_events.py"
from fastapi.testclient import TestClient
from sssn import LocalStore

from aaax import Strategy, create_strategy_app

desk = Strategy("desk")
desk.channel("tickets", description="Support tickets.")
desk.attach_store(LocalStore(".lllm/network"))
client = TestClient(create_strategy_app(desk))
url = "/channels/tickets/events"

for kind, text in [("ticket", "Refund"), ("note", "Called back")]:
    client.post(url, json={"input": {"kind": kind, "payload": text}})
events = client.get(url).json()["output"]
last = events[-1]["cursor"]

client.post(url, json={"input": {"kind": "ticket", "payload": "Login"}})
newer = client.get(url, params={"after_cursor": last}).json()["output"]
print([event["payload"] for event in newer])
#> ['Login']
tickets = client.get(url, params={"kind": "ticket"}).json()["output"]
print([event["payload"] for event in tickets])
#> ['Refund', 'Login']

body = {"input": {"op": "info"}}
info = client.post("/resources/tickets/invoke", json=body).json()
print(info["output"]["description"])  # (1)!
#> Support tickets.

response = client.post(url, json={"input": "Refund"})  # (2)!
print(response.status_code, response.json()["detail"]["error"]["message"])
#> 400 input must be an object with the event fields
```

1. `/resources/{name}/invoke` takes the operation in the input. From
   Python, `await desk.invoke_resource("tickets", {"op": "info"})` does the
   same.
2. The input must be an object, so an event is never appended without the
   data that was sent.

The `/channels/` routes serve channel resources only: any other name is a
404, so a `GET` never runs a tactic. A negative `after_cursor` or a `limit`
below 1 is a 400. Store errors keep SSSN's status codes: 404 for a missing
channel or event (such as an unknown id in `parent_ids`), 409 for a
conflict, and 400 for an invalid event, such as a `kind` with spaces in it
([Serving](serving.md#errors)). The store API at `/network/` also serves
subscriptions, artifacts, and snapshots; SSSN's
[HTTP API](https://sssn.one/http/) lists its routes.

## Channels with handlers

A channel resource with a handler is served by the handler instead of the
store, and the channel routes still work. Use one to put a channel in
front of a feed that lives somewhere else:

```python title="handler_channel.py"
from fastapi.testclient import TestClient

from aaax import Strategy, create_strategy_app

ALERTS = ["disk 91% on db-1"]


def alerts(request: dict) -> list[str]:  # (1)!
    if request["op"] == "append":
        ALERTS.append(request["payload"])
    return ALERTS[request.get("after_cursor", 0) :]


ops = Strategy("ops").channel("alerts", handler=alerts)
client = TestClient(create_strategy_app(ops))
body = {"input": {"payload": "queue depth 10k"}}
client.post("/channels/alerts/events", json=body)
print(client.get("/channels/alerts/events").json()["output"])
#> ['disk 91% on db-1', 'queue depth 10k']
```

1. The handler gets the input the store would: `{"op": "query",
   "after_cursor": 0, "limit": 100, "kind": None}` for a `GET`, and the
   event fields plus `"op": "append"` for a `POST`.

A strategy with neither a handler nor a store for a channel keeps it as a
record: it is listed, and invoking it echoes the resource, the input, and
the context back.

## Stores other than SSSN

The store can be any object with these methods. It needs no SSSN, and it is
not served at `/network/`, which serves SSSN stores only.

| Method | Called |
| --- | --- |
| `create_channel(channel)` | For each declared channel when the store opens; `channel` is a dict with `name`, `description`, and, for package channels, `schema`, `form`, and `metadata` |
| `append_event(event)` | For `op: append`, with the event fields as a dict |
| `query_events(name, *, after_cursor, limit, kind)` | For `op: query` |
| `get_channel(name)` | For `op: info` |

For a channel that already exists, `create_channel` should return quietly
or raise an error whose `error_type` attribute is `"ChannelExistsError"`;
any other error stops the store from opening. Without a `create_channel`,
or with an async one, AAAX creates no channels, and you create them
yourself.

## Run a tactic over a channel

SSSN's [`TacticProcessor`](https://sssn.one/processing/) reads a channel
through a named subscription, runs a tactic on each event's payload, and
appends the result to another channel. Give it a mounted tactic and the
strategy's store:

```python title="processor.py"
from lllm import Tactic
from sssn import LocalStore, TacticProcessor

from aaax import Strategy


class Triage(Tactic):
    """Route a support ticket to a queue."""

    name = "triage"

    def call(self, ticket: dict) -> dict:
        urgent = "down" in ticket["text"].lower()
        return {"queue": "oncall" if urgent else "support"}


desk = Strategy("desk").add_tactic(Triage())
desk.channel("tickets").channel("routed")  # (1)!
desk.attach_store(LocalStore(".lllm/network"))
desk.store.append_event(
    {"channel": "tickets", "payload": {"text": "Checkout is down"}}
)

processor = TacticProcessor(
    desk.tactics()["triage"], desk.store, source="tickets", sink="routed"
)
for event in processor.process():  # (2)!
    print(event.channel, event.kind, event.payload)
    #> routed result {'queue': 'oncall'}
print(processor.process())  # (3)!
#> []
```

1. Declare the sink as a channel too, so it is created when the store
   opens, here at the first `append_event`.
2. Each result is appended to `routed`, with `parent_ids` pointing at the
   ticket it came from.
3. The subscription remembers where it stopped, so the second call finds
   nothing new.

AAAX does not run processors for you: call `process()` from the strategy's
runner, a service handler, or a worker of your own. Any tactic works here,
including one whose agents call a model ([Tactics](https://lllm.one/tactics/)).
The [support desk](examples/support-desk.md) example runs a processor from
its runner, so `POST /run` triages every new ticket.
