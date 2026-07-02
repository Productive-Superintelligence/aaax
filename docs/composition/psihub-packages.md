# PsiHub Packages

AAAX can mount a package folder or a direct `psi.toml` file:

```python
from aaax import load_strategy


shell = load_strategy("packages/analyst-pack")
shell = load_strategy("packages/analyst-pack/psi.toml")
```

The loader recognizes a package after it checks for `strategy.py` and `aaax.py`
in a directory. That keeps explicit strategy files in control when both exist.

## Imported Manifest Sections

AAAX imports:

- `[package]` as a package resource and shell metadata.
- `[card]` into package and strategy metadata.
- `[config]` as `config.default`.
- `[schemas.*]` as schema resources.
- `[tactics.*]` as tactic resources and local handlers when bound.
- `[channels.*]` as channel resources and local SSSN handlers when bound.
- `[snapshots.*]` as snapshot resources.
- `[services.*]` as service resources.
- `[runs.*]` as run resources.
- `[docs.*]`, `[examples.*]`, and `[assets.*]` as context resources.

## Tactic Entrypoints

AAAX imports the Python value named by `entry`:

```toml
[tactics.echo]
entry = "demo.tactics:echo"
runtime = "python"
```

It supports:

- LLLM `Tactic` subclasses;
- LLLM `Tactic` instances;
- normal Python callables;
- zero-argument factories that return one of the above;
- objects with a `run` method.

When LLLM is installed, normal callables and `run` methods are wrapped through
`as_tactic`, so callers meet the same `CallContext` and validation boundary.

## Channel Stores

When a package has channels and `bind=True`, AAAX creates a local SSSN store:

```python
shell.use_package("packages/source", store=".aaax/source-store")
```

If no store path is provided, the package folder gets a `.sssn` store. Existing
channels are reused.

## Package Cards

Cards are not execution code, but they matter. AAAX preserves card summaries,
tags, safety notes, latency notes, suggested commands, and metadata so future
agent handoff surfaces can inject useful package context without re-parsing the
manifest.
