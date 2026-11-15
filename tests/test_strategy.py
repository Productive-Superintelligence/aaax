"""Strategies, the loader, the CLI, and the app, without a channel store.

Nothing here needs sssn; channel stores are tested in test_channels.py.
"""

from __future__ import annotations

import asyncio
import builtins
import re
import sys
import types
import warnings
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aaax import Strategy, create_strategy_app, load_strategy
from aaax.cli import main
from helpers import write_demo_package


def test_strategy_app_runs_and_invokes_resources():
    strategy = Strategy("analyst-system", description="Fixture system.")
    strategy.channel(
        "events",
        ref="lllm://society/source-channels/channels/finance_ticks",
    )
    strategy.tactic(
        "finance_baseline",
        ref="lllm://society/analyst-tactics/tactics/finance_baseline",
        handler=lambda input_value, context=None: {
            "handled": input_value,
            "context": context or {},
        },
    )

    @strategy.runner
    def run(input_value, *, context=None):
        return {
            "input": input_value,
            "resource_count": len(strategy.resources),
            "context": context or {},
        }

    client = TestClient(create_strategy_app(strategy))

    assert client.get("/health").json() == {
        "ok": True,
        "strategy": "analyst-system",
    }
    assert client.get("/resources").json()[0]["kind"] == "channel"
    run_response = client.post(
        "/run",
        json={"input": {"task": "summarize"}, "context": {"request": "demo"}},
    )
    invoke_response = client.post(
        "/resources/finance_baseline/invoke",
        json={"input": {"records": []}},
    )

    assert run_response.status_code == 200
    assert run_response.json()["output"]["resource_count"] == 2
    assert invoke_response.status_code == 200
    # A tactic resource runs as /tactics/<name>/run runs it: with a CallContext.
    assert invoke_response.json()["output"]["handled"] == {"records": []}
    assert invoke_response.json()["output"]["context"]["metadata"] == {}
    assert invoke_response.json()["output"]["context"]["endpoint"] == "run"


def test_strategy_loader_from_directory(tmp_path: Path):
    strategy_file = tmp_path / "strategy.py"
    strategy_file.write_text(
        """
from aaax import Strategy


def build_strategy():
    strategy = Strategy("loaded")
    strategy.service("api", ref="lllm://demo/app/services/api")
    return strategy
""".lstrip(),
        encoding="utf-8",
    )

    strategy = load_strategy(tmp_path)

    assert strategy.name == "loaded"
    assert strategy.resources[0].kind == "service"


@pytest.mark.parametrize(
    ("files", "loaded"),
    [
        (["shell.py"], "shell"),  # the name LLLM 0.3's `lllm shell` loaded
        (["strategy.py", "shell.py"], "strategy"),
        (["aaax.py", "shell.py"], "shell"),
        (["strategy.py", "aaax.py", "shell.py"], "strategy"),
    ],
)
def test_strategy_files_load_before_the_package_manifest(tmp_path: Path, files, loaded):
    for name in files:
        (tmp_path / name).write_text(
            f"from aaax import Strategy\nstrategy = Strategy({name[:-3]!r})\n",
            encoding="utf-8",
        )
    (tmp_path / "lllm.toml").write_text('[package]\nname = "pkg"\n', encoding="utf-8")

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        assert load_strategy(tmp_path).name == loaded


def test_an_aaax_py_strategy_still_loads_with_a_warning_to_rename_it(tmp_path: Path):
    # AAAX 0.2 loaded aaax.py too, but in its folder that file shadows the
    # aaax package, so `lllm shell` and `python -m aaax` cannot import AAAX.
    (tmp_path / "aaax.py").write_text(
        "from aaax import Strategy\nstrategy = Strategy('legacy')\n", encoding="utf-8"
    )
    (tmp_path / "lllm.toml").write_text('[package]\nname = "pkg"\n', encoding="utf-8")

    for target in (tmp_path, tmp_path / "aaax.py"):
        with pytest.warns(FutureWarning, match=r"aaax\.py to strategy\.py: a file named"):
            assert load_strategy(target).name == "legacy"


def test_strategy_loader_names_what_a_directory_needs(tmp_path: Path):
    with pytest.raises(
        ValueError,
        match="strategy directory must contain strategy.py, shell.py, or lllm.toml",
    ):
        load_strategy(tmp_path)


def test_a_package_folder_and_its_lllm_toml_load_the_same_strategy(tmp_path: Path):
    package = write_demo_package(tmp_path / "analysis-pack")

    strategy = load_strategy(package)

    assert strategy.name == "analysis-pack"
    assert strategy.resources[0].ref == "lllm://demo/analysis-pack"
    assert load_strategy(package / "lllm.toml").info() == strategy.info()


def test_tactic_only_package_does_not_require_sssn(
    tmp_path: Path,
    monkeypatch,
):
    package = _write_tactic_only_package(tmp_path / "standalone-pack")
    real_import = builtins.__import__

    def blocked_optional_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name.split(".", 1)[0] == "sssn":
            raise ImportError(f"blocked optional integration: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_optional_import)

    strategy = load_strategy(package)
    client = TestClient(create_strategy_app(strategy))
    response = client.post(
        "/tactics/echo/run",
        json={
            "input": {"text": "hello"},
            "context": {"metadata": {"request": "standalone"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["output"] == {
        "echo": {"text": "hello"},
        "context_type": "CallContext",
        "metadata": {"request": "standalone"},
    }


def test_cli_inspect_prints_strategy(tmp_path: Path, capsys):
    strategy_file = tmp_path / "strategy.py"
    strategy_file.write_text(
        """
from aaax import Strategy

strategy = Strategy("cli-demo")
strategy.tactic("review", ref="lllm://demo/pkg/tactics/review")
""".lstrip(),
        encoding="utf-8",
    )

    assert main(["inspect", str(strategy_file)]) == 0
    out = capsys.readouterr().out

    assert "cli-demo" in out
    assert "tactic review lllm://demo/pkg/tactics/review" in out


def test_cli_inspect_prints_package_resources(tmp_path: Path, capsys):
    package = write_demo_package(tmp_path / "analysis-pack")

    assert main(["inspect", str(package)]) == 0
    out = capsys.readouterr().out

    assert "analysis-pack" in out
    assert "tactic echo lllm://demo/analysis-pack/tactics/echo" in out
    assert "doc readme lllm://demo/analysis-pack/docs/readme" in out


def test_default_runner_exposes_strategy_pack():
    strategy = Strategy("empty")
    strategy.package("analysts", ref="lllm://society/analyst-tactics")

    client = TestClient(create_strategy_app(strategy))
    response = client.post("/run", json={"input": {"ok": True}})

    assert response.status_code == 200
    assert response.json()["output"]["strategy"] == "empty"
    assert response.json()["output"]["resources"][0]["kind"] == "package"


def test_mounted_tactics_get_the_full_service_surface():
    from pydantic import BaseModel

    from lllm import Tactic

    class Text(BaseModel):
        text: str

    class Shout(Tactic[Text, Text]):
        name = "shout"
        input_type = Text
        output_type = Text

        def _run(self, input_value, *, context=None):
            return Text(text=input_value.text.upper())

    strategy = Strategy("served").add_tactic(Shout())
    strategy.tactic("plain", handler=lambda input_value: {"seen": input_value})
    client = TestClient(create_strategy_app(strategy))

    assert [r["name"] for r in client.get("/tactics").json()] == ["shout", "plain"]
    assert client.get("/tactics/shout/info").json()["name"] == "shout"
    assert client.post("/tactics/shout/run", json={"input": {"text": "hi"}}).json()[
        "output"
    ] == {"text": "HI"}
    # Streaming errors come back in the services error envelope.
    stream = client.post("/tactics/shout/stream", json={"input": {"text": "go"}})
    assert stream.status_code == 400
    assert stream.json()["detail"]["error"]["type"] == "TacticUnsupportedError"
    assert client.get("/tactics/shout/info").json()["description"] == ""
    assert client.post("/tactics/plain/run", json={"input": 3}).json()["output"] == {
        "seen": 3
    }


# Without sssn, everything but the channel store works, and the store says
# what to install.


def _without_sssn(monkeypatch) -> None:
    """Import sssn as if it were not installed."""

    real_import = builtins.__import__

    def import_without_sssn(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name.split(".", 1)[0] == "sssn":
            raise ModuleNotFoundError("No module named 'sssn'", name="sssn")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_sssn)


def test_a_package_with_channels_needs_sssn_only_for_its_store(
    tmp_path: Path, monkeypatch, capsys
):
    package = write_demo_package(tmp_path / "analysis-pack")
    _without_sssn(monkeypatch)
    strategy = load_strategy(package)
    missing = "Channel stores need the sssn package: pip install sssn"

    assert main(["inspect", str(package)]) == 0
    assert "channel events lllm://demo/analysis-pack/channels/events" in (
        capsys.readouterr().out
    )
    echoed = asyncio.run(strategy.invoke_resource("echo", {"text": "hi"}))
    assert echoed["echo"] == {"text": "hi"}
    with pytest.raises(ImportError, match=missing):
        asyncio.run(strategy.invoke_resource("events", {"op": "append", "payload": 1}))
    with pytest.raises(ImportError, match=missing):
        create_strategy_app(strategy)
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: pytest.fail("serve started"))
    with pytest.raises(SystemExit) as exit_info:
        main(["serve", str(package)])
    assert exit_info.value.code == 2
    assert f"error: {missing}" in capsys.readouterr().err
    assert not (package / ".lllm").exists()


# An sssn older than 0.2 is not used: the store says to upgrade it.

UPGRADE_SSSN = "aaax needs sssn>=0.2: pip install -U 'aaax[channels]'"


def _with_old_sssn(monkeypatch, version: str | None = "0.1.1") -> None:
    """Import sssn as if an sssn older than 0.2 were installed."""

    old = types.ModuleType("sssn")
    if version is not None:  # sssn 0.0 had no __version__
        old.__version__ = version
    monkeypatch.setitem(sys.modules, "sssn", old)


@pytest.mark.parametrize("version", ["0.1.1", None])
def test_an_sssn_older_than_0_2_says_to_upgrade_it(
    tmp_path: Path, monkeypatch, capsys, version
):
    package = write_demo_package(tmp_path / "analysis-pack")
    _with_old_sssn(monkeypatch, version)
    strategy = load_strategy(package)

    with pytest.raises(ImportError, match=re.escape(UPGRADE_SSSN)):
        asyncio.run(strategy.invoke_resource("events", {"op": "append", "payload": 1}))
    with pytest.raises(ImportError, match=re.escape(UPGRADE_SSSN)):
        create_strategy_app(strategy)
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: pytest.fail("serve started"))
    with pytest.raises(SystemExit) as exit_info:
        main(["serve", str(package)])
    assert exit_info.value.code == 2
    assert f"error: {UPGRADE_SSSN}" in capsys.readouterr().err
    assert not (package / ".lllm").exists()


def test_an_old_sssn_imported_elsewhere_leaves_error_codes_alone(monkeypatch):
    # sssn 0.1 had neither NetworkError nor RemoteStoreError to look up.
    _with_old_sssn(monkeypatch)
    for name in ("sssn.core.errors", "sssn.client.http"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))

    def check(input_value=None):
        raise ValueError("bad input")

    client = TestClient(create_strategy_app(Strategy("plain").service("check", handler=check)))
    response = client.post("/resources/check/invoke", json={"input": 1})

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["message"] == "bad input"


class _ChannelExists(Exception):
    error_type = "ChannelExistsError"


class _MemoryStore:
    """A store that is not an sssn store: channels and events in memory."""

    def __init__(self):
        self.channels: dict[str, dict] = {}
        self.events: list[dict] = []

    def create_channel(self, channel):
        if channel["name"] in self.channels:
            raise _ChannelExists(channel["name"])
        self.channels[channel["name"]] = dict(channel)
        return self.channels[channel["name"]]

    def get_channel(self, name):
        return self.channels[name]

    def append_event(self, event):
        self.events.append(dict(event))
        return self.events[-1]

    def query_events(self, name, *, after_cursor=0, limit=100, kind=None):
        events = [event for event in self.events if event["channel"] == name]
        return events[after_cursor:][:limit]


def test_an_attached_store_that_is_not_an_sssn_store_needs_no_sssn(monkeypatch):
    store = _MemoryStore()
    store.create_channel({"name": "log", "description": "Made earlier."})
    _without_sssn(monkeypatch)
    strategy = Strategy("memory").attach_store(store)
    strategy.channel("log").channel("notes")

    appended = asyncio.run(strategy.invoke_resource("log", {"op": "append", "payload": 1}))
    queried = asyncio.run(strategy.invoke_resource("log", {"op": "query"}))

    assert appended["source"] == "aaax"
    assert [event["payload"] for event in queried] == [1]
    assert store.channels["log"]["description"] == "Made earlier."
    assert sorted(store.channels) == ["log", "notes"]


def test_serving_a_store_that_is_not_an_sssn_store_needs_no_sssn(monkeypatch):
    store = _MemoryStore()
    _without_sssn(monkeypatch)
    strategy = Strategy("memory").channel("log").attach_store(store)

    client = TestClient(create_strategy_app(strategy))

    assert sorted(store.channels) == ["log"]  # building the app opened the store
    appended = client.post("/channels/log/events", json={"input": {"payload": 1}})
    queried = client.get("/channels/log/events")
    assert appended.status_code == 200
    assert [event["payload"] for event in queried.json()["output"]] == [1]
    # sssn's store API serves sssn stores only.
    assert client.get("/network/channels").status_code == 404


def _write_tactic_only_package(root: Path) -> Path:
    package_dir = root / "demo_pkg"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
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
    (root / "lllm.toml").write_text(
        """
[package]
manifest_version = "0.1"
org = "demo"
name = "standalone-pack"
version = "0.1.0"
kind = "app"
description = "Tactic-only demo package."

[tactics.echo]
entry = "demo_pkg.tactics:echo"
runtime = "python"
description = "Echo tactic."

[runs.local]
tactics = ["echo"]
description = "Local run."
""".lstrip(),
        encoding="utf-8",
    )
    return root
