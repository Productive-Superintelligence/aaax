# Channel Events

Package channels become SSSN-backed local endpoints when packages are mounted.

## 1. Add A Channel

```toml title="psi.toml"
[channels.events]
form = "log"
description = "Application event stream."
```

AAAX creates the channel in the package `.sssn` store by default. You can pass a
custom store path when mounting:

```python
shell.use_package("packages/source-pack", store=".aaax/source-store")
```

## 2. Append An Event

```bash
curl -X POST http://127.0.0.1:8400/channels/events/events \
  -H 'content-type: application/json' \
  -d '{
    "input": {
      "kind": "record",
      "source": "tutorial",
      "payload": {"text": "first"}
    }
  }'
```

The response output is an SSSN event envelope with an id, cursor, timestamp,
channel, kind, payload, and metadata.

## 3. Query Events

```bash
curl 'http://127.0.0.1:8400/channels/events/events?after_cursor=0&limit=10'
```

Filter by kind:

```bash
curl 'http://127.0.0.1:8400/channels/events/events?kind=record&limit=10'
```

## 4. Use The Shell Escape Hatch

```bash
curl -X POST http://127.0.0.1:8400/resources/events/invoke \
  -H 'content-type: application/json' \
  -d '{"input": {"op": "query", "limit": 10}}'
```

The generic path is the shell escape hatch for clients that do not want
resource-kind-specific routes.
