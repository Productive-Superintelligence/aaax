# Strategies

A `Strategy` is the application AAAX serves: a name, a table of resources,
the handlers that make some of them callable, and an optional runner behind
`/run`. You build one with a few method calls. Each returns the strategy,
so the calls chain, and none of them imports package code or opens a store:
building a strategy only fills in its table.

```python title="desk.py"
import asyncio

from lllm import Tactic, as_tactic

from aaax import Strategy


class Triage(Tactic):
    """Route a support ticket to a queue."""

    name = "triage"

    def call(self, text: str) -> str:
        return "oncall" if "outage" in text.lower() else "support"


def word_count(text: str) -> int:
    """Count the words in a ticket."""
    return len(text.split())


strategy = (
    Strategy("desk", description="The support desk as one API.")  # (1)!
    .add_tactic(Triage())  # (2)!
    .add_tactic(as_tactic(word_count, name="words"))
    .channel("inbox", description="Tickets as they arrive.")  # (3)!
)


@strategy.runner  # (4)!
async def run(ticket: str) -> dict:
    return {
        "queue": await strategy.invoke_resource("triage", ticket),
        "words": await strategy.invoke_resource("words", ticket),
    }


for resource in strategy.info().resources:  # (5)!
    print(resource.kind, resource.name, "-", resource.description)
    #> tactic triage - Route a support ticket to a queue.
    #> tactic words - Count the words in a ticket.
    #> channel inbox - Tickets as they arrive.
print(asyncio.run(strategy.arun("Total outage in eu-west")))  # (6)!
#> {'queue': 'oncall', 'words': 4}
```

1. The name is a path segment, such as `desk` or `support-desk.v2`
   ([Naming rules](#naming-rules)).
2. `add_tactic` mounts an LLLM tactic. Its local name, description, and ref
   come from the tactic's `info()`.
3. A channel resource. Until the strategy has a store, it is only listed;
   [Channels](channels.md) backs it with an SSSN store.
4. The runner answers `POST /run`, and `arun()` calls it from Python.
5. `info()` returns the strategy's public description, the data
   `GET /strategy` serves.
6. Calls into a strategy are async; `asyncio.run` drives one from a script.

## Mount tactics

`add_tactic(tactic, *, name=None, ref=None, description=None,
metadata=None)` mounts a tactic as a tactic resource. Any LLLM tactic
works: a native `lllm.Tactic`, a function wrapped with `as_tactic`, a
Pydantic AI agent in a `PydanticAITactic`, or a `RemoteTactic` that calls a
service elsewhere ([Runtimes](https://lllm.one/runtimes/)). The tactics on these pages are
plain Python so the examples run anywhere; a tactic whose agents call
models mounts the same way ([Tactics](https://lllm.one/tactics/)).

| Parameter | Default |
| --- | --- |
| `name` | The tactic's name; it is the local name and the route `/tactics/{name}/` |
| `ref` | The tactic's `package_ref` |
| `description` | The tactic's description, usually its docstring |
| `metadata` | Yours, plus `runtime`: the tactic's runtime kind, such as `native` or `python` |

`name`, `ref`, and `description` apply where the tactic is served too. A
tactic mounted as `add_tactic(as_tactic(word_count), name="words")` is
served at `/tactics/words/`, and its responses and `/info` name it `words`.
A `ref` you pass is the `package_ref` its `/info` reports and the
`tactic_ref` its requests carry, and a `description` is the one its
`/info` gives. The strategy serves a copy that has them, and the tactic you
passed in keeps its own. A `ref` that is not a tactic ref,
`lllm://ORG/PACKAGE/tactics/NAME`, labels only the record.

`strategy.tactic(name, handler=fn)` mounts a plain function without
wrapping it yourself. AAAX wraps it with `lllm.as_tactic` when the strategy
is served or the tactic is used, so it is a full tactic too. Its record and
its `/info` take the `description` you pass, or else the function's
docstring, as `add_tactic(as_tactic(fn))` does, and its `ref` reaches the
tactic as `add_tactic`'s does.

`strategy.tactics()` returns every tactic resource that has a handler, as
LLLM tactics, by local name: tactic objects as they are, package tactics
loaded, and plain functions wrapped. Use it to call one tactic directly, or
to hand it to code that takes a tactic:

```python title="tactics.py"
from aaax import Strategy


def word_count(text: str) -> int:
    """Count the words in a ticket."""
    return len(text.split())


strategy = Strategy("desk").tactic("words", handler=word_count)
words = strategy.tactics()["words"]
print(words.info().name, "-", words.info().description)
#> words - Count the words in a ticket.
print(words.run("Total outage in eu-west"))
#> 4
```

When the strategy is served, each of these tactics is mounted with LLLM's
`create_tactic_app` at `/tactics/{name}/`, so it has the whole tactic
service: `run`, `stream`, `info`, and its custom endpoints. A request there,
or to `/resources/{name}/invoke`, reaches the tactic with an LLLM
`CallContext` ([How a request flows](concepts.md#how-a-request-flows)).

## Add other resources

`resource(kind, name, *, ref=None, entrypoint=None, description="",
metadata=None, handler=None)` adds a resource of any kind, and `tactic()`,
`channel()`, `service()`, `package()`, and `snapshot()` add one of their
kind:

```python title="resources.py"
from aaax import Strategy


def page(queue: str) -> str:
    return f"paged {queue}"


strategy = Strategy("desk")
strategy.service("pager", handler=page, description="Page an engineer.")
strategy.resource("doc", "runbook", ref="lllm://acme/desk/docs/runbook")
print([(r.kind, r.name) for r in strategy.resources])
#> [('service', 'pager'), ('doc', 'runbook')]
```

`add_resource(resource, *, handler=None)` adds a `StrategyResource` you
built, and `Strategy(..., resources=[...])` adds a list of them at once. A
name that is already taken raises `ValueError`. [Resources](resources.md)
covers the record, what each kind does, and how handlers are called.

## The runner

The runner is the strategy's top-level command. `POST /run` calls it, and
so does `await strategy.arun(input_value, context=None)` from Python. Set it with
the `@strategy.runner` decorator, `strategy.runner(fn)`, or
`Strategy(..., runner=fn)`. It can be sync or async, and like every handler
it receives the input if it takes a positional parameter, and the context,
as a plain dict, if it declares `context` or `**kwargs`.

Until you set one, `/run` returns the strategy's table: its name, the
input, and every resource record. That default makes a new strategy useful
before it has a workflow, because a script or an agent can ask it what it
offers:

```python title="default_run.py"
import asyncio

from aaax import Strategy

strategy = Strategy("desk")
strategy.tactic("triage", ref="lllm://acme/desk/tactics/triage")

output = asyncio.run(strategy.arun("What can you do?"))
print(sorted(output))
#> ['input', 'resources', 'strategy']
print(output["resources"][0]["ref"])
#> lllm://acme/desk/tactics/triage
```

## Call a strategy from Python

| Call | Does |
| --- | --- |
| `await strategy.arun(input_value, context=None)` | Runs the runner, as `POST /run` does |
| `await strategy.invoke_resource(name, input_value, context=None)` | Calls one resource, as `POST /resources/{name}/invoke` does |
| `strategy.tactics()` | The tactic resources as LLLM tactics |
| `strategy.info()` | The `StrategyInfo`: name, description, resources, metadata |
| `strategy.resources` | The resource records, in the order they were added |

`invoke_resource` raises `aaax.ResourceNotFoundError`, a `KeyError`, for
a name the strategy does not have. For a tactic resource,
`context` is a `CallContext` or a dict of its fields; for any other
resource, it is the plain dict the handler receives.

## Naming rules

A strategy's name, and each resource's name, must be a non-empty path
segment: no whitespace, `/`, `:`, `\`, or `%`, and not `.` or `..`. Dots,
dashes, and underscores are fine. Resource names become URL paths, such as
`/tactics/{name}/run`, and the strategy's name follows the same rule. Both
are checked when you build the strategy, not when a request arrives:

```python title="names.py"
from aaax import Strategy

try:
    Strategy("My Strategy")
except ValueError as error:
    print(error)
    #> strategy.name must be a non-empty path segment

strategy = Strategy("support-desk.v2").tactic("triage")
try:
    strategy.tactic("triage")
except ValueError as error:
    print(error)
    #> Strategy resource already exists: triage
```

A resource name that breaks the rule raises a Pydantic `ValidationError`, a
`ValueError` too, when the record is built.

## Load a strategy from a file

`load_strategy(target)` builds a strategy from a file, a folder, or an
import path. `aaax inspect` and `aaax serve` load their target with it:

| Target | Loads |
| --- | --- |
| A `.py` file | Its `build_strategy()`, called with no arguments, or else its `strategy` |
| A folder | Its `strategy.py`, else `shell.py`, else `aaax.py`; else its `lllm.toml`, as a package |
| An `lllm.toml` | The package, with `strategy_from_package` ([Packages](packages.md)) |
| `module:attribute` | A `Strategy`, or a function that returns one, imported from the working directory |

A strategy file runs with its folder on `sys.path`, so it can import the
modules next to it. While the file loads, its top level and its
`build_strategy()`, every relative package path given to `use_package`,
`add_package`, or `strategy_from_package` is relative to the file's
folder, including one that helper code the file calls gives, so the file
works from any working directory:

```python title="strategy.py"
from aaax import Strategy


def build_strategy() -> Strategy:
    strategy = Strategy("ops", description="Support and billing.")
    strategy.use_package("packages/support-desk", prefix="support")
    strategy.use_package("packages/billing", prefix="billing")
    return strategy
```

```text
$ aaax inspect .
ops: Support and billing.
package support.support-desk lllm://demo/support-desk
tactic support.triage lllm://demo/support-desk/tactics/triage
channel support.inbox lllm://demo/support-desk/channels/inbox
package billing.billing lllm://demo/billing
tactic billing.refund lllm://demo/billing/tactics/refund
```

AAAX 0.3 resolved these paths against the working directory. A path that
is not in the file's folder but is in the working directory still loads,
with a `FutureWarning` that names it: a future minor release looks in the
file's folder only. Other relative paths in the file, such as a store
folder or a file it reads, are relative to the working directory; build
those from `Path(__file__).parent`. A strategy imported as
`module:attribute` is not run as a file, so its package paths are relative
to the working directory too.

`shell.py` is the file name LLLM 0.3's `lllm shell` loaded, and it still
works. `aaax.py`, which AAAX 0.2 loaded, still loads with a
`FutureWarning`: in its folder, Python imports that file in place of the
`aaax` package, so `lllm shell` and `python -m aaax` fail there. Rename it
to `strategy.py`.

## Inspect and serve

```bash
aaax inspect strategy.py          # kind, name, and ref of each resource
aaax inspect strategy.py --json   # the whole StrategyInfo
aaax serve strategy.py --port 8400
```

Inspecting builds the strategy and prints its table without importing
package code or opening a store. `aaax serve` builds the app with
`create_strategy_app(strategy)` and runs it with Uvicorn, on port 8400 by
default. [Serving](serving.md) covers the app and its routes, and the
[CLI reference](api/cli.md) every option.
