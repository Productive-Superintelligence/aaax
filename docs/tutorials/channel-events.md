# Channel Events

Package channels become endpoints backed by the strategy's SSSN store when
packages are mounted. Channel stores come from SSSN, so install the channels
extra:

```bash
python -m pip install "aaax[channels]"
```

## 1. Add A Channel

```toml title="lllm.toml"
[channels.events]
form = "log"
description = "Application event stream."
```

AAAX creates the channel in the package's `.lllm/network` store by default,
the first time the strategy is served or a channel is used. You can pass a
custom store path when mounting:

```python
from aaax import Strategy


shell = Strategy("events-shell")
shell.use_package("packages/source-pack", store=".lllm/source-store")
```

A strategy has one store, so packages mounted later share it.

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

The response output is an SSSN event with an id, cursor, timestamp, channel,
source, kind, payload, and metadata. Without `kind` the event's kind is
`event`, and without `source` its source is `aaax`.

## 3. Query Events

```bash
curl 'http://127.0.0.1:8400/channels/events/events?after_cursor=0&limit=10'
```

Filter by kind:

```bash
curl 'http://127.0.0.1:8400/channels/events/events?kind=record&limit=10'
```

The same events are in SSSN's store API, served at `/network/`:

```bash
curl 'http://127.0.0.1:8400/network/events?channel=events'
```

## 4. Use The Shell Escape Hatch

```bash
curl -X POST http://127.0.0.1:8400/resources/events/invoke \
  -H 'content-type: application/json' \
  -d '{"input": {"op": "query", "limit": 10}}'
```

The generic path is the shell escape hatch for clients that do not want
resource-kind-specific routes.

To run a tactic over every new event, point an SSSN `TacticProcessor` at the
strategy's store; see [Use with LLLM](../guides/lllm.md#channels-through-sssn).
