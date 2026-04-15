# Minimal Kernel

This is the smallest AAAX example in the repo.

It gives you two entry points:

- a one-shot Python script that boots the kernel, prints the channel surface, and exits
- the AAAX CLI, either in one-shot inspection mode or as the long-running runtime loop

## Files

- `aaax.toml` — minimal AAAX config
- `run_once.py` — bootstrap once, inspect the kernel, and exit

## Run Once

From the repo root:

```bash
python examples/minimal-kernel/run_once.py
```

This script boots the kernel, starts the owned channels, prints the governance channel IDs, runs one kernel step, and exits.

## Enter the CLI

AAAX does not have an interactive shell yet. The CLI entry point is the `aaax` command:

```bash
aaax --help
python -m aaax --help
```

To run this example through the CLI:

```bash
aaax launch examples/minimal-kernel/aaax.toml --once
```

or:

```bash
python -m aaax launch examples/minimal-kernel/aaax.toml --once
```

That prints the kernel snapshot and exits.

If you want the long-running runtime loop instead:

```bash
python -m aaax launch examples/minimal-kernel/aaax.toml
```

That command keeps the AAAX runtime alive and is mostly silent after startup. Stop it with `Ctrl+C`.
