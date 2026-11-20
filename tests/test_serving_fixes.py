"""Regression tests for the serving fixes found while the docs were rewritten.

Each section names the fix it covers (docs fixes 1-8). The fixes that need a
channel store are tested in test_channels.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from lllm import Tactic
from lllm.services import create_service_app

from aaax import Strategy, StrategyResource, create_strategy_app
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


# Docs fix 2: a name under /tactics/ that no tactic is mounted under got
# Starlette's plain {"detail": "Not Found"}.


def test_an_unmounted_tactic_name_gets_lllms_tactic_not_found_envelope():
    strategy = Strategy("desk").add_tactic(Echo())
    strategy.tactic("review", ref="lllm://acme/desk/tactics/review")  # no handler
    client = TestClient(create_strategy_app(strategy))
    lllm_client = TestClient(create_service_app([Echo()]))

    for name in ("nope", "review"):
        expected = lllm_client.post(f"/tactics/{name}/run", json={"input": 1})
        for method, path in [
            ("POST", f"/tactics/{name}/run"),
            ("POST", f"/tactics/{name}/stream"),
            ("GET", f"/tactics/{name}/info"),
            ("DELETE", f"/tactics/{name}/custom/route"),
            ("POST", f"/tactics/{name}"),
        ]:
            response = client.request(method, path, json={"input": 1})
            assert response.status_code == expected.status_code == 404, path
            assert response.json() == expected.json(), path
    assert error_detail(expected) == {
        "type": "TacticNotFound",
        "message": "Tactic not found: review",
        "tactic": "review",
        "endpoint": None,
        "request_id": None,
        "metadata": {},
    }
    # Mounted tactics, their own 404s, and the resource list are unchanged.
    assert client.post("/tactics/echo/run", json={"input": 1}).status_code == 200
    assert client.get("/tactics/echo/nope").json() == {"detail": "Not Found"}
    assert [record["name"] for record in client.get("/tactics").json()] == [
        "echo",
        "review",
    ]


def test_a_not_found_name_lllm_errors_cannot_carry_still_gets_the_envelope():
    client = TestClient(create_strategy_app(Strategy("desk")))

    response = client.post("/tactics/a;b/run", json={"input": 1})

    assert response.status_code == 404
    assert error_detail(response)["type"] == "TacticNotFound"
    assert error_detail(response)["message"] == "Tactic not found: a;b"
    assert error_detail(response)["tactic"] is None


# Docs fix 3: a declared description did not reach /info, a handler's
# docstring did not reach the record, and a package tactic's /info ignored
# the manifest's description and examples.


def count_words(text: str) -> int:
    """Count the words in a ticket."""
    return len(text.split())


def test_a_declared_description_reaches_the_tactic_info():
    echo = Echo()
    strategy = Strategy("desk")
    strategy.tactic("words", handler=count_words, description="Count words.")
    strategy.add_tactic(echo, description="Repeat a ticket.")
    strategy.tactic("again", handler=Echo(), description="Repeat it again.")
    strategy.add_resource(
        StrategyResource(kind="tactic", name="long", description="Words."),
        handler=count_words,
    )
    client = TestClient(create_strategy_app(strategy))

    for name, description in [
        ("words", "Count words."),
        ("echo", "Repeat a ticket."),
        ("again", "Repeat it again."),
        ("long", "Words."),
    ]:
        info = client.get(f"/tactics/{name}/info").json()
        assert info["description"] == description
        assert strategy.tactics()[name].info().description == description
    assert echo.info().description == "Echo the input."


def test_a_handler_docstring_fills_the_record_when_nothing_is_declared():
    strategy = Strategy("desk").tactic("words", handler=count_words)
    strategy.tactic("echo", handler=Echo())
    strategy.tactic("bare", handler=lambda text: text)
    strategy.add_resource(StrategyResource(kind="tactic", name="long"), handler=count_words)
    strategy.add_tactic(Echo(), name="blank", description="")
    client = TestClient(create_strategy_app(strategy))

    records = {resource.name: resource.description for resource in strategy.resources}
    assert records == {
        "words": "Count the words in a ticket.",
        "echo": "Echo the input.",
        "bare": "",
        "long": "Count the words in a ticket.",
        "blank": "",  # add_tactic keeps a description given as ""
    }
    for name in ("words", "echo", "bare", "long"):
        info = client.get(f"/tactics/{name}/info").json()
        assert info["description"] == records[name]


def _described_package(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "docs_fix_described.py").write_text(
        """
from lllm.protocol import Tactic


def plain(input_value):
    return input_value


class Coded(Tactic):
    \"\"\"Described in code.\"\"\"

    def _run(self, input_value, *, context=None):
        return input_value


coded = Coded(name="coded", examples=[{"input": "from code"}])
""".lstrip(),
        encoding="utf-8",
    )
    (root / "lllm.toml").write_text(
        """
[package]
org = "demo"
name = "described"

[tactics.plain]
entry = "docs_fix_described:plain"
description = "Described in the manifest."
examples = [{ input = "hello" }]

[tactics.coded]
entry = "docs_fix_described:coded"
description = "Also described in the manifest."
examples = [{ input = "from the manifest" }]
""".lstrip(),
        encoding="utf-8",
    )
    return root


def test_a_package_tactic_info_uses_the_manifest_when_its_code_has_none(tmp_path: Path):
    package = _described_package(tmp_path / "described")
    strategy = Strategy("ops").use_package(package, prefix="d")
    client = TestClient(create_strategy_app(strategy))

    plain = client.get("/tactics/d.plain/info").json()
    coded = client.get("/tactics/d.coded/info").json()

    assert plain["description"] == "Described in the manifest."
    assert plain["examples"] == [{"input": "hello"}]
    # The code's own description and examples come first.
    assert coded["description"] == "Described in code."
    assert coded["examples"] == [{"input": "from code"}]
