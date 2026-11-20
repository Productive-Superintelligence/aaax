# Packages

AAAX mounts LLLM packages: folders described by an `lllm.toml`, the format
that `lllm serve` and the [LLLM Hub](https://lllm.one/publishing/) read.
Mounting a package adds a resource for each thing its manifest declares,
under a local name you can choose, and keeps the refs the package gave them.
Package code is imported only when it is used, by the same rule
`lllm serve` uses, so a mounted tactic behaves as it would if the package
were served alone.

```python title="mount.py"
from pathlib import Path

from fastapi.testclient import TestClient

from aaax import create_strategy_app, strategy_from_package

Path("support-desk").mkdir()
Path("support-desk/lllm.toml").write_text(
    """
[package]
org = "demo"
name = "support-desk"
description = "Triage support messages."

[tactics.triage]
entry = "support_desk:triage"
description = "Assign a priority to a support message."

[channels.inbox]
description = "Support messages as they arrive."
"""
)
Path("support-desk/support_desk.py").write_text(
    """
def triage(ticket: dict) -> dict:
    urgent = "down" in ticket["text"].lower().split()
    return {"priority": "urgent" if urgent else "normal"}
"""
)

desk = strategy_from_package("support-desk")  # (1)!
for resource in desk.resources:
    print(resource.kind, resource.name, resource.ref)
    #> package support-desk lllm://demo/support-desk
    #> tactic triage lllm://demo/support-desk/tactics/triage
    #> channel inbox lllm://demo/support-desk/channels/inbox
print(Path("support-desk/.lllm").exists())  # (2)!
#> False

client = TestClient(create_strategy_app(desk))  # (3)!
ticket = {"text": "Checkout is down"}
response = client.post("/tactics/triage/run", json={"input": ticket})
print(response.json()["output"])
#> {'priority': 'urgent'}
print(Path("support-desk/.lllm/network").is_dir())
#> True
```

1. One strategy from one package, named after it. The refs come from the
   manifest: `lllm://ORG/PACKAGE` for the package, and
   `lllm://ORG/PACKAGE/SECTION/NAME` for what it declares.
2. Building the strategy only read the manifest: the package's code is not
   imported, and the store for its channel does not exist yet.
3. Serving the strategy imports `support_desk` and creates the store, with
   the `inbox` channel, at `support-desk/.lllm/network`. Stores come from
   SSSN, so a package with channels needs `pip install "aaax[channels]"`.

## Serve a package folder

`aaax inspect` and `aaax serve` take a package folder, or its `lllm.toml`,
and build the strategy with `strategy_from_package`:

```bash
aaax inspect support-desk
aaax serve support-desk --port 8400
curl -X POST localhost:8400/tactics/triage/run \
  -H 'content-type: application/json' \
  -d '{"input": {"text": "Checkout is down"}}'
```

```text
support-desk: Triage support messages.
package support-desk lllm://demo/support-desk
tactic triage lllm://demo/support-desk/tactics/triage
channel inbox lllm://demo/support-desk/channels/inbox
```

`lllm serve support-desk` serves one resource, the package's `primary`;
AAAX serves everything it declares, tactics and channels, as one API. A folder that also
holds a `strategy.py` (or `shell.py`) loads that file instead, so a strategy
file can wrap the package it sits in ([Strategies](strategies.md#load-a-strategy-from-a-file)).

`strategy_from_package(path, *, name=None, prefix=None, store=None,
bind=True)` names the strategy after the package unless you pass `name`,
uses the package's description, and copies `package` (`org/name`),
`version`, `source` (the folder), and `card` into the strategy's
`metadata`.

Unlike `lllm serve`, AAAX does not check the API keys a package declares
under `[requirements.api_keys]`. Before serving a package whose tactics
call models, put its keys in the environment; `lllm inspect support-desk`
lists them.

## Mount packages into a strategy

`add_package(strategy, path, *, prefix=None, store=None, bind=True)` mounts
a package into a strategy you already have, next to your own tactics and
other packages. `strategy.use_package(path, ...)` is the same call as a
method, and returns the strategy so calls chain.

A package's names must not clash with names the strategy already has. A
package that clashes is rejected before anything is added, and a `prefix`
mounts every name as `PREFIX.NAME` instead:

```python title="ops.py"
from pathlib import Path

from lllm import Tactic

from aaax import Strategy

Path("support-desk").mkdir()
Path("support-desk/lllm.toml").write_text(
    """
[package]
org = "demo"
name = "support-desk"

[tactics.triage]
entry = "support_desk:triage"

[channels.inbox]
"""
)
Path("support-desk/support_desk.py").write_text(
    """
def triage(ticket: dict) -> dict:
    urgent = "down" in ticket["text"].lower().split()
    return {"priority": "urgent" if urgent else "normal"}
"""
)


class Triage(Tactic):
    """Route an incident to a team."""

    name = "triage"

    def call(self, text: str) -> str:
        return "network" if "dns" in text.lower() else "platform"


ops = Strategy("ops", description="Incidents and support in one API.")
ops.add_tactic(Triage())
try:
    ops.use_package("support-desk")  # (1)!
except ValueError:
    print([resource.name for resource in ops.resources])
    #> ['triage']

ops.use_package("support-desk", prefix="support")  # (2)!
for resource in ops.resources:
    print(resource.kind, resource.name, resource.ref)
    #> tactic triage None
    #> package support.support-desk lllm://demo/support-desk
    #> tactic support.triage lllm://demo/support-desk/tactics/triage
    #> channel support.inbox lllm://demo/support-desk/channels/inbox

print(ops.store.root.relative_to(Path("support-desk").resolve()))  # (3)!
#> .lllm/network
print(ops.tactics()["support.triage"].package_ref)  # (4)!
#> lllm://demo/support-desk/tactics/triage
```

1. The package has a `triage` tactic too, so it is rejected, and the
   strategy is left as it was: `ValueError: Cannot mount package
   demo/support-desk: strategy 'ops' already has resources named triage.
   Mount it with a prefix to keep the names apart.`
2. With a prefix, the package's names are `support.*`. Its refs do not
   change.
3. The package declares a channel and the strategy had no store, so the
   package gave it one ([below](#channels-share-the-strategys-store)).
4. The loaded tactic carries its manifest ref, whatever it is called in
   the strategy.

## What each manifest section becomes

| Section | Resource kind | Name | Handler, when bound |
| --- | --- | --- | --- |
| `[package]` | `package` | The package's name | |
| `[config]` | `config` | `default` | |
| `[schemas.NAME]` | `schema` | `NAME` | |
| `[tactics.NAME]` | `tactic` | `NAME` | Its `entry`, loaded as an LLLM tactic |
| `[channels.NAME]` | `channel` | `NAME` | The channel of the same name in the strategy's store |
| `[snapshots.NAME]` | `snapshot` | `NAME` | |
| `[services.NAME]` | `service` | `NAME` | The handler of the `tactic` it names, if that is one of the package's tactics |
| `[runs.NAME]`, `[docs.NAME]`, `[examples.NAME]`, `[assets.NAME]` | `run`, `doc`, `example`, `asset` | `NAME` | |

Every name gets the prefix when there is one. Each record keeps the
manifest's `description`, its `entry` as the `entrypoint` (for tactics,
services, and schemas), and in its `metadata` the package (`org/name`), its
`version`, the `resource` name in the manifest, and the section's own
fields, such as a tactic's `runtime` and `examples` or a channel's `form`.
The `[card]` goes into the package resource's metadata. Discovery sections,
such as `[prompts] paths = [...]`, are not mounted: LLLM reads them when the
package's own code loads its runtime ([Packages](https://lllm.one/packages/)).

## Tactics load on first use

A tactic's `entry` is imported the first time the strategy needs the
tactic: when the app is built, when `strategy.tactics()` is called, or when
the resource is invoked. AAAX imports it from the package folder and turns
the value into a tactic with LLLM's `coerce_tactic`, the rule `lllm serve`
uses:

| The entry names | It becomes |
| --- | --- |
| A `Tactic` subclass | An instance, built with no arguments |
| A `Tactic` instance | That tactic |
| A factory: a function without parameters, or one annotated to return a tactic | What it returns; it is called once, when the tactic loads |
| An object with a `run` method | Its `run`, wrapped with `as_tactic` |
| Any other callable | A handler, wrapped with `as_tactic` and called once per input |

[How entrypoints become tactics](https://lllm.one/runtimes/#how-entrypoints-become-tactics)
has the fine print. The loaded tactic is served under its local name, such
as `support.triage`, and one without a `package_ref` of its own gets the
manifest's ref, so its `/info` and the `tactic_ref` of every request's
`CallContext` name it by ref. Both are set on a copy, and the imported
object is left as it is. The strategy's record takes its
description from the manifest, while the tactic's `/info` takes it from the
code, such as a docstring.

Loaded code stays loaded, and the package folder stays on `sys.path`, so a
package's code can import its own modules while it runs. Packages mounted
in one process share `sys.modules`, though: give their top-level modules
distinct names, such as `support_desk.py` rather than `tactics.py`, or two
packages that both ship a `tactics.py` end up sharing one of them.

## Channels share the strategy's store

A strategy has one channel store, and a package's channels live in it.
Mounting a package that declares channels gives a strategy without a store
one, at `store=` if you pass it and otherwise at
`<package>/.lllm/network`. Packages mounted later share it:

- Channels are created in the store under their local names, such as
  `support.inbox`, so packages with different prefixes never share a
  channel. Channels that already exist in the store are kept.
- A later `store=` that names another folder raises `ValueError`, before
  anything is added; naming the same folder is fine.
- The store folder and its channels are created on first use, when the app
  is built or a channel is used, never while the strategy is built or
  inspected.

To choose the store yourself, attach one before you mount packages, and
they use it ([Attach a store](channels.md#attach-a-store)). Stores, events,
and the store API at `/network/` come from [SSSN](https://sssn.one/);
[Channels](channels.md) covers reading and writing events.

## Mount a package for reference

`bind=False` adds the records and nothing else: no tactic handlers, so no
`/tactics/{name}/` routes, and no store. Invoking one of its resources
returns the record. Use it for a package that runs somewhere else, so that
people and agents reading the strategy still see its card, refs, docs, and
examples.

## Packages from the LLLM Hub

A package from the hub is an ordinary folder once it is on disk. A local
hub, a folder (`.lllm/hub` by default), hands it out with `lllm hub get`:

```bash
lllm hub publish support-desk --local         # validate, publish
lllm hub get demo/support-desk --dest vendor  # to vendor/support-desk
aaax serve vendor/support-desk --port 8400
```

Packages on [lllm.one/hub](https://lllm.one/hub/) download as zips with the
`lllm.toml` at their root:

```bash
curl -L -o analyst-tactics.zip \
  https://lllm.one/hub/api/packages/society/analyst-tactics/download
unzip analyst-tactics.zip -d vendor/analyst-tactics
aaax inspect vendor/analyst-tactics
```

A strategy file can mount several of them, each under its own prefix.
[The hub](https://lllm.one/publishing/) covers validating, publishing, and
the cards that AAAX copies into its records.

## Call a mounted tactic by ref

Every tactic in a strategy is a standard LLLM tactic service, at
`/tactics/{name}/`. So code that calls a tactic by its ref, through LLLM's
`Resolver`, keeps working when the tactic moves into a strategy: bind the
ref to that URL in the project's `.lllm/config.toml`.

```python title="by_ref.py"
from pathlib import Path

from lllm import Resolver

TRIAGE = "lllm://demo/support-desk/tactics/triage"

Path(".lllm").mkdir()
Path(".lllm/config.toml").write_text(
    f"""
[refs."{TRIAGE}"]
url = "http://127.0.0.1:8400/tactics/support.triage"
"""
)

triage = Resolver.from_config(".").tactic(TRIAGE)
print(type(triage).__name__, triage.url)
#> RemoteTactic http://127.0.0.1:8400/tactics/support.triage/run
```

With a strategy that mounts the package under the prefix `support` served
on port 8400, `triage.run({"text": "Checkout is down"})` returns
`{'priority': 'urgent'}`. The URL uses the local name, `support.triage`,
and the ref stays the package's. [Local configuration](https://lllm.one/packages/#local-configuration)
covers the rest of the file.
