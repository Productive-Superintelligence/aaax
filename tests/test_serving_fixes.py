"""Regression tests for the serving fixes found while the docs were rewritten.

Each section names the fix it covers (docs fixes 1-8). The fixes that need a
channel store are tested in test_channels.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from lllm import Tactic

from aaax import Strategy, create_strategy_app
from helpers import error_detail, write_package


class Echo(Tactic[Any, Any]):
    """Echo the input."""

    name = "echo"

    def _run(self, input_value, *, context=None):
        return input_value


class Broken(Tactic[Any, Any]):
    name = "broken"

    def _run(self, input_value, *, context=None):
        raise RuntimeError("tactic broke")


# Docs fix 1: tactic route replies and errors named the tactic, not the route.


def test_tactic_route_replies_and_errors_name_the_mounted_resource(tmp_path: Path):
    echo = Echo()
    strategy = Strategy("names").add_tactic(echo, name="renamed")
    strategy.add_tactic(Broken(), name="desk.broken")
    strategy.use_package(write_package(tmp_path / "pkg", channels=()), prefix="pkg")
    client = TestClient(create_strategy_app(strategy))

    for name in ("renamed", "pkg.echo"):
        reply = client.post(f"/tactics/{name}/run", json={"input": 1})
        assert reply.status_code == 200
        assert reply.json()["tactic"] == name
        assert client.get(f"/tactics/{name}/info").json()["name"] == name
        assert strategy.tactics()[name].tactic_name == name
    failed = client.post("/tactics/desk.broken/run", json={"input": 1})
    unsupported = client.post("/tactics/renamed/stream", json={"input": 1})
    assert failed.status_code == 500
    assert error_detail(failed)["tactic"] == "desk.broken"
    assert unsupported.status_code == 400
    assert error_detail(unsupported)["tactic"] == "renamed"
    # The tactic that was passed in keeps its own name.
    assert echo.tactic_name == "echo"


def test_a_tactic_keeps_its_name_when_lllm_cannot_carry_the_local_name():
    # AAAX names may hold ";", which LLLM tactic names may not.
    strategy = Strategy("names").add_tactic(Echo(), name="a;b")
    client = TestClient(create_strategy_app(strategy))

    reply = client.post("/tactics/a;b/run", json={"input": 1})

    assert reply.status_code == 200
    assert reply.json()["tactic"] == "echo"
