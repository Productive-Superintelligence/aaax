# Advanced Autonomous Agent Executor (AAAX)

<p align="center">
  <img src="assets/aaax-logo-text-black.png" alt="AAAX" width="420">
</p>

Advanced Autonomous Agent Executor (AAAX) is the strategy shell for
package-shaped agent systems, built on [LLLM](https://lllm.one/).
Documentation: [aaax.one](https://aaax.one/).

Use it to inspect an LLLM package, mount its tactics and channels, bind local
handlers, open a FastAPI surface, and hand that surface to a human, script,
coding agent, or another system. The feel is intentionally shell-like: name the
package, see the resources, run one command, and get a callable system.

AAAX is LLLM-centric. It depends on `lllm-core` for tactics, services, refs,
and packages: every mounted tactic is served as a full LLLM tactic service,
packages are `lllm.toml` packages from the LLLM hub, and installing AAAX adds
`lllm shell` to the `lllm` command. Channels come from
[SSSN](https://sssn.one/), the optional `channels` extra.

```bash
$ aaax inspect packages/analyst-pack
analyst-pack: Demo analyst package.
package analyst-pack lllm://demo/analyst-pack
tactic echo lllm://demo/analyst-pack/tactics/echo
channel events lllm://demo/analyst-pack/channels/events

$ aaax serve packages/analyst-pack --port 8400
Uvicorn running on http://127.0.0.1:8400
```

`lllm shell inspect` and `lllm shell serve` run the same commands.

AAAX does not replace LLLM, SSSN, Codex, Claude Code, schedulers, sandboxes, or
deployment platforms. It is the thin shell where those pieces are named,
mounted, served, and handed off.

## Install

```bash
pip install aaax                 # or: pip install "lllm-core[shell]"
pip install "aaax[channels]"     # with SSSN channel stores
```

For a reproducible install:

```bash
pip install aaax==0.3.0
```

## Mount An LLLM Package

If a folder contains `lllm.toml`, AAAX can serve it directly:

```bash
aaax serve packages/analyst-pack --port 8400
```

AAAX reads the manifest and mounts:

- package metadata and card hints;
- schemas, tactics, services, runs, and config;
- channels and snapshots;
- docs, examples, and assets.

Each tactic entrypoint loads as an LLLM tactic and gets the full tactic
service at `/tactics/{name}/`: `run`, `stream`, `info`, and custom endpoints.
Channels are backed by the strategy's SSSN store, `<package>/.lllm/network`
unless you pick another, which is created the first time the strategy is
served or a channel is used, and served at `/network/`. Services that point at
one tactic are invokable as resources.

```bash
curl -X POST http://127.0.0.1:8400/tactics/echo/run \
  -H 'content-type: application/json' \
  -d '{"input": {"text": "hello"}, "context": {"metadata": {"request": "demo"}}}'
```

Append and query channel events:

```bash
curl -X POST http://127.0.0.1:8400/channels/events/events \
  -H 'content-type: application/json' \
  -d '{"input": {"kind": "record", "payload": {"text": "hello"}}}'

curl 'http://127.0.0.1:8400/channels/events/events?limit=10'
```

Inspecting a package imports neither its code nor SSSN. Serving a package that
declares channels needs `aaax[channels]`; without it, `aaax serve` says what to
install.

## Write A Shell Script

For larger systems, write a `strategy.py`. A strategy is the shell script: it
mounts packages and LLLM tactics, assigns local names, and optionally defines
`/run`.

```python
from aaax import Strategy


def build_strategy() -> Strategy:
    shell = Strategy(
        "analyst-shell",
        description="Mount source channels and analyst tactics.",
    )
    shell.use_package("packages/source-channels", prefix="sources")
    shell.use_package("packages/analyst-tactics", prefix="analysts")

    @shell.runner
    def run(input_value, *, context=None):
        return {
            "input": input_value,
            "resources": [resource.ref for resource in shell.resources],
            "context": context or {},
        }

    return shell
```

```bash
aaax serve strategy.py --port 8400
```

## Surface

Useful endpoints:

- `GET /health`
- `GET /strategy`
- `GET /resources`
- `GET /packages`
- `GET /tactics`
- `GET /channels`
- `POST /run`
- `POST /resources/{name}/invoke`
- `GET /channels/{name}/events`
- `POST /channels/{name}/events`
- `/tactics/{name}/...`: the LLLM tactic service (`run`, `stream`, `info`)
- `/network/...`: the SSSN store API, when the strategy has a channel store

Errors come back in LLLM's services error envelope.

## Upgrading

AAAX 0.3 is the code LLLM 0.3 shipped as its shell module, back in its own
package and built on `lllm-core`. `CHANGELOG.md` lists what changed from AAAX
0.2: packages are `lllm.toml` packages with `lllm://` refs, tactics get the
full LLLM service, request context is a `CallContext`, channel stores live in
`.lllm/network`, and a strategy file named `aaax.py` should become
`strategy.py`.
