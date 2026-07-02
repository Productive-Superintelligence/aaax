# Package Composition

AAAX composes packages by mounting manifest resources into a shell. A package
remains the unit of publication and discovery. A strategy is the shell session
that chooses local names, binds handlers, and serves endpoints.

```mermaid
flowchart TD
  A["psi.toml"] --> B["PsiHub manifest"]
  B --> C["mounted resources"]
  C --> D["Tactic handlers"]
  C --> E["Channel handlers"]
  C --> F["Docs, examples, assets"]
  D --> G["FastAPI endpoints"]
  E --> G
  F --> H["Agent or human context"]
```

## Direct Package Shell

`strategy_from_package(path)` creates one shell from one package:

```python
from aaax import strategy_from_package


shell = strategy_from_package("packages/analyst-pack")
```

The shell name defaults to `package.name`. Package card metadata is copied onto
the strategy metadata and package resource.

## Imported Packages

`Strategy.use_package(path)` mounts one package into an existing shell:

```python
from aaax import Strategy


shell = Strategy("analysis-shell")
shell.use_package("packages/sources", prefix="sources")
shell.use_package("packages/analysts", prefix="analysts")
```

Prefixes only affect local shell names. The original `psi://` refs stay in
the resource records.

## Binding

When `bind=True`, AAAX tries to bind:

- Python tactic entrypoints through LLLM's `Tactic` or `as_tactic` boundary.
- Package channels to a local SSSN `LocalStore`.
- Services that declare one `tactic` to the same tactic handler.

Use `bind=False` when you only want the mount table and metadata:

```python
shell.use_package("packages/remote-only", bind=False)
```

That is useful for remote packages, planning tools, and agent handoff contexts
where another process will resolve the actual service URLs.
