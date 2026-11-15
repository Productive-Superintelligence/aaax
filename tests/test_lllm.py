"""AAAX plugs into LLLM: `lllm shell`, the aaax command, and the old lllm.shell path."""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import lllm.cli

import aaax
import aaax.cli
from aaax import Strategy, create_strategy_app

ROOT = Path(__file__).resolve().parents[1]


def test_aaax_registers_the_lllm_shell_command():
    points = [point for point in entry_points(group="lllm.commands") if point.name == "shell"]

    assert [point.value for point in points] == ["aaax.cli"]
    assert points[0].load() is aaax.cli


def test_lllm_shell_runs_the_aaax_cli(tmp_path, capsys):
    (tmp_path / "strategy.py").write_text(
        "from aaax import Strategy\n"
        "strategy = Strategy('desk', description='Triage support messages.')\n"
        "strategy.tactic('triage', ref='lllm://demo/desk/tactics/triage')\n",
        encoding="utf-8",
    )

    assert lllm.cli.main(["shell", "inspect", str(tmp_path)]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "desk: Triage support messages.",
        "tactic triage lllm://demo/desk/tactics/triage",
    ]


def test_lllm_help_lists_the_shell_command(capsys):
    with pytest.raises(SystemExit) as exc:
        lllm.cli.main(["--help"])

    assert exc.value.code == 0
    assert re.search(r"^\s+shell\s+\S", capsys.readouterr().out, re.M)


@pytest.mark.parametrize(
    ("argv", "usage"),
    [
        (["/venv/bin/aaax", "--help"], "usage: aaax [-h] [--version]"),
        (["/venv/bin/lllm", "shell", "--help"], "usage: lllm shell [-h] [--version]"),
    ],
)
def test_help_names_the_command_that_ran(monkeypatch, capsys, argv, usage):
    monkeypatch.setattr(sys, "argv", argv)
    command = aaax.cli.main if Path(argv[0]).name == "aaax" else lllm.cli.main

    with pytest.raises(SystemExit) as exc:
        command(argv[1:])

    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith(usage)


def test_errors_name_the_command_that_ran(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["/venv/bin/lllm", "shell", "inspect", str(tmp_path)])

    with pytest.raises(SystemExit) as exc:
        lllm.cli.main(["shell", "inspect", str(tmp_path)])

    assert exc.value.code == 2
    assert "lllm shell: error: strategy directory must contain" in capsys.readouterr().err


def test_every_version_is_the_aaax_version(capsys):
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    with pytest.raises(SystemExit):
        aaax.cli.main(["--version"])
    openapi = TestClient(create_strategy_app(Strategy("v"))).get("/openapi.json").json()

    assert re.search(r'^version = "(.+)"$', pyproject, re.M).group(1) == aaax.__version__
    assert capsys.readouterr().out == f"aaax {aaax.__version__}\n"
    assert openapi["info"]["version"] == aaax.__version__


def console_script(name):
    script = shutil.which(name, path=os.path.dirname(sys.executable))
    if script is None:
        pytest.skip(f"the {name} console script is not installed next to {sys.executable}")
    return script


@pytest.mark.parametrize("command", [["aaax", "--help"], ["lllm", "shell", "--help"]])
def test_console_scripts_show_help(command):
    result = subprocess.run(
        [console_script(command[0]), *command[1:]], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(f"usage: {' '.join(command[:-1])} ")


def test_python_m_aaax_runs_the_cli():
    result = subprocess.run(
        [sys.executable, "-m", "aaax", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("usage: aaax ")


DESK_STRATEGY = "from aaax import Strategy\nstrategy = Strategy('desk', description='Triage.')\n"


@pytest.mark.parametrize("name", ["strategy.py", "shell.py"])
@pytest.mark.parametrize("command", [["aaax"], ["lllm", "shell"], ["python", "-m", "aaax"]])
def test_every_command_inspects_a_strategy_in_the_working_directory(tmp_path, command, name):
    # `lllm shell` and `python -m aaax` put the working directory on sys.path
    # before they import aaax.
    (tmp_path / name).write_text(DESK_STRATEGY, encoding="utf-8")
    program = sys.executable if command[0] == "python" else console_script(command[0])

    result = subprocess.run(
        [program, *command[1:], "inspect", "."],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "desk: Triage.\n"


def test_aaax_inspects_an_aaax_py_folder_and_says_to_rename_the_file(tmp_path):
    (tmp_path / "aaax.py").write_text(DESK_STRATEGY, encoding="utf-8")

    result = subprocess.run(
        [console_script("aaax"), "inspect", "."],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "desk: Triage.\n"
    assert "FutureWarning: rename aaax.py to strategy.py" in result.stderr


@pytest.mark.xfail(
    reason=(
        "lllm.cli puts the working directory on sys.path before it imports "
        "aaax.cli, so the folder's aaax.py is imported as the aaax package"
    ),
    raises=AssertionError,
)
def test_lllm_shell_inspects_an_aaax_py_folder(tmp_path):
    (tmp_path / "aaax.py").write_text(DESK_STRATEGY, encoding="utf-8")

    result = subprocess.run(
        [console_script("lllm"), "shell", "inspect", "."],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "desk: Triage.\n"


def test_the_deprecated_lllm_shell_path_reaches_aaax():
    # LLLM 0.4 keeps lllm.shell as an alias of aaax for code written against
    # LLLM 0.3; it relies on aaax keeping that module layout.
    if importlib.util.find_spec("lllm.shell") is None:
        pytest.skip("this lllm has no lllm.shell alias")
    code = (
        "import warnings\n"
        "with warnings.catch_warnings(record=True) as caught:\n"
        "    warnings.simplefilter('always')\n"
        "    import lllm.shell\n"
        "import aaax\n"
        "from lllm.shell.server import create_strategy_app\n"
        "from lllm.shell.strategy import StrategyStore\n"
        "assert lllm.shell.Strategy is aaax.Strategy\n"
        "assert create_strategy_app is aaax.server.create_strategy_app\n"
        "assert StrategyStore is aaax.strategy.StrategyStore\n"
        "print(caught[0].category.__name__, caught[0].message)\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("DeprecationWarning")
    assert "import aaax" in result.stdout
