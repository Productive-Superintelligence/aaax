# HTTP API

`create_strategy_app(strategy)` serves a strategy as JSON endpoints through
FastAPI. The app is built from LLLM's services: each tactic is a mounted
LLLM tactic service, and a strategy with an SSSN channel store mounts SSSN's
store API. [Serving](../serving.md) and [Channels](../channels.md) show
these routes in use.

## Envelopes

The strategy's routes (`/run`, `/resources/...`, `/channels/...`) take a
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

These routes read a body by the rules of LLLM's tactic routes. An object
whose keys are `input` or `task`, and optionally `context`, is the
envelope: its `input` is the input, or its `task` when `input` is missing
or `null`. Any other body, such as an object with other keys, a string, or
a number, is the input itself; a body that is not JSON is its text, and an
empty body is the input `null`. The body is decoded strictly as UTF-8;
one that is not UTF-8 is the input as bytes when its content type is
`application/octet-stream`, as on LLLM's tactic routes, and a 400
`SchemaError` otherwise. `metadata` names the resource and the route
(`resource` or `channel`), and is empty for `/run`.

The tactic services under `/tactics/{name}/` use LLLM's service envelopes:
requests are `{"input": ..., "context": {...}}` with a `CallContext`-shaped
context, and responses are `{"output": ..., "request_id": ..., "tactic": ...}`.
The `tactic` field of replies and of the tactic's errors is `{name}`, the
resource's local name, also when the resource was renamed or prefixed. The
exception is a `{name}` with `;`, which LLLM's tactic names cannot hold:
that tactic answers under its own name. The 403 that refuses a cross-site
request ([Errors](#errors)) comes before any tactic and carries only `type`
and `message`.

## Endpoints

| Route | Returns or does |
| --- | --- |
| `GET /health` | `{"ok": true, "strategy": "<name>"}` |
| `GET /strategy` | The `StrategyInfo` |
| `GET /resources` | All resources |
| `GET /packages` | Resources with kind `package` |
| `GET /tactics` | Resources with kind `tactic` |
| `GET /channels` | Resources with kind `channel` |
| `POST /run` | Calls the strategy's runner |
| `POST /resources/{name}/invoke` | Invokes any resource by local name: runs its tactic or handler, or uses its store channel with an `op` of `append`, `query`, or `info` |
| `POST /channels/{name}/events` | Appends an event to a channel resource. The `input` is an object of event fields: `payload`, `kind` (default `event`), `source` (default `aaax`), `schema`, `metadata`, `correlation_id`, `parent_ids` |
| `GET /channels/{name}/events` | Queries a channel resource: `?after_cursor=0&limit=100&kind=...` |
| `POST /tactics/{name}/run`, `POST /tactics/{name}/stream`, `GET /tactics/{name}/info` | The mounted LLLM tactic service, with any custom tactic endpoints under the same prefix, and its own `/docs` and `/openapi.json` |
| `/network/...` | SSSN's store API (channels, events, subscriptions, artifacts, snapshots), when the strategy's channel store is an SSSN store |
| `GET /docs`, `GET /openapi.json` | FastAPI's interactive docs and OpenAPI document for the routes above, apart from the mounted apps |

A `{name}` under `/tactics/` that no tactic is mounted under is a 404 in
the error envelope below, with the type `TacticNotFound`, the message
`Tactic not found: {name}`, and `tactic` set to `{name}`, as in LLLM's own
multi-tactic services. `tactic` is `null` when LLLM's errors cannot carry
the name: one with `;`, `:`, `%`, or `\`, only spaces, or `.` or `..`.

## Errors

The strategy's routes report errors in LLLM's services error envelope:

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
| 400 | A malformed request, an appended event whose `input` is not an object, or a `ValueError`, `SchemaError`, or `TacticUnsupportedError` from the runner or a handler, except an `OutputSchemaError`. |
| 403 | A cross-site request (by `Sec-Fetch-Site: cross-site` or `same-site`, or, without it, an `Origin` that is `null` or for another host and port) that is a POST whose body is not JSON, on any route, or a GET or HEAD to a tactic's custom endpoint under `/tactics/{name}/` (`CrossSiteRequestError`). `create_strategy_app(strategy, allow_cross_site_requests=True)` serves them. |
| 404 | The resource named in the URL does not exist, or a `/channels/` route names a resource that is not a channel. |
| Its own | An `HTTPException` from the runner or a handler keeps its status and plain `detail`; a channel store error keeps the store API's code (404 not found, 409 conflict, 400 otherwise). |
| 500 | Anything else the runner or a handler raises, including an `OutputSchemaError`, which lllm-core 0.4.1 and later raise for a result that fails its output schema; and a reply that cannot be encoded, such as bytes that are not UTF-8 or a string with a lone surrogate. |

A body that does not validate is a 400 `SchemaError` with `endpoint` set to
`null`. A tactic resource gets the status codes of `POST /tactics/{name}/run`
on both of its routes: 400 for `SchemaError` (other than an
`OutputSchemaError`, a 500) and `TacticUnsupportedError`, 500 for anything
else. SSSN's routes under `/network/` use the same envelope with only
`type` and `message`.
