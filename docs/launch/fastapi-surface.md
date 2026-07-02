# FastAPI Surface

`create_strategy_app(strategy)` exposes the strategy as a FastAPI application.
Responses use a simple envelope:

```json
{
  "output": {},
  "strategy": "analysis-workbench",
  "metadata": {}
}
```

## Health And Metadata

```text
GET /health
GET /strategy
GET /resources
GET /packages
GET /tactics
GET /channels
```

These endpoints are read-only and useful for smoke tests, UI surfaces, and
agent handoff.

## Strategy Run

```text
POST /run
```

Request:

```json
{
  "input": {"task": "summarize"},
  "context": {"request": "demo"}
}
```

`/run` calls the strategy runner. If no runner is configured, it returns the
default strategy pack.

## Tactic Run

```text
POST /tactics/{name}/run
```

This invokes the resource named `{name}` and marks the response metadata endpoint
as `tactic`.

## Generic Resource Invocation

```text
POST /resources/{name}/invoke
```

This is the universal escape hatch. It can invoke tactics, services, channels,
or custom resources by local strategy name.

## Channel Events

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

Query parameters:

- `after_cursor`: non-negative integer, default `0`.
- `limit`: positive integer, default `100`.
- `kind`: optional event kind filter.

AAAX converts channel validation errors into `400` responses and missing
resources into `404` responses.
