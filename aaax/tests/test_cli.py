from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from aaax.cli import main


def _write_config(path: Path) -> None:
    path.write_text(
        """
[aaax]
id = "aaax-cli-test"
name = "AAAX CLI Test"
policy = "default"

[aaax.libos]
name = "lllm"
strict_boot = true
discover_shared_packages = false

[aaax.network]
publish = false
host = "127.0.0.1"
port = 8100

[[aaax.modules]]
id = "example-agent"
framework = "custom"
channels = []
executors = []
remote_channels = []
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_launch_once_prints_kernel_snapshot(tmp_path: Path) -> None:
    config_path = tmp_path / "aaax.toml"
    _write_config(config_path)

    runner = CliRunner()
    result = runner.invoke(main, ["launch", str(config_path), "--once"])

    assert result.exit_code == 0
    assert "kernel_id=aaax-cli-test" in result.output
    assert "docked_systems=['example-agent']" in result.output
    assert "aaax.capability-request" in result.output


def test_launch_once_cannot_be_combined_with_publish(tmp_path: Path) -> None:
    config_path = tmp_path / "aaax.toml"
    _write_config(config_path)

    runner = CliRunner()
    result = runner.invoke(main, ["launch", str(config_path), "--once", "--publish"])

    assert result.exit_code != 0
    assert "--once cannot be combined with --publish" in result.output
