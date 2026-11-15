"""Package folders and response helpers shared by the test modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def error_detail(response) -> dict[str, Any]:
    """The ``error`` object of a services error envelope."""

    return response.json()["detail"]["error"]


def write_package(root: Path, name: str = "analysis-pack", *, channels=("events",)) -> Path:
    """A package with one ``echo`` tactic and log channels, in ``root``."""

    module = root / "demo_pkg"
    module.mkdir(parents=True)
    (module / "__init__.py").write_text("", encoding="utf-8")
    (module / "tactics.py").write_text(
        """
def echo(input_value, *, context=None):
    return {
        "echo": input_value,
        "context_type": type(context).__name__,
        "metadata": getattr(context, "metadata", context),
        "tactic_ref": getattr(context, "tactic_ref", None),
    }
""".lstrip(),
        encoding="utf-8",
    )
    sections = "".join(
        f'\n[channels.{channel}]\nform = "log"\ndescription = "The {channel} stream."\n'
        for channel in channels
    )
    (root / "lllm.toml").write_text(
        f"""
[package]
org = "demo"
name = "{name}"
version = "0.1.0"
kind = "app"
description = "Demo package."

[tactics.echo]
entry = "demo_pkg.tactics:echo"
description = "Echo tactic."
{sections}""".lstrip(),
        encoding="utf-8",
    )
    return root


def write_demo_package(root: Path) -> Path:
    """A package with a resource in every manifest section, in ``root``."""

    package_dir = root / "demo_pkg"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "schemas.py").write_text(
        """
class Record:
    pass
""".lstrip(),
        encoding="utf-8",
    )
    (package_dir / "tactics.py").write_text(
        """
def echo(input_value, *, context=None):
    metadata = getattr(context, "metadata", context or {})
    context_type = type(context).__name__ if context is not None else None
    return {
        "echo": input_value,
        "context_type": context_type,
        "metadata": metadata,
    }
""".lstrip(),
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Demo Package\n", encoding="utf-8")
    (root / "examples").mkdir()
    (root / "examples" / "first.py").write_text("print('demo')\n", encoding="utf-8")
    (root / "assets").mkdir()
    (root / "assets" / "logo.txt").write_text("AAAX\n", encoding="utf-8")
    (root / "lllm.toml").write_text(
        """
[package]
manifest_version = "0.1"
org = "demo"
name = "analysis-pack"
version = "0.1.0"
kind = "app"
primary = "runs.local"
description = "Demo package."

[card]
summary = "Demo analyst package."
tags = ["analysis", "demo"]
suggested_commands = ["aaax serve ."]

[config]
description = "Runtime defaults."
schema = { mode = "string" }
defaults = { mode = "demo" }

[schemas.record]
entry = "demo_pkg.schemas:Record"
description = "Record schema."

[tactics.echo]
entry = "demo_pkg.tactics:echo"
runtime = "python"
input = "schemas.record"
output = "schemas.record"
description = "Echo tactic."
examples = [{ input = { text = "hello" } }]

[channels.events]
form = "log"
description = "Event stream."

[snapshots.latest]
channel = "events"
description = "Latest event."

[services.api]
tactic = "echo"
transport = "fastapi"
description = "HTTP service."
subscribes = ["events"]
publishes = ["events"]

[runs.local]
tactics = ["echo"]
channels = ["events"]
services = ["api"]
snapshots = ["latest"]
description = "Local run."

[docs.readme]
path = "README.md"
title = "README"

[examples.first]
path = "examples/first.py"
command = "python examples/first.py"

[assets.logo]
path = "assets/logo.txt"
media_type = "text/plain"
""".lstrip(),
        encoding="utf-8",
    )
    return root
