# CLI

The `aaax` command loads, inspects, and serves packages and strategy
files. Installing AAAX also adds it to the LLLM command as `lllm shell`,
and `python -m aaax` runs it too; all three are the same CLI, and usage and
error messages name the command you typed.
[Serving](../serving.md#serve-from-the-command-line) shows it in use.

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

`TARGET` can be:

- a Python file that defines `build_strategy()` or `strategy`;
- a directory, which loads its `strategy.py`, else its `shell.py`, else
  the package in its `lllm.toml`;
- an `lllm.toml` file, loaded as a strategy named after the package;
- a `module:attribute` value, imported from the working directory: a
  `Strategy`, or a function without parameters that returns one.

Don't name a strategy file `aaax.py`: run in its folder, `lllm shell` and
`python -m aaax` import that file in place of the `aaax` package and fail.
`aaax` itself still loads one, with a `FutureWarning` to rename it.

Text output lists resource kind, local name, and ref or entrypoint:

```text
analysis-pack: Demo package.
package analysis-pack lllm://demo/analysis-pack
tactic echo lllm://demo/analysis-pack/tactics/echo
channel events lllm://demo/analysis-pack/channels/events
```

`--json` prints the full `StrategyInfo`, with sorted keys. Inspecting a
package neither imports its code nor creates its channel store, and needs
no SSSN.

## Serve

```bash
aaax serve TARGET --host 127.0.0.1 --port 8400 --log-level info
```

`serve` builds the strategy app and runs it with Uvicorn.

Validation:

- host must be a host name or address, not a URL;
- port must be between `1` and `65535`;
- log level must be one of `critical`, `debug`, `error`, `info`, `trace`, or
  `warning`, in any case.

A target that does not load, and a strategy whose channel store is an SSSN
store (any package with channels, or an attached `LocalStore`) when SSSN is
not installed or is older than 0.2, are usage errors (exit status `2`):

```text
aaax: error: Channel stores need the sssn package: pip install sssn
aaax: error: aaax needs sssn>=0.2: pip install -U 'aaax[channels]'
```

## Launch

```bash
aaax launch TARGET --port 8400
```

`launch` is an alias for `serve`, with the same options and defaults.

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
