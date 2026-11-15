# HTTP API

AAAX exposes the shell surface as JSON endpoints through FastAPI. The app is
built from LLLM's services: each tactic is a mounted LLLM tactic service, and
a strategy with an SSSN channel store mounts SSSN's store API.

## Envelopes

The shell routes (`/run`, `/resources/...`, `/channels/...`) take a
`StrategyRunRequest`:

```json
{
  "input": {},
  "context": {}
}
```

and return a `StrategyRunResponse`:

```json
{
  "output": {},
  "strategy": "strategy-name",
  "metadata": {}
}
```

The tactic services under `/tactics/{name}/` use LLLM's service envelopes:
requests are `{"input": ..., "context": {...}}` with a `CallContext`-shaped
context, and responses are `{"output": ..., "request_id": ..., "tactic": ...}`.

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
: Invokes any resource by local name: runs its tactic or handler, or uses its
  store channel with an `op` of `append`, `query`, or `info`.

`POST /channels/{name}/events`
: Appends an event to a channel resource. The `input` is an object of event
  fields: `payload`, `kind` (default `event`), `source` (default `aaax`),
  `schema`, `metadata`, `correlation_id`, `parent_ids`.

`GET /channels/{name}/events`
: Queries a channel resource: `?after_cursor=0&limit=100&kind=...`.

`POST /tactics/{name}/run`, `POST /tactics/{name}/stream`, `GET /tactics/{name}/info`
: The mounted LLLM tactic service, with any custom tactic endpoints.

`/network/...`
: SSSN's store API (channels, events, subscriptions, artifacts, snapshots),
  when the strategy's channel store is an SSSN store.

## Errors

The shell routes report errors in LLLM's services error envelope:

```json
{
  "detail": {
    "error": {
      "type": "ResourceNotFoundError",
      "message": "Strategy resource not found: nope",
      "tactic": null,
      "endpoint": "resource",
      "request_id": null,
      "metadata": {"resource": "nope"}
    }
  }
}
```

| Status | When |
| --- | --- |
| 400 | A malformed request, an appended event whose `input` is not an object, or a `ValueError`, `SchemaError`, or `TacticUnsupportedError` from the runner or a handler. |
| 404 | The resource named in the URL does not exist, or a `/channels/` route names a resource that is not a channel. |
| Its own | An `HTTPException` from the runner or a handler keeps its status and plain `detail`; a channel store error keeps the store API's code (404 not found, 409 conflict, 400 otherwise). |
| 500 | Anything else the runner or a handler raises. |

A tactic resource gets the status codes of `POST /tactics/{name}/run` on both
of its routes: 400 for `SchemaError` and `TacticUnsupportedError`, 500 for
anything else.
