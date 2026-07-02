# AAAX

AAAX is the PSI shell for package-shaped agent systems.

Use it to inspect a PsiHub package, mount its tactics and channels, bind local
handlers, open a small FastAPI surface, and hand that surface to a human,
script, or coding agent. The feel is intentionally shell-like: name the package,
see the resources, run one command, and get a callable system.

```bash
$ aaax inspect packages/analyst-pack
analysis-pack: Demo analyst package.
package analysis-pack psi://demo/analysis-pack
tactic echo psi://demo/analysis-pack/tactics/echo
channel events psi://demo/analysis-pack/channels/events

$ aaax serve packages/analyst-pack --port 8400
Uvicorn running on http://127.0.0.1:8400
```

AAAX does not replace LLLM, SSSN, PsiHub, Codex, Claude Code, schedulers,
sandboxes, or deployment platforms. It is the thin shell where those pieces are
named, mounted, served, and handed off.

## Install

```bash
python -m pip install aaax
```

For a reproducible install:

```bash
python -m pip install aaax==0.2.1
```

For local PSI composition:

```bash
python -m pip install "aaax[integrations]" lllm-core sssn psihub
```

## Mount A PsiHub Package

If a folder contains `psi.toml`, AAAX can serve it directly:

```bash
aaax serve packages/analyst-pack --port 8400
```

AAAX reads the manifest and mounts:

- package metadata and card hints;
- schemas, tactics, services, runs, and config;
- SSSN channels and snapshots;
- docs, examples, and assets.

Python tactic entrypoints become `/tactics/{name}/run`. Channels are backed by a
local SSSN store and exposed through `/channels/{name}/events`. Services that
point at one tactic are invokable as resources.

```bash
curl -X POST http://127.0.0.1:8400/tactics/finance_baseline/run \
  -H 'content-type: application/json' \
  -d '{"input": {"records": []}, "context": {"request": "demo"}}'
```

Append and query channel events:

```bash
curl -X POST http://127.0.0.1:8400/channels/events/events \
  -H 'content-type: application/json' \
  -d '{"input": {"kind": "record", "payload": {"text": "hello"}}}'

curl http://127.0.0.1:8400/channels/events/events?limit=10
```

## Write A Shell Script

For larger systems, write a `strategy.py`. A strategy is the shell script: it
mounts packages, assigns local names, and optionally defines `/run`.

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
- `POST /tactics/{name}/run`
- `GET /channels`
- `POST /channels/{name}/events`
- `GET /channels/{name}/events`
- `POST /run`
- `POST /resources/{name}/invoke`
