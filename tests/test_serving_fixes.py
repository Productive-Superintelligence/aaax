"""Regression tests for the serving fixes found while the docs were rewritten.

Each section names the fix it covers (docs fixes 1-8). The fixes that need a
channel store are tested in test_channels.py.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import lllm.cli
import lllm.credentials
from lllm import Tactic
from lllm.services import create_service_app

from aaax import Strategy, StrategyResource, create_strategy_app
from aaax.cli import main
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


# Docs fix 4: the strategy's own routes ignored unknown body keys, ran with
# the input None when "input" was missing, and did not take "task", unlike
# LLLM's tactic routes.

ENVELOPE_BODIES = [
    {"input": 1},
    {"task": 2},
    {"input": None, "task": 3},
    {"input": 4, "task": 5},
    {"input": 6, "context": {"metadata": {"user": "ada"}}},
    {"text": "not an envelope"},
    {"input": 7, "extra": 8},
    {"context": {"metadata": {}}},
    {},
    "text",
    42,
    [1, 2],
    None,  # no body at all
]


def test_strategy_routes_read_a_body_as_lllms_tactic_routes_do():
    strategy = Strategy("desk").add_tactic(Echo())
    strategy.service("svc", handler=lambda value: value)
    strategy.runner(lambda value: value)
    client = TestClient(create_strategy_app(strategy))

    for body in ENVELOPE_BODIES:
        expected = client.post("/tactics/echo/run", json=body)
        assert expected.status_code == 200, body
        for route in ("/run", "/resources/svc/invoke", "/resources/echo/invoke"):
            response = client.post(route, json=body)
            assert response.status_code == 200, (route, body)
            assert response.json()["output"] == expected.json()["output"], (route, body)
    text = {"content": "plain words", "headers": {"content-type": "text/plain"}}
    assert client.post("/tactics/echo/run", **text).json()["output"] == "plain words"
    assert client.post("/run", **text).json()["output"] == "plain words"


def test_an_envelope_passes_its_context_and_a_bad_context_is_a_400():
    strategy = Strategy("desk")
    strategy.service("ctx", handler=lambda value, context=None: [value, context])
    client = TestClient(create_strategy_app(strategy))

    body = {"task": "refund", "context": {"user": "ada"}}
    output = client.post("/resources/ctx/invoke", json=body).json()["output"]
    bad = client.post("/resources/ctx/invoke", json={"input": 1, "context": "nope"})

    assert output == ["refund", {"user": "ada"}]
    assert bad.status_code == 400
    assert error_detail(bad)["type"] == "SchemaError"
    assert error_detail(bad)["message"] == "context: Input should be a valid dictionary"
    assert error_detail(bad)["endpoint"] is None


def test_a_channel_append_takes_the_event_fields_as_the_body_too():
    seen = []

    def feed(value=None, *, context=None):
        seen.append(value)
        return value

    client = TestClient(create_strategy_app(Strategy("srv").channel("feed", handler=feed)))

    raw = client.post("/channels/feed/events", json={"payload": 1, "kind": "note"})
    wrapped = client.post("/channels/feed/events", json={"input": {"payload": 2}})
    text = client.post("/channels/feed/events", json="just text")

    assert raw.status_code == wrapped.status_code == 200
    assert seen == [
        {"payload": 1, "kind": "note", "op": "append"},
        {"payload": 2, "op": "append"},
    ]
    assert text.status_code == 400
    assert error_detail(text)["message"] == "input must be an object with the event fields"


# Docs fix 5: aaax serve and lllm shell serve did not check a package's
# [requirements.api_keys], and read keys from the environment only.

KEY = "DOCS_FIX_API_KEY"
MISSING_KEY = f"missing required API key(s):\n- {KEY} - Model access for the demo."


def _keyed_package(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "docs_fix_keyed.py").write_text("def echo(value):\n    return value\n")
    (root / "lllm.toml").write_text(
        f"""
[package]
org = "demo"
name = "keyed"

[tactics.echo]
entry = "docs_fix_keyed:echo"

[requirements.api_keys]
{KEY} = "Model access for the demo."
""".lstrip(),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def serve_here(tmp_path: Path, monkeypatch):
    """Serve from ``tmp_path`` without the key, a keyring, or a server.

    Returns the list of apps ``uvicorn.run`` was called with.
    """

    # setenv before delenv, so the key the command loads is removed afterwards.
    monkeypatch.setenv(KEY, "placeholder")
    monkeypatch.delenv(KEY)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(lllm.credentials, "keyring_get", lambda name: None)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    served: list[Any] = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: served.append(app))
    return served


def _serve_error(capsys, argv: list[str], command=main) -> str:
    with pytest.raises(SystemExit) as exit_info:
        command(argv)
    assert exit_info.value.code == 2
    return capsys.readouterr().err


def test_serving_a_package_checks_its_api_keys(tmp_path: Path, serve_here, capsys):
    _keyed_package(tmp_path / "keyed")

    for command in (["serve", "keyed"], ["launch", "keyed/lllm.toml"]):
        err = _serve_error(capsys, command)
        assert MISSING_KEY in err
        assert "Run `lllm setup keyed` or set the missing names" in err
    assert serve_here == []
    assert main(["serve", "keyed", "--skip-key-check"]) == 0
    assert len(serve_here) == 1


def test_serving_a_strategy_file_checks_the_keys_of_its_packages(
    tmp_path: Path, serve_here, capsys
):
    package = _keyed_package(tmp_path / "vendor" / "keyed")
    (tmp_path / "strategy.py").write_text(
        "from aaax import Strategy\n"
        "strategy = Strategy('ops')\n"
        f"strategy.use_package({str(package)!r}, prefix='k')\n"
        f"strategy.use_package({str(package)!r}, prefix='ref', bind=False)\n",
        encoding="utf-8",
    )

    (tmp_path / "reference.py").write_text(
        "from aaax import Strategy\n"
        "strategy = Strategy('ref')\n"
        f"strategy.use_package({str(package)!r}, bind=False)\n",
        encoding="utf-8",
    )

    err = _serve_error(capsys, ["serve", "strategy.py"])

    assert MISSING_KEY in err
    assert "Run `lllm setup vendor/keyed` or set" in err
    assert serve_here == []
    # A package mounted for reference runs no code, so it needs no keys.
    assert main(["serve", "reference.py"]) == 0
    assert len(serve_here) == 1


def test_keys_stored_by_lllm_setup_count_and_are_loaded(
    tmp_path: Path, serve_here, monkeypatch, capsys
):
    _keyed_package(tmp_path / "keyed")
    lllm.credentials.write_env_file(".env.local", {KEY: "from-the-env-file"})

    assert main(["serve", "keyed"]) == 0
    assert os.environ[KEY] == "from-the-env-file"
    # Another env file, and the OS keyring, which --no-keyring leaves out.
    os.environ.pop(KEY)
    Path(".env.local").unlink()
    lllm.credentials.write_env_file("keys.env", {KEY: "from-keys-env"})
    assert main(["serve", "keyed", "--env-file", "keys.env"]) == 0
    assert os.environ.pop(KEY) == "from-keys-env"
    serve_here.clear()
    monkeypatch.setattr(lllm.credentials, "keyring_get", lambda name: "from-the-keyring")
    assert MISSING_KEY in _serve_error(capsys, ["serve", "keyed", "--no-keyring"])
    assert main(["serve", "keyed"]) == 0
    assert os.environ[KEY] == "from-the-keyring"
    assert len(serve_here) == 1


def test_missing_keys_are_asked_for_in_a_terminal(
    tmp_path: Path, serve_here, monkeypatch, capsys
):
    _keyed_package(tmp_path / "keyed")
    asked = []

    def configure(missing, *, credentials, env_file):
        asked.append(([requirement.name for requirement in missing], credentials))
        lllm.credentials.write_env_file(env_file, {KEY: "typed-in"})
        return str(env_file)

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(lllm.credentials, "configure_missing_api_keys", configure)

    assert main(["serve", "keyed", "--credentials", "env"]) == 0
    assert asked == [([KEY], "env")]
    assert "Configured 1 API key(s) via .env.local." in capsys.readouterr().out
    assert os.environ[KEY] == "typed-in"


def test_lllm_shell_serve_checks_keys_with_the_same_options(
    tmp_path: Path, serve_here, capsys
):
    _keyed_package(tmp_path / "keyed")

    err = _serve_error(capsys, ["shell", "serve", "keyed"], command=lllm.cli.main)

    assert MISSING_KEY in err
    assert lllm.cli.main(["shell", "serve", "keyed", "--skip-key-check"]) == 0
    assert len(serve_here) == 1


# Docs fix 6: add_tactic(tactic, ref=...) only labeled the strategy's record:
# the tactic's /info said package_ref null and requests had tactic_ref None.


class RefProbe(Tactic[Any, Any]):
    name = "probe"

    def _run(self, input_value, *, context=None):
        return context.tactic_ref


def test_a_mounted_ref_reaches_the_served_tactic():
    probe = RefProbe()
    own = RefProbe(package_ref="lllm://acme/desk/tactics/own")
    strategy = Strategy("desk")
    strategy.add_tactic(probe, ref="lllm://acme/desk/tactics/probe")
    strategy.add_tactic(probe, name="again", ref="lllm://acme/desk/tactics/again")
    strategy.add_tactic(own, name="mounted", ref="lllm://acme/desk/tactics/mounted")
    strategy.tactic(
        "plain",
        handler=lambda value, *, context=None: context.tactic_ref,
        ref="lllm://acme/desk/tactics/plain",
    )
    client = TestClient(create_strategy_app(strategy))

    for name in ("probe", "again", "mounted", "plain"):
        ref = f"lllm://acme/desk/tactics/{name}"
        assert client.get(f"/tactics/{name}/info").json()["package_ref"] == ref
        run = client.post(f"/tactics/{name}/run", json={"input": 1})
        invoked = client.post(f"/resources/{name}/invoke", json={"input": 1})
        assert run.json()["output"] == invoked.json()["output"] == ref
    # The tactics that were passed in keep their own refs.
    assert probe.package_ref is None
    assert own.package_ref == "lllm://acme/desk/tactics/own"


def test_a_ref_that_is_not_a_tactic_ref_labels_only_the_record():
    strategy = Strategy("desk")
    strategy.add_tactic(RefProbe(), ref="lllm://acme/desk/channels/inbox")
    strategy.add_tactic(RefProbe(), name="own", ref="desk-probe")
    client = TestClient(create_strategy_app(strategy))

    assert [resource.ref for resource in strategy.resources] == [
        "lllm://acme/desk/channels/inbox",
        "desk-probe",
    ]
    for name in ("probe", "own"):
        assert client.get(f"/tactics/{name}/info").json()["package_ref"] is None
        assert client.post(f"/tactics/{name}/run", json={"input": 1}).json()["output"] is None
