# Use with LLLM

AAAX is the strategy shell of the [LLLM](https://lllm.one/) family. LLLM runs
tactics and owns packages and the hub, [SSSN](https://sssn.one/) keeps
channels, and AAAX mounts them into one `Strategy` served as one API. The
`aaax` package depends on `lllm-core` and plugs into it in four places:

| LLLM piece | What AAAX adds |
| --- | --- |
| Tactics | A strategy mounts LLLM tactics and serves each with LLLM's tactic service at `/tactics/<name>/`. |
| Packages and the hub | `lllm.toml` packages, from a folder or the LLLM hub, mount in one call and keep their `lllm://` refs. |
| The `lllm` command | `lllm shell`, the AAAX CLI. |
| Channels | Through SSSN: channel resources are backed by one SSSN store, served at `/network/`. |

## Install

```bash
pip install aaax                 # or: pip install "lllm-core[shell]"
pip install "aaax[channels]"     # with SSSN channel stores
```

`aaax` depends on `lllm-core` with its FastAPI server. SSSN is optional: AAAX
imports it only for a channel store and says what to install when it is
missing or older than 0.2. The examples on this page run top to bottom as one
session, with `aaax[channels]` and `httpx` (for FastAPI's `TestClient`)
installed.

## Mount LLLM Tactics

`add_tactic(tactic, *, name=None, ref=None, description=None, metadata=None)`
mounts an LLLM tactic as a tactic resource. The name defaults to
`tactic.info().name` and the ref to the tactic's `package_ref`; the runtime
kind is recorded in the metadata.

```python
from pydantic import BaseModel

from lllm import Tactic
from aaax import Strategy


class Text(BaseModel):
    text: str


class Shout(Tactic[Text, Text]):
    name = "shout"
    description = "Upper-case a message."
    input_type = Text
    output_type = Text

    def _run(self, input_value, *, context=None):
        return Text(text=input_value.text.upper())


strategy = Strategy("loud-desk", description="Shout at things.")
strategy.add_tactic(Shout(), ref="lllm://demo/loud-desk/tactics/shout")


@strategy.runner
async def run(input_value, *, context=None):
    first = await strategy.tactics()["shout"].arun(input_value)
    return {"once": first.text, "twice": f"{first.text}!!"}
```

`create_strategy_app` serves it:

```python
from fastapi.testclient import TestClient

from aaax import create_strategy_app

client = TestClient(create_strategy_app(strategy))
print(client.post("/tactics/shout/run", json={"input": {"text": "hello"}}).json()["output"])
print(client.post("/run", json={"input": {"text": "hello"}}).json())
```

```text
{'text': 'HELLO'}
{'output': {'once': 'HELLO', 'twice': 'HELLO!!'}, 'strategy': 'loud-desk', 'metadata': {}}
```

A plain function also works as a tactic handler:

```python
def count_words(payload: dict) -> dict:
    return {"words": len(payload["text"].split())}


strategy.tactic("count", handler=count_words, description="Count words.")
print(sorted(strategy.tactics()))
```

```text
['count', 'shout']
```

`strategy.tactics()` returns every tactic resource that has a handler as an
LLLM `Tactic`, wrapping plain functions with `lllm.as_tactic`. Each one is
mounted with LLLM's `create_tactic_app` at `/tactics/<name>/`, so it gets the
full [tactic service](https://lllm.one/protocol/services/): `run`, `stream`,
`info`, and custom tactic endpoints, with the services request and error
envelopes. The `context` of a run has the shape of an LLLM `CallContext`
(`request_id`, `trace_id`, `caller`, `tags`, `metadata`, and the other
fields); keys that are not `CallContext` fields are dropped, so send your own
values in `metadata`. `POST /resources/<name>/invoke` runs a tactic resource
the same way.

## Mount LLLM Packages

A folder with an `lllm.toml` is an LLLM package (see
[the manifest](https://lllm.one/packages/manifest/)):

```text
support-desk/
  lllm.toml
  tactics.py
```

`support-desk/lllm.toml`:

```toml
[package]
org = "demo"
name = "support-desk"
version = "0.1.0"
kind = "app"
description = "Triage support messages."

[tactics.triage]
entry = "tactics:triage"
description = "Assign a priority to a support message."

[channels.inbox]
description = "Support messages as they arrive."
```

`support-desk/tactics.py`:

```python
def triage(ticket: dict) -> dict:
    urgent = "down" in ticket["text"].lower().split()
    return {"priority": "urgent" if urgent else "normal"}
```

It mounts in one call:

```python
from pathlib import Path

from aaax import strategy_from_package

desk = strategy_from_package("support-desk")
for resource in desk.resources:
    print(resource.kind, resource.name, resource.ref)
print(desk.store.root.relative_to(Path("support-desk").resolve()))
```

```text
package support-desk lllm://demo/support-desk
tactic triage lllm://demo/support-desk/tactics/triage
channel inbox lllm://demo/support-desk/channels/inbox
.lllm/network
```

The tactic entry loads through LLLM's `coerce_tactic`, the rule `lllm serve`
uses: a `Tactic` class or instance is mounted, a factory is called once when
the tactic loads, and any other callable, like `triage`, is a handler called
once per input. Packages load lazily: building or inspecting the strategy
imports no package code and creates no store folder; serving it, calling
`strategy.tactics()`, or invoking the resource does. A package tactic that
declares no `package_ref` reports its manifest ref,
`lllm://demo/support-desk/tactics/triage` here, in `/tactics/triage/info` and
as the `tactic_ref` of the `CallContext` it receives. [LLLM
Packages](../composition/packages.md) lists what every manifest section
becomes.

To combine packages and your own tactics, mount packages into a strategy; a
`prefix` keeps names apart:

```python
ops = Strategy("ops", description="Support and loud desks in one API.")
ops.use_package("support-desk", prefix="support")
ops.add_tactic(Shout())
print([resource.name for resource in ops.resources])
```

```text
['support.support-desk', 'support.triage', 'support.inbox', 'shout']
```

### Packages From The LLLM Hub

Packages on the [LLLM hub](https://lllm.one/packages/hub/) are ordinary
package folders once fetched, so AAAX serves them like any other:

```bash
lllm hub publish support-desk --local          # validate and publish to .lllm/hub
lllm hub get demo/support-desk --dest vendor   # fetch it into vendor/support-desk
aaax inspect vendor/support-desk
aaax serve vendor/support-desk --port 8400
```

A `strategy.py` can mount several fetched packages with `use_package`, each
under its own prefix. Package code is imported into the server process and
stays loaded, so give packages you mount together distinct top-level module
names.

## Channels Through SSSN

Channel resources are backed by an SSSN store. `desk` had no store, so
mounting the package gave it one at `<package>/.lllm/network`; the folder and
the `inbox` channel are created on first use, here when the app is built. The
channel shortcuts, the tactic, and SSSN's store API at `/network/` all work on
the same events:

```python
client = TestClient(create_strategy_app(desk))
client.post(
    "/channels/inbox/events",
    json={"input": {"kind": "message", "payload": {"text": "Checkout is down"}}},
)
events = client.get("/channels/inbox/events").json()["output"]
print([(event["kind"], event["source"], event["payload"]) for event in events])
print(client.post("/tactics/triage/run", json={"input": events[0]["payload"]}).json()["output"])
print([event["payload"] for event in client.get("/network/events", params={"channel": "inbox"}).json()])
```

```text
[('message', 'aaax', {'text': 'Checkout is down'})]
{'priority': 'urgent'}
[{'text': 'Checkout is down'}]
```

`strategy.store` forwards store methods to the SSSN store, so an SSSN
[`TacticProcessor`](https://sssn.one/guides/lllm/) over it connects a mounted
tactic to a channel: it reads `inbox` through a named subscription, runs each
event through the tactic, and appends the result to a sink channel.

```python
from sssn import TacticProcessor

desk.store.create_channel({"name": "triaged"})
processor = TacticProcessor(desk.tactics()["triage"], desk.store, source="inbox", sink="triaged")
for event in processor.process():
    print(event.source, event.payload, event.parent_ids == (events[0]["id"],))
```

```text
triage-inbox-processor {'priority': 'urgent'} True
```

A strategy has one store. To pick it yourself, attach an SSSN `LocalStore` or
`RemoteStore` with `strategy.attach_store(store)` before mounting packages,
which then share it; see [Channels And
Services](../composition/channels-services.md). Without SSSN, inspecting and
building still work, and the first use of the store raises
`ImportError: Channel stores need the sssn package: pip install sssn`.

## The `lllm shell` Command

Installing `aaax` adds `lllm shell` through an entry point in AAAX's
`pyproject.toml`:

```toml
[project.entry-points."lllm.commands"]
shell = "aaax.cli"
```

`lllm shell` and `aaax` are the same CLI; usage and error messages name the
command you typed:

```bash
lllm shell inspect support-desk
lllm shell serve support-desk --port 8400
aaax serve support-desk --port 8400     # the same server
lllm --help                             # lists shell next to the core commands
```

Without `aaax`, `lllm shell` prints
`lllm shell needs the aaax package: pip install aaax` and exits with status 2.
Every option is in the [CLI reference](../reference/cli.md).

## Call A Served Strategy By Ref

Each mounted tactic is a standard LLLM tactic service, so `lllm.Resolver`
reaches it by ref. Bind the ref to the tactic's URL in `.lllm/config.toml`:

```toml
[refs."lllm://demo/support-desk/tactics/triage"]
url = "http://127.0.0.1:8400/tactics/triage"
```

With `aaax serve support-desk --port 8400` running:

```python
from lllm import Resolver

triage = Resolver.from_config(".").tactic("lllm://demo/support-desk/tactics/triage")
print(type(triage).__name__, triage.run({"text": "Checkout is down"}))
```

```text
RemoteTactic {'priority': 'urgent'}
```

## Coming From `lllm.shell`

LLLM 0.3 shipped this code as `lllm.shell`. In LLLM 0.4 that module is a
deprecated alias: it imports `aaax`, warns once, and keeps old import paths
working (`lllm.shell.server` is `aaax.server`). Replace
`from lllm.shell import ...` with `from aaax import ...`; the names are the
same. `lllm shell` keeps working once `aaax` is installed, and a directory's
`shell.py` still loads. Two things read differently: events appended without
a `source` say `aaax` instead of `lllm.shell`, and the app reports AAAX's
version.
