# FastAPI Shell

`create_strategy_app(strategy)` exposes the shell as a FastAPI application.
It is assembled from LLLM's services: every tactic resource is mounted as a
full LLLM tactic service, and a strategy with a channel store mounts SSSN's
store API. The shell adds its own routes on top. Requests and responses use
Pydantic models, so the same shell can be called by an app, a local script, an
agent, or another system in the loop.

Building the app serves the strategy: it imports package code and opens the
channel store, which creates the declared channels. The app keeps the strategy
at `app.state.aaax_strategy` and reports AAAX's version in its OpenAPI
document.

## Health And Metadata

```text
GET /health
GET /strategy
GET /resources
GET /packages
GET /tactics
GET /channels
```

These endpoints are read-only and useful for smoke tests, UI surfaces, and agent
handoff. They are the shell's `ls` and `env`. `/strategy` returns the
`StrategyInfo`: name, description, resources, and metadata.

## Shell Routes

The shell routes, `/run`, `/resources/{name}/invoke`, and
`/channels/{name}/events`, use a simple envelope. Requests:

```json
{
  "input": {"task": "summarize"},
  "context": {"request": "demo"}
}
```

Responses:

```json
{
  "output": {},
  "strategy": "analysis-shell",
  "metadata": {}
}
```

### Shell Run

```text
POST /run
```

`/run` calls the shell runner with the input and, as a plain dict, the
context. If no runner is configured, it returns the default shell pack: the
strategy name, the input, and the mounted resources.

### Generic Resource Invocation

```text
POST /resources/{name}/invoke
```

This is the universal escape hatch. It can invoke tactics, services, channels,
or custom resources by local shell name, and marks the response metadata
endpoint as `resource`. A tactic resource runs exactly as on its tactic
service, with the `context` as an LLLM `CallContext`; other handlers get the
context as a plain dict; a channel backed by the store takes an `op`
(`append`, `query`, or `info`).

### Channel Events

```text
POST /channels/{name}/events
GET /channels/{name}/events
```

Append request:

```json
{
  "input": {
    "kind": "record",
    "source": "client",
    "payload": {"text": "hello"},
    "metadata": {"demo": true}
  }
}
```

The `input` must be an object of event fields: `payload`, `kind` (default
`event`), `source` (default `aaax`), `schema`, `metadata`, `correlation_id`,
and `parent_ids`.

Query parameters:

- `after_cursor`: non-negative integer, default `0`.
- `limit`: positive integer, default `100`.
- `kind`: optional event kind filter.

These routes serve channel resources only; naming another resource is a `404`.

## Tactic Services

```text
POST /tactics/{name}/run
POST /tactics/{name}/stream
GET  /tactics/{name}/info
```

Each tactic resource with a handler is mounted at `/tactics/{name}/` with
LLLM's `create_tactic_app`, so it is a standard
[LLLM tactic service](https://lllm.one/protocol/services/): `run`, `stream`
(server-sent events, for tactics that stream), `info` (description, input and
output schemas, examples, and refs), and the tactic's custom endpoints. It
uses LLLM's service envelopes rather than the shell's:

```json
{"input": {"text": "hello"}, "context": {"metadata": {"request": "demo"}}}
```

```json
{"output": {"text": "HELLO"}, "request_id": "...", "tactic": "shout"}
```

The `context` has the shape of an LLLM `CallContext` (`request_id`,
`trace_id`, `caller`, `tags`, `metadata`, and the other fields); keys that are
not `CallContext` fields are dropped. Prefixed names keep their dots, as in
`/tactics/analyst.echo/run`. Because these are standard services, an LLLM
`RemoteTactic` or `lllm.Resolver` can call them by URL or by ref.

## Store API

```text
GET  /network/channels
GET  /network/events?channel=...
POST /network/events
```

A strategy with a channel store mounts SSSN's store API at `/network/`:
channels, events, subscriptions, artifacts, and snapshots, as
[`sssn.create_app`](https://sssn.one/reference/http-api/) serves them. It
works on the same store as the channel routes, and channels declared after the
app is built are created there too.

## Errors

The shell routes report errors in LLLM's services error envelope, as the
tactic services do:

```json
{"detail": {"error": {"type": "ResourceNotFoundError", "message": "Strategy channel not found: shout", "tactic": null, "endpoint": "channel", "request_id": null, "metadata": {"resource": "shout"}}}}
```

| Status | When |
| --- | --- |
| 400 | A malformed request, an appended event whose `input` is not an object, or a `ValueError`, `SchemaError`, or `TacticUnsupportedError` from the runner or a handler. |
| 404 | The resource named in the URL does not exist, or a `/channels/` route names a resource that is not a channel. |
| Its own | An `HTTPException` from the runner or a handler keeps its status and its plain `detail`, without the envelope; a store error keeps the store API's code (404 not found, 409 conflict, 400 otherwise). |
| 500 | Anything else the runner or a handler raises, including a resource lookup that fails inside it. |

A tactic resource fails with the codes of `POST /tactics/{name}/run` instead,
on both routes: 400 for `SchemaError` and `TacticUnsupportedError`, 500 for
anything else, a `ValueError`, `HTTPException`, or store error included. The
store API at `/network/` uses the same envelope with only `type` and
`message`.
