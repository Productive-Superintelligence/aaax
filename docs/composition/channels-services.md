# Channels And Services

AAAX makes channels and services available through the same shell boundary as
tactics. This lets a mounted package expose both "do work" and "share state"
operations without inventing a separate API surface.

## Channels

A package channel:

```toml
[channels.events]
form = "log"
description = "Application event stream."
```

becomes:

- a `channel` resource in `/resources`;
- an item in `/channels`;
- a channel of the same name in the strategy's SSSN store;
- an append/query HTTP endpoint;
- events in SSSN's store API at `/network/`.

Channel stores come from [SSSN](https://sssn.one/): install `aaax[channels]`.

Append:

```bash
curl -X POST http://127.0.0.1:8400/channels/events/events \
  -H 'content-type: application/json' \
  -d '{"input": {"kind": "record", "payload": {"id": "a1"}}}'
```

The `input` is an object of event fields: `payload`, `kind` (default `event`),
`source` (default `aaax`), `schema`, `metadata`, `correlation_id`, and
`parent_ids`. An `input` that is not an object is a `400`. The response output
is the SSSN event, with its `id`, `cursor`, and `timestamp`.

Query:

```bash
curl 'http://127.0.0.1:8400/channels/events/events?after_cursor=0&limit=100'
```

The same events are in the store API:

```bash
curl 'http://127.0.0.1:8400/network/events?channel=events'
```

## Channel Operations

The generic resource invocation path also supports channel operations:

```bash
curl -X POST http://127.0.0.1:8400/resources/events/invoke \
  -H 'content-type: application/json' \
  -d '{"input": {"op": "info"}}'
```

Supported operations are:

- `info`
- `append`
- `query` (the default)

The HTTP convenience endpoints set `op` for you. They serve channel resources
only: naming a tactic or any other resource on a `/channels/` route is a
`404`, so a `GET` never runs a tactic.

## The Strategy Store

A strategy has one channel store. Every channel resource without a handler,
whether a package declared it or you added it with `strategy.channel()`, is
backed by the store channel of the same name, created the first time the store
is used. Packages give a strategy without a store one at
`<package>/.lllm/network` (see [LLLM Packages](packages.md#channel-stores)), or
you attach your own before mounting them:

```python
from sssn import LocalStore

from aaax import Strategy


shell = Strategy("ops")
shell.attach_store(LocalStore(".lllm/network"))
shell.channel("log", description="Everything the shell did.")
shell.use_package("packages/source", prefix="source")
```

`strategy.store` wraps the store and forwards store methods to it, so a runner
can write with `strategy.store.append_event(...)`, and an SSSN
`TacticProcessor` over `strategy.store` connects a mounted tactic to a channel
(see [Use with LLLM](../guides/lllm.md#channels-through-sssn)). Use a
synchronous store, a `LocalStore` or a `RemoteStore`: the channel routes and
`/network/` do not work with an `AsyncRemoteStore`. Attaching a different store
to a strategy that has one raises `ValueError` instead of replacing it.

A channel resource with its own handler is served by that handler instead,
and without a store a channel resource is metadata like any other.

## Services

A service can point at a single tactic:

```toml
[services.api]
tactic = "echo"
transport = "fastapi"
description = "HTTP-facing echo service."
```

AAAX imports it as a `service` resource. If the tactic is locally bound, the
service resource uses the same handler:

```bash
curl -X POST http://127.0.0.1:8400/resources/api/invoke \
  -H 'content-type: application/json' \
  -d '{"input": {"text": "hello"}}'
```

This is intentionally conservative. AAAX does not launch arbitrary service
processes from a manifest. It exposes the shell-facing resource boundary and
lets deployment or agent tooling decide how far to go.
