# Advanced Autonomous Agent Executor

<p class="psi-brand">
  <img src="assets/aaax-logo-text-black.png#only-light" alt="AAAX" />
  <img src="assets/aaax-logo-text-white.png#only-dark" alt="AAAX" />
</p>

[aaax.one](https://aaax.one){ .psi-domain }

**AAAX** is the strategy shell of the LLLM family.
[LLLM](https://lllm.one/) composes agents into tactics and
[SSSN](https://sssn.one/) connects systems through channels, but an
application is rarely one tactic: it is a few tactics, a package or two
from the hub, and the channels between them. AAAX, built on LLLM, mounts
all of them into one **strategy**, gives each part a name, and serves the
strategy as a single FastAPI app.

## Why AAAX

- **One API for the whole system.** A strategy's tactics, channels, and
  packages are served by one app, next to routes that list what is there
  and a [`/run`](strategies.md#the-runner) command of your own.
- **Tactics keep their contract.** Each tactic is served by LLLM's own
  tactic service, so its `run`, `stream`, and `info` routes work as they do
  under [`lllm serve`](https://lllm.one/serving/).
- **Packages mount in one call.** An LLLM package folder, from your repo or
  the [LLLM Hub](https://lllm.one/publishing/), adds every resource its
  `lllm.toml` declares ([Packages](packages.md)).
- **Names are local, refs are stable.** Mount two packages that both have a
  `triage` tactic under different prefixes, and each keeps its `lllm://`
  ref ([Resources](resources.md)).
- **Nothing runs until it is used.** Building or inspecting a strategy
  imports no package code and creates no store, so `aaax inspect` reads a
  package without running any of it.
- **Channels share one store.** A strategy's channels live in one
  [SSSN](https://sssn.one/) store, served at `/network/` next to the
  strategy's own routes ([Channels](channels.md)).

## A first strategy

```python title="hello.py"
from fastapi.testclient import TestClient
from lllm import Tactic

from aaax import Strategy, create_strategy_app


class Triage(Tactic):
    """Route a support ticket to a queue."""

    name = "triage"

    def call(self, text: str) -> str:
        return "oncall" if "outage" in text.lower() else "support"


strategy = Strategy("desk", description="The support desk as one API.")
strategy.add_tactic(Triage())

client = TestClient(create_strategy_app(strategy))
body = {"input": "Total outage"}
response = client.post("/tactics/triage/run", json=body)
print(response.json()["output"])
#> oncall
```

`Triage` is an ordinary [LLLM tactic](https://lllm.one/tactics/). Its
`call()` is plain Python here, and a tactic whose agents call models mounts
the same way. `add_tactic` mounts it under its name, `create_strategy_app`
builds the FastAPI app, and `TestClient` calls the app in the same process.

## A real strategy: tactics, a package, and a runner

A strategy is for gathering parts that come from different places. This
support desk uses a tactic of its own, a plain function, and a search
tactic from a knowledge-base package, and answers each ticket through one
`/run` command:

```python title="desk.py"
from pathlib import Path

from fastapi.testclient import TestClient
from lllm import Tactic, as_tactic

from aaax import Strategy, create_strategy_app

Path("kb").mkdir(exist_ok=True)  # (1)!
Path("kb/lllm.toml").write_text(
    """
[package]
org = "acme"
name = "knowledge-base"
description = "Help articles for the support desk."

[tactics.search]
entry = "kb_search:search"
description = "Find the help article for a ticket."
"""
)
Path("kb/kb_search.py").write_text(
    """
ARTICLES = {
    "refund": "Refunds reach your card in 5 business days.",
    "outage": "Live status: status.acme.com.",
}

def search(text: str) -> str:
    words = text.lower().split()
    found = [body for key, body in ARTICLES.items() if key in words]
    return found[0] if found else "No article found."
"""
)


class Triage(Tactic):
    """Route a support ticket to a queue."""

    name = "triage"

    def call(self, text: str) -> str:
        return "oncall" if "outage" in text.lower() else "support"


def redact(text: str) -> str:
    """Hide email addresses."""
    return " ".join("[email]" if "@" in w else w for w in text.split())


strategy = Strategy("desk", description="The support desk as one API.")
strategy.add_tactic(Triage())
strategy.add_tactic(as_tactic(redact))  # (2)!
strategy.use_package("kb", prefix="kb")  # (3)!


@strategy.runner  # (4)!
async def run(ticket: str) -> dict:
    text = await strategy.invoke_resource("redact", ticket)
    return {
        "queue": await strategy.invoke_resource("triage", text),
        "article": await strategy.invoke_resource("kb.search", text),
        "ticket": text,
    }


client = TestClient(create_strategy_app(strategy))
for resource in client.get("/resources").json():  # (5)!
    print(resource["kind"], resource["name"], resource["ref"])
    #> tactic triage None
    #> tactic redact None
    #> package kb.knowledge-base lllm://acme/knowledge-base
    #> tactic kb.search lllm://acme/knowledge-base/tactics/search

ticket = "Outage again. Write to ada@example.com"
print(client.post("/run", json={"input": ticket}).json()["output"])  # (6)!
"""
{
    'queue': 'oncall',
    'article': 'Live status: status.acme.com.',
    'ticket': 'Outage again. Write to [email]',
}
"""
```

1. A package is a folder with an `lllm.toml`, the format of the LLLM Hub.
   The example writes one so that it runs anywhere; usually the folder
   comes from your repo or the hub.
2. `as_tactic` turns a function into a tactic, named after the function and
   described by its docstring.
3. Mounts every resource the package declares. The prefix keeps its names
   apart from yours, so its `search` tactic is `kb.search` here. Its code is
   imported when the strategy is served, not when it is built.
4. The runner is the strategy's own command, `POST /run`. It calls the other
   resources by their local names.
5. `GET /resources` lists the strategy's table: each resource's kind, local
   name, and ref. The package's resources keep their `lllm://` refs,
   whatever they are called here.
6. The `/run` response also names the strategy and carries metadata;
   `output` is what the runner returned.

Each tactic still has its own routes: `POST /tactics/kb.search/run` runs the
package's search alone, with LLLM's request and response envelopes.

## Serve it

`aaax serve` loads the file's `strategy` and runs the app with Uvicorn:

```bash
aaax serve desk.py --port 8400
curl -X POST localhost:8400/run -H 'content-type: application/json' \
  -d '{"input": "Outage again. Write to ada@example.com"}'
```

You get `POST /run`, `/tactics/{name}/run`, `/stream`, and `/info` for every
tactic, `GET /resources` and `/strategy`, and OpenAPI docs at `/docs`.
`lllm shell serve desk.py` is the same command. See [Serving](serving.md).

## How the pieces fit

AAAX treats an application as a table of named parts behind one API:

- **Strategy is the application.** It has a name, a description, its
  resources, and an optional runner behind `/run`.
- **Resource is a named part.** A tactic, channel, package, service, doc,
  or another kind, with a local name in this strategy and a stable ref.
- **Handler makes a resource callable.** A tactic resource runs an LLLM
  tactic, other resources call plain Python, and a channel without a
  handler is backed by the strategy's store.
- **The app is the boundary.** `create_strategy_app` serves tactics with
  LLLM's tactic service, channels with SSSN's store API, and the table with
  routes of its own.

[How AAAX works](concepts.md) explains the model in one page, and each part
has its own guide.

## Next steps

- [Install AAAX](install.md).
- [Build a strategy](strategies.md), and learn how its
  [resources](resources.md) are named and called.
- [Mount packages](packages.md) from a folder or the LLLM Hub.
- Add [channels](channels.md), then [serve](serving.md) the result.
- Hand a strategy to [agents](agents.md).
- Browse complete [examples](examples/index.md).

## The LLLM family

- **[LLLM](https://lllm.one/)** (`pip install lllm-core`) builds tactics:
  programs whose agents call models, each typed and served on its own.
- **[LLLM Hub](https://lllm.one/hub/)** hosts packages, each described by
  one `lllm.toml`, which AAAX mounts in one call.
- **[SSSN](https://sssn.one/)** (`pip install sssn`) adds channels: events,
  artifacts, and snapshots in stores that connect systems.
- **AAAX** (`pip install aaax`) mounts tactics, packages, and channels into
  a strategy and serves it as one API.

SSSN and AAAX are separate packages built on LLLM. Installing them adds
`lllm network` and `lllm shell` to the `lllm` command.
