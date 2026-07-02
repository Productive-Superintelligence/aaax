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
- a local SSSN channel in the bound store;
- an append/query HTTP endpoint.

Append:

```bash
curl -X POST http://127.0.0.1:8400/channels/events/events \
  -H 'content-type: application/json' \
  -d '{"input": {"kind": "record", "payload": {"id": "a1"}}}'
```

Query:

```bash
curl 'http://127.0.0.1:8400/channels/events/events?after_cursor=0&limit=100'
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
- `query`

The HTTP convenience endpoints set `op` for you.

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
