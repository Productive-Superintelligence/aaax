# Installation

AAAX needs Python 3.10 or later. It is built on LLLM, so installing it also
installs `lllm-core` with LLLM's FastAPI server; you import it as `aaax`.

```bash
pip install aaax
```

or with uv:

```bash
uv add aaax
```

From the LLLM side, the `shell` extra installs the same thing:

```bash
pip install "lllm-core[shell]"
```

| Package | Brings |
| --- | --- |
| `lllm-core[server]>=0.4` | Tactics, packages, refs, and LLLM's tactic service, with FastAPI and Uvicorn |
| `pydantic>=2.7` | The resource and envelope models |
| `sssn>=0.2`, with the `channels` extra | Channel stores and their HTTP API |

## Channels

Channels are stored by [SSSN](https://sssn.one/). Install the `channels`
extra to use them:

```bash
pip install "aaax[channels]"
```

AAAX imports SSSN only when a channel store is used. Without it, you can
still build and serve strategies that have no store, and inspect any
strategy or package, including one that declares channels. The first use
of a store raises an `ImportError` that says what to install, and
`aaax serve` reports it before starting:

```text
aaax: error: Channel stores need the sssn package: pip install sssn
```

An SSSN older than 0.2 is not used either; the message is then
`aaax needs sssn>=0.2: pip install -U 'aaax[channels]'`. Installing SSSN
also adds `lllm network` to the `lllm` command.

## Tactics that call models

AAAX itself never calls a model. Tactics with agents that call models
need LLLM's `native` extra and a provider key, as LLLM's
[Installation](https://lllm.one/install/) explains:

```bash
pip install aaax "lllm-core[native]"
export OPENAI_API_KEY=sk-...  # or the key of any provider LiteLLM supports
```

## The command line

Installing AAAX adds the `aaax` command:

```bash
aaax --help
aaax inspect ./support-desk   # list what a package or strategy mounts
aaax serve ./support-desk     # serve it on port 8400
aaax --version                # aaax 0.3.0
```

It also adds `shell` to the `lllm` command, through this entry point in
AAAX's `pyproject.toml`:

```toml
[project.entry-points."lllm.commands"]
shell = "aaax.cli"
```

`lllm shell` and `aaax` are the same CLI, and `python -m aaax` runs it too;
usage and error messages name the command you typed. `lllm --help` lists
`shell` next to the core commands. Without AAAX, `lllm shell` prints
`lllm shell needs the aaax package: pip install aaax` and exits with
status 2. Every option is in the [CLI reference](api/cli.md).

## Check the install

```python title="check_install.py"
from fastapi.testclient import TestClient

from aaax import Strategy, create_strategy_app

client = TestClient(create_strategy_app(Strategy("hello")))
print(client.get("/health").json())
#> {'ok': True, 'strategy': 'hello'}
```

The examples in this guide call apps in the same process with FastAPI's
`TestClient`, which needs httpx: `pip install httpx`.

## Coming from `lllm.shell`

LLLM 0.3 shipped this code inside LLLM, as `lllm.shell`. In LLLM 0.4 that
module is a deprecated alias: importing it imports `aaax` and warns once,
and the old import paths keep working (`lllm.shell.server` is
`aaax.server`). Replace `from lllm.shell import ...` with
`from aaax import ...`; the names are the same.

`lllm shell` keeps working once AAAX is installed, and a folder's
`shell.py` still loads as a strategy file. Two things read differently:
events appended without a `source` say `aaax` instead of `lllm.shell`, and
the app reports AAAX's version.

## From source

```bash
git clone https://github.com/Productive-Superintelligence/aaax
cd aaax
pip install -e ".[dev,docs]"
pytest
```
