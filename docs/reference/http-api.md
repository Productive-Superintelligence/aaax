# HTTP API

AAAX exposes the shell surface as JSON endpoints through FastAPI.

## Envelopes

Requests use:

```json
{
  "input": {},
  "context": {}
}
```

Responses use:

```json
{
  "output": {},
  "strategy": "strategy-name",
  "metadata": {}
}
```

## Endpoints

`GET /health`
: Returns `{"ok": true, "strategy": "<name>"}`.

`GET /strategy`
: Returns `StrategyInfo`.

`GET /resources`
: Returns all resources.

`GET /packages`
: Returns resources with kind `package`.

`GET /tactics`
: Returns resources with kind `tactic`.

`GET /channels`
: Returns resources with kind `channel`.

`POST /run`
: Calls the shell runner.

`POST /resources/{name}/invoke`
: Invokes any resource by local name.

`POST /tactics/{name}/run`
: Invokes a tactic by local name.

`POST /channels/{name}/events`
: Appends an event to a channel.

`GET /channels/{name}/events`
: Queries channel events.

## Errors

Missing resources return `404`.

Invalid channel query parameters or unsupported channel operations return `400`.

Unhandled handler exceptions propagate through FastAPI's normal exception path,
which is useful during local development and should be handled by deployment
middleware in production.
