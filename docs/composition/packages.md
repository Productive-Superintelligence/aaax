# LLLM Packages

AAAX mounts LLLM packages: folders described by an `lllm.toml` manifest, the
format the [LLLM hub](https://lllm.one/packages/hub/) validates, publishes,
and serves. It can mount a package folder or a direct `lllm.toml` file:

```python
from aaax import load_strategy


shell = load_strategy("packages/analyst-pack")
shell = load_strategy("packages/analyst-pack/lllm.toml")
```

In a directory, the loader first looks for `strategy.py`, then `shell.py` (the
name LLLM 0.3's `lllm shell` used), and mounts the `lllm.toml` only when
neither exists. That keeps explicit strategy files in control when both exist.

A package fetched from the hub is an ordinary folder:

```bash
lllm hub get demo/analyst-pack --dest vendor
aaax serve vendor/analyst-pack --port 8400
```

## Imported Manifest Sections

Every manifest section becomes resources:

| Manifest section | Resource kind | Handler when bound |
| --- | --- | --- |
| `[package]` | `package` (named after the package) | |
| `[card]` | `card` in the package resource's metadata (and the strategy's, with `strategy_from_package`) | |
| `[config]` | `config` named `default` | |
| `[schemas.<name>]` | `schema` | |
| `[tactics.<name>]` | `tactic` | the imported entrypoint, as an LLLM tactic |
| `[channels.<name>]` | `channel` | append, query, and info on the strategy's store |
| `[snapshots.<name>]` | `snapshot` | |
| `[services.<name>]` | `service` | its `tactic`'s handler, when it names one |
| `[runs.<name>]`, `[docs.<name>]`, `[examples.<name>]`, `[assets.<name>]` | `run`, `doc`, `example`, `asset` | |

Resource refs are the package's `lllm://` refs, such as
`lllm://demo/analyst-pack/tactics/echo`, whatever local name the package is
mounted under.

## Tactic Entrypoints

AAAX imports the Python value named by `entry`:

```toml
[tactics.echo]
entry = "demo.tactics:echo"
runtime = "python"
```

and loads it with LLLM's `coerce_tactic`, the rule `lllm serve` uses:

- an LLLM `Tactic` instance is mounted, and a `Tactic` class that can be built
  without arguments is instantiated;
- a factory is called once, when the tactic loads: a callable that takes no
  parameters, or that can be called without arguments and is annotated to
  return a `Tactic`;
- an object with a `run` method is served through that method;
- any other callable is a handler, wrapped with `lllm.as_tactic` and called
  once per input.

Callers meet the same `CallContext` and validation boundary either way. A
package tactic that declares no `package_ref` reports its manifest ref in
`/tactics/{name}/info` and as the `tactic_ref` of the `CallContext` it
receives.

Packages load lazily: building or inspecting the strategy never imports
package code. Building the app, calling `strategy.tactics()`, or invoking the
resource does, and the code stays loaded, so give packages you mount together
distinct top-level module names: two packages that both ship a `helpers.py`
share one copy of it.

## Channel Stores

Package channels are backed by the strategy's channel store, an SSSN store
(install `aaax[channels]`). `store=` picks its folder for a strategy that has
no store yet:

```python
from aaax import Strategy


shell = Strategy("sources")
shell.use_package("packages/source", store=".lllm/source-store")
```

- A strategy has one store. The first package with channels gives the
  strategy its store, at `store=` or `<package>/.lllm/network`, unless it
  already has one. Later packages share it, and a later `store=` naming
  another folder raises `ValueError`.
- Package channels are created in the store under their resource names
  (`source.events`), so a prefix keeps two packages' channels apart. Existing
  channels are reused.
- The store folder and its channels are created on first use, when the app is
  built or a channel is used, never while building or inspecting the strategy.

## Package Cards

Cards are not execution code, but they matter. AAAX preserves card summaries,
tags, safety notes, latency notes, suggested commands, and metadata so future
agent handoff surfaces can inject useful package context without re-parsing the
manifest.
