# CLI

The `aaax` command is the shell entrypoint. It loads, inspects, and serves
packages or strategy files. Installing AAAX also adds it to the LLLM command as
`lllm shell`, and `python -m aaax` runs it too; all three are the same CLI, and
usage and error messages name the command you typed.

```bash
aaax inspect TARGET [--json]
aaax serve TARGET [--host 127.0.0.1] [--port 8400] [--log-level info]
aaax launch TARGET [...]          # an alias for serve
aaax --version                    # aaax 0.3.0
lllm shell inspect TARGET         # the same commands through lllm
```

## Inspect

```bash
aaax inspect TARGET
aaax inspect TARGET --json
```

`TARGET` can be a strategy file, a package folder, a direct `lllm.toml`, a
directory with `strategy.py` or `shell.py`, or a `module:attribute` value.
Don't name a strategy file `aaax.py`: run in its folder, `lllm shell` and
`python -m aaax` import that file in place of the `aaax` package and fail.

Text output lists resource kind, local name, and ref or entrypoint:

```text
analysis-pack: Demo package.
package analysis-pack lllm://demo/analysis-pack
tactic echo lllm://demo/analysis-pack/tactics/echo
channel events lllm://demo/analysis-pack/channels/events
```

`--json` prints the full `StrategyInfo`. Inspecting a package neither imports
its code nor creates its channel store, and needs no SSSN.

## Serve

```bash
aaax serve TARGET --host 127.0.0.1 --port 8400 --log-level info
```

`serve` builds the strategy app and runs it with Uvicorn.

Validation:

- host must be a host name or address, not a URL;
- port must be between `1` and `65535`;
- log level must be one of `critical`, `debug`, `error`, `info`, `trace`, or
  `warning`.

A target that does not load, and a strategy with channels when SSSN is not
installed, are usage errors (exit status `2`):

```text
aaax: error: Channel stores need the sssn package: pip install sssn
```

## Launch

```bash
aaax launch TARGET --port 8400
```

`launch` is an alias for `serve` in the current public surface. It exists so the
command family can grow without changing the shell habit: inspect, mount, serve.

## Through LLLM

```bash
lllm shell inspect TARGET
lllm shell serve TARGET --port 8400
lllm --help                       # lists shell next to the core commands
```

AAAX registers `lllm shell` with the `lllm.commands` entry point
`shell = "aaax.cli"`. Without AAAX installed, `lllm shell` prints
`lllm shell needs the aaax package: pip install aaax` and exits with status
`2`.
