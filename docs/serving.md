# Serving

`create_strategy_app(strategy)` turns a strategy into one FastAPI app. The
app adds no new protocol where one already exists: every tactic resource is
mounted as LLLM's own tactic service at `/tactics/<name>/`, an SSSN channel
store is mounted as SSSN's store API at `/network/`, and AAAX adds routes
only for what neither has, such as the resource table and the strategy's
`/run`. A client written for an LLLM tactic service or an SSSN store works
against a strategy unchanged.

```python title="desk.py"
from fastapi.testclient import TestClient
from lllm import Tactic

from aaax import Strategy, create_strategy_app


class Triage(Tactic):
    """Route a support ticket to a queue."""

    name = "triage"
    input_type = str

    def call(self, text: str) -> str:
        return "oncall" if "outage" in text.lower() else "support"


def summarize(text: str) -> str:
    """Keep the first sentence of a ticket."""
    return text.split(". ")[0] + "."


desk = Strategy("desk", description="Route and summarize tickets.")
desk.add_tactic(Triage())  # (1)!
desk.tactic("summarize", handler=summarize)


@desk.runner  # (2)!
async def handle(text: str) -> dict:
    tactics = desk.tactics()
    return {
        "queue": await tactics["triage"].arun(text),
        "summary": await tactics["summarize"].arun(text),
    }


client = TestClient(create_strategy_app(desk))  # (3)!
ticket = "Total outage in eu-west. It started at 9:00."
reply = client.post("/tactics/triage/run", json={"input": ticket}).json()
print(reply["output"], reply["tactic"])  # (4)!
#> oncall triage
print(client.post("/run", json={"input": ticket}).json())  # (5)!
"""
{
    'output': {'queue': 'oncall', 'summary': 'Total outage in eu-west.'},
    'strategy': 'desk',
    'metadata': {},
}
"""
```

1. Two tactic resources: an LLLM tactic, and a plain function that AAAX
   wraps with `lllm.as_tactic`. Both are served at `/tactics/<name>/`.
   Agent-backed tactics are served the same way
   ([Tactics](https://lllm.one/tactics/)).
2. The runner is the strategy's own operation, served at `POST /run`.
3. Building the app mounts the tactics and opens the channel store, if
   there is one. `TestClient` calls the app in this process.
4. `/tactics/triage/run` is LLLM's tactic service, with its envelope:
   `output`, `request_id`, and `tactic`.
5. The strategy's routes use AAAX's envelope: `output`, `strategy`, and
   `metadata`.

```mermaid
flowchart TD
    A[strategy app] --> T["/tactics/NAME/<br/>LLLM tactic service"]
    A --> N["/network/<br/>SSSN store API"]
    A --> S["/strategy, /resources,<br/>/channels, /run"]
```

## Routes

| Route | Does |
| --- | --- |
| `GET /health` | `{"ok": true, "strategy": NAME}` |
| `GET /strategy` | The `StrategyInfo`: name, description, resources, metadata |
| `GET /resources`, `/tactics`, `/channels`, `/packages` | Resource records: all of them, or those of one kind |
| `POST /run` | Calls the strategy's runner |
| `POST /resources/{name}/invoke` | Calls one resource by name |
| `GET`, `POST /channels/{name}/events` | Reads or appends a channel's events ([Channels](channels.md)) |
| `POST /tactics/{name}/run`, `/stream`; `GET /tactics/{name}/info` | LLLM's tactic service, one per tactic resource |
| `/network/...` | SSSN's store API, when the store is an SSSN store |
| `GET /docs`, `/openapi.json` | FastAPI's docs for the strategy's own routes |

Each mounted app keeps its own docs: `/tactics/<name>/docs` and
`/tactics/<name>/openapi.json` carry a tactic's schemas, and `/network/docs`
documents the store API. `GET /tactics` lists the tactic resource records,
including tactics declared without a handler, which have no service. Names
keep their dots, as in `/tactics/support.triage/run`. A name under
`/tactics/` that no tactic is mounted under, such as a tactic declared
without a handler, is a 404 with the type `TacticNotFound` in the error
envelope, as in LLLM's own multi-tactic services.

## Tactic routes

`/tactics/<name>/` is `create_tactic_app(tactic)` from LLLM, mounted as
is, so everything in LLLM's [Serving](https://lllm.one/serving/) guide
holds there. `run` and `stream` (server-sent events, for a tactic that
streams) take a `POST`, `info` returns the input and output schemas, and
the tactic's [custom endpoints](https://lllm.one/serving/#custom-endpoints)
sit under the same prefix: an endpoint at `/explain` is served at
`/tactics/<name>/explain`.

`strategy.tactics()` decides what is mounted. A `Tactic` is served as is,
a package tactic is imported when the app is built, and a plain function
is wrapped with `lllm.as_tactic`, so its annotations become the schemas.
A tactic mounted under a name, description, or ref other than its own,
such as one that `add_tactic(name=...)` or a package prefix renamed, is
served as a copy that has them; the tactic you mounted, or the package
code imported, keeps its own. Each tactic is served under its local name,
so the `tactic` field of replies and errors names the route, as in
`/tactics/support.triage/run`. The exception is a local name with `;`,
which LLLM's tactic names cannot hold: that tactic answers under its own
name.

Requests use LLLM's envelope, `{"input": ..., "context": {...}}`, and the
`context` becomes the `CallContext` a tactic receives. A tactic declares a
`context` parameter to read it:

```python title="context.py"
from fastapi.testclient import TestClient
from lllm import Tactic

from aaax import Strategy, create_strategy_app


class Lookup(Tactic):
    """Look up an order."""

    name = "lookup"
    input_type = str

    def call(self, order_id: str, *, context=None) -> dict:
        return {
            "order": order_id,
            "trace": context.trace_id,
            "user": context.metadata["user"],
        }


def audit(entry: dict, context=None) -> dict:  # (1)!
    return {"saw": sorted(context)}


shop = Strategy("shop").add_tactic(Lookup())
shop.service("audit", handler=audit)
client = TestClient(create_strategy_app(shop))
context = {
    "request_id": "req-7",
    "trace_id": "trace-42",
    "metadata": {"user": "ada"},
    "shard": 3,  # (2)!
}

body = {"input": "A-1001", "context": context}
reply = client.post("/tactics/lookup/run", json=body).json()
print(reply["output"], reply["request_id"])
#> {'order': 'A-1001', 'trace': 'trace-42', 'user': 'ada'} req-7
reply = client.post("/resources/lookup/invoke", json=body).json()
print(reply["output"])  # (3)!
#> {'order': 'A-1001', 'trace': 'trace-42', 'user': 'ada'}

body = {"input": {"note": "refund"}, "context": context}
print(client.post("/resources/audit/invoke", json=body).json()["output"])
#> {'saw': ['metadata', 'request_id', 'shard', 'trace_id']}
```

1. A handler that is not a tactic, here a service, gets the `context`
   object as a plain dict, every key included.
2. `CallContext` has no `shard` field, so a tactic never sees it. Put your
   own values in `metadata`.
3. A tactic resource runs the same way through the strategy's
   `/resources/{name}/invoke`, with the same `CallContext`.

| `CallContext` field | Meaning |
| --- | --- |
| `request_id` | The call's id; generated when missing, and returned as the reply's `request_id` |
| `trace_id`, `span_id`, `caller` | Tracing ids and who is calling |
| `tags` | String labels, such as `{"env": "prod"}` |
| `metadata` | Your own values: any JSON object |
| `tactic_ref` | Defaults to the tactic's `package_ref`: the ref it was mounted with, or a package tactic's manifest ref |
| `package_ref`, `service_ref` | Refs the caller passes along |
| `endpoint` | Set by the service: `run`, `stream`, or a custom endpoint's name |

Unknown keys are ignored, and a `context` that is not an object, or has
`metadata` or `tags` that are not objects, is a 400 `SchemaError`. As in
any LLLM service, a body that is not an envelope is taken as the input
itself, and `task` works in place of `input`; the strategy's own routes,
below, read a body the same way.

## The strategy's routes

`/run`, `/resources/{name}/invoke`, and `/channels/{name}/events` take the
same envelope, `{"input": ..., "context": {...}}` (a `StrategyRunRequest`),
and answer with a `StrategyRunResponse`:

```json
{
  "output": {"queue": "oncall"},
  "strategy": "desk",
  "metadata": {"resource": "triage", "endpoint": "resource"}
}
```

`metadata` names the resource and the route (`resource` or `channel`), and
is empty for `/run`. A body is read as on the tactic routes: an object with
`input` or `task`, and at most `context` besides, is an envelope, and any
other body is the input itself, so `{"text": "Hi"}` runs with that object
as the input, and an empty body with `None`. A body whose first value is
an array or object nested more than 500 levels deep is a 400, since code
that walks it recursively can crash the server; with lllm-core 0.4.0, the
routes under `/tactics/` lack this limit, and 0.4.1 adds it. A body that
is not UTF-8 is the input as bytes when its content type is
`application/octet-stream`, and a 400 otherwise, as on the tactic routes
from lllm-core 0.4.1. With 0.4.0, those routes parse JSON in any UTF
encoding (UTF-16 and UTF-32 included, and UTF-8-encoded surrogates pass
through) and take any other body that is not UTF-8 as bytes.
`/resources/{name}/invoke` does what the resource calls for:

| Resource | `/resources/{name}/invoke` |
| --- | --- |
| A tactic with a handler | Runs it as `/tactics/{name}/run` does, with a `CallContext` |
| A channel backed by the store | A store operation, chosen by `op` in the input ([Channels](channels.md#append-and-read-events)) |
| Anything else with a handler | Calls the handler with the input, and with `context` as a dict if it takes one |
| Anything without a handler | Echoes the resource record, the input, and the context |

The runner follows the handler rule, and a strategy without a runner
answers `/run` with its name, the input, and its resources. How handlers
are called, sync or async, with or without the input, is in
[Resources](resources.md).

## Errors

The strategy's routes report failures in the error envelope that LLLM's
tactic services use, under FastAPI's `detail` key:

```python title="errors.py"
from fastapi import HTTPException
from fastapi.testclient import TestClient

from aaax import Strategy, create_strategy_app


def refund(order: dict) -> dict:
    if order["amount"] > 100:
        raise ValueError("refunds over 100 need a manager")
    if order["amount"] <= 0:
        raise HTTPException(status_code=403, detail="Not allowed.")
    return {"refunded": order["amount"]}


shop = Strategy("shop").service("refund", handler=refund)
client = TestClient(create_strategy_app(shop))

response = client.post("/resources/nope/invoke", json={"input": 1})
error = response.json()["detail"]["error"]
print(response.status_code, error["type"], error["metadata"])
#> 404 ResourceNotFoundError {'resource': 'nope'}
print(sorted(error))
#> ['endpoint', 'message', 'metadata', 'request_id', 'tactic', 'type']

body = {"input": {"amount": 500}}
response = client.post("/resources/refund/invoke", json=body)
error = response.json()["detail"]["error"]
print(response.status_code, error["type"], error["message"])
#> 400 ValueError refunds over 100 need a manager

body = {"input": {"amount": 0}}
response = client.post("/resources/refund/invoke", json=body)
print(response.status_code, response.json())  # (1)!
#> 403 {'detail': 'Not allowed.'}
```

1. A handler that raises an `HTTPException` decides the response itself:
   its status and its `detail`, without the envelope.

| Status | When, on the strategy's routes |
| --- | --- |
| 400 | A body that does not validate (`SchemaError`), an appended event whose `input` is not an object, or a `ValueError`, `SchemaError`, or `TacticUnsupportedError` from the runner or a handler, except an `OutputSchemaError` |
| 403 | A cross-site POST whose body is not JSON, or a cross-site GET or HEAD to a tactic's custom endpoint (`CrossSiteRequestError`, [below](#your-own-server)) |
| 404 | The URL names no resource, or a `/channels/` route names one that is not a channel (`ResourceNotFoundError`) |
| 404, 409, 400 | A channel store error, with SSSN's codes: not found, conflict, anything else |
| Its own | An `HTTPException` from the runner or a handler |
| 500 | Anything else the runner or a handler raises, an `OutputSchemaError` included, or a reply that cannot be encoded, such as bytes that are not UTF-8 |

`OutputSchemaError` is the `SchemaError` that lllm-core 0.4.1 and later
raise for a result that fails its output schema: the code's fault, not the
caller's, so it is a 500. A tactic fails the same way on both of its
routes, with LLLM's codes: 400 for `SchemaError` (but 500 for an
`OutputSchemaError`) and `TacticUnsupportedError`, 500 for anything else,
`ValueError` and `HTTPException` included. On `/tactics/...` the error
carries the tactic's name and the `request_id`; on the strategy's routes
`metadata.resource` names the resource. SSSN's routes under `/network/`
use the same envelope with only `type` and `message`, and so does the 403
that refuses a cross-site request, on any route.

## Serve from the command line

`aaax serve` loads a strategy and runs its app with Uvicorn; `aaax inspect`
prints what would be served, without importing package code or opening the
store. A strategy file defines `build_strategy()` or a module-level
`strategy`:

```python title="strategy.py"
from aaax import Strategy


def triage(text: str) -> str:
    """Route a support ticket to a queue."""
    return "oncall" if "outage" in text.lower() else "support"


def build_strategy() -> Strategy:
    desk = Strategy("desk", description="Route support tickets.")
    ref = "lllm://acme/desk/tactics/triage"
    desk.tactic("triage", handler=triage, ref=ref)
    desk.channel("tickets", description="Support tickets.")
    return desk
```

```text
$ aaax inspect strategy.py
desk: Route support tickets.
tactic triage lllm://acme/desk/tactics/triage
channel tickets
$ aaax serve strategy.py
INFO:     Uvicorn running on http://127.0.0.1:8400 (Press CTRL+C to quit)
```

Each line of `inspect` is a resource's kind, name, and ref (or
entrypoint), and `--json` prints the whole `StrategyInfo`. `lllm shell
serve` and `python -m aaax serve` are the same command as `aaax serve`,
and `aaax launch` is another name for it.

| Target | Loads |
| --- | --- |
| A `.py` file | Its `build_strategy()`, or else its `strategy` |
| A folder | `strategy.py`, else `shell.py`, else the package in `lllm.toml` |
| `lllm.toml` | The package, as a strategy named after it |
| `module:attribute` | A `Strategy`, or a function without parameters that returns one, imported from the working directory |

`--host` defaults to `127.0.0.1` and must be a host name or address, not a
URL or `host:port`. `--port` defaults to 8400 (LLLM's `lllm serve` uses
8000). `--log-level` is one of `critical`, `debug`, `error`, `info` (the
default), `trace`, or `warning`. A bad option, a target that does not load,
missing API keys, or a strategy whose store needs a missing SSSN stops the
command with exit status 2 and a message. The [CLI reference](api/cli.md)
lists every option.

### API keys

Before it starts, `aaax serve` checks the API keys of every package it
serves, a package folder or the packages a strategy file mounts: the keys
`lllm serve` checks for the package, its `[requirements.api_keys]` plus
those of the resource `lllm serve` would launch
([API keys](https://lllm.one/packages/#api-keys)), and the keys each of
its tactics declares, since AAAX serves them all. When the environment has
every key, that is all. Otherwise a key also counts when it is in the env
file (`--env-file`, default `.env.local`) or in the OS keyring, the two
places `lllm setup` stores keys: the keyring when LLLM's `secure` extra is
installed, the env file otherwise. A key found there is put in the
server's environment before any package code is imported. In a terminal,
`aaax serve` asks for missing keys and stores them as `lllm setup` does
(`--credentials auto`, `keyring`, or `env`; in the env file under
`--no-keyring`, which refuses `--credentials keyring`); otherwise it stops
and lists them. A default `.env.local` that cannot be read, a symlink
included (even a broken one), counts as absent, and the message says why;
keys are not asked for when they would have to go to that file. An env
file you name with `--env-file` that exists must be a regular file you can
read, not a symlink (even a broken one), or the command stops before it
asks for anything; one that does not exist yet is created when keys are
stored in it. `~` and `~user` are expanded, also in `--env-file=~/...` and
after a leading `./` (`./~name` is read as `~name`). One that cannot be
expanded, such as `~` followed by a user name the system does not know
(on Linux and macOS; on Windows, Python guesses `C:\Users\name`
instead), is a usage error; name a file whose name begins with `~` by
its absolute path.

Without a terminal, missing keys stop the command with a message that
names them and says how to set them:

```text
$ aaax serve support-desk
aaax: error: missing required API key(s):
- OPENAI_API_KEY - Model access for the triage agent.

Run `lllm setup support-desk` or set the missing names in your environment.
```

A key only one tactic declares is stored with `lllm setup PACKAGE
--resource tactics.NAME`, and the message names that command.
`--no-keyring` leaves the keyring out, and `--skip-key-check` starts without
checking. A package mounted with `bind=False` runs no code, so its keys are
not checked. Only the command checks keys: an app you build with
`create_strategy_app` and run yourself sees the environment it is given.

## Your own server

`create_strategy_app` returns a plain FastAPI app, titled with the
strategy's name and description and versioned with AAAX's version; the
strategy is at `app.state.aaax_strategy`. To choose the server or wrap the
app, put `app = create_strategy_app(build_strategy())` in a module and run
it with any ASGI server, as in `uvicorn app:app`.

The app has no authentication, and handlers and package code run in the
server process, so serve it on localhost or behind a gateway. Middleware on
the strategy app also covers the mounted tactic services and `/network/`,
so one check guards every route; LLLM's
[Authentication](https://lllm.one/serving/#authentication) section has a
bearer-token middleware that works here unchanged. AAAX does not manage
TLS, replicas, workers, secrets, or deployment; those belong to whatever
runs the app.

A page on another site can make a visitor's browser send a form, a text
body, or a GET to a server on their machine without asking it first. So
the app refuses, with a 403 `CrossSiteRequestError`, a cross-site POST
whose body is not JSON, and a cross-site GET or HEAD to a tactic's custom
endpoints, which run its code; a tactic's `info`, `docs`, and
`openapi.json`, and the strategy's own read routes, stay open. A request
is cross-site when its `Sec-Fetch-Site` header says `cross-site` or
`same-site`, or, without that header, when its `Origin` is `null` or names
another host and port than the `Host` header. Scripts and other servers
send neither, and are not affected. Browsers check a cross-origin JSON
request, and any PUT, PATCH, or DELETE, against the app's CORS settings
before sending it, and the app allows none until you add FastAPI's
`CORSMiddleware`. For an app that browsers on other origins must reach,
build it with `create_strategy_app(strategy,
allow_cross_site_requests=True)`.

The check does not stop DNS rebinding, where a site makes its own domain
resolve to `127.0.0.1` so that its requests look same-origin. A local
strategy app also needs a host allowlist, such as Starlette's
`TrustedHostMiddleware` with `localhost` and `127.0.0.1`, or a token as in
LLLM's [Authentication](https://lllm.one/serving/#authentication):

```python title="local.py"
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

from aaax import Strategy, create_strategy_app


def triage(text: str) -> str:
    return "oncall" if "outage" in text.lower() else "support"


desk = Strategy("desk").tactic("triage", handler=triage)
app = create_strategy_app(desk)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"]
)

client = TestClient(app, base_url="http://127.0.0.1:8400")
url = "/tactics/triage/run"
page = {"origin": "https://evil.example", "content-type": "text/plain"}
print(client.post(url, content="Outage", headers=page).status_code)
#> 403
body = {"input": "Outage"}
rebound = {"host": "evil.example:8400"}  # (1)!
print(client.post(url, json=body, headers=rebound).status_code)
#> 400
print(client.post(url, json=body).json()["output"])
#> oncall
```

1. A rebound page's requests carry its own name in `Host`, which the
   allowlist refuses before the tactic runs.
