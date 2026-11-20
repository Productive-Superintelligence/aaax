"""Regression tests for the serving fixes found while the docs were rewritten.

Each section names the fix it covers (docs fixes 1-8). The fixes that need a
channel store are tested in test_channels.py.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import warnings
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import lllm.cli
import lllm.credentials
import lllm.protocol
from lllm import Tactic
from lllm.protocol import SchemaError
from lllm.services import create_service_app, endpoint

import aaax
import aaax.strategy
from aaax import (
    Strategy,
    StrategyResource,
    StrategyRunRequest,
    create_strategy_app,
    load_strategy,
)
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


def test_a_function_mounted_under_a_name_lllm_cannot_hold_answers_under_its_own():
    strategy = Strategy("names").tactic("a;b", handler=count_words)
    client = TestClient(create_strategy_app(strategy))

    reply = client.post("/tactics/a;b/run", json={"input": "one two"})
    invoked = client.post("/resources/a;b/invoke", json={"input": "one two"})

    assert reply.status_code == invoked.status_code == 200
    assert (reply.json()["output"], reply.json()["tactic"]) == (2, "count_words")
    assert invoked.json()["output"] == 2


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
            ("OPTIONS", f"/tactics/{name}/run"),
            ("POST", f"/tactics/{name}"),
            ("GET", f"/tactics/{name}/"),
        ]:
            response = client.request(
                method, path, json={"input": 1}, follow_redirects=False
            )
            assert response.status_code == expected.status_code == 404, (method, path)
            assert response.json() == expected.json(), (method, path)
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


def test_routes_added_under_tactics_after_the_app_is_built_still_answer():
    app = create_strategy_app(Strategy("desk").add_tactic(Echo()))

    @app.get("/tactics/extra/hello")
    def hello():
        return {"hello": True}

    @app.get("/tactics/extra/gone")
    def gone():
        raise HTTPException(status_code=404, detail="gone")

    more = FastAPI()
    more.get("/ping")(lambda: "pong")
    app.mount("/tactics/more", more)
    client = TestClient(app)

    assert client.get("/tactics/extra/hello").json() == {"hello": True}
    assert client.get("/tactics/more/ping").json() == "pong"
    # Their own 404s are theirs, not TacticNotFound.
    assert client.get("/tactics/extra/gone").json() == {"detail": "gone"}
    assert client.get("/tactics/more/nope").json() == {"detail": "Not Found"}
    # A mounted tactic's bare path redirects to its app, as LLLM's do.
    bare = client.get("/tactics/echo", follow_redirects=False)
    assert bare.status_code == 307
    assert bare.headers["location"].endswith("/tactics/echo/")


def test_the_apps_own_http_exception_handler_still_sees_every_other_404():
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    app = create_strategy_app(Strategy("desk").add_tactic(Echo()))

    @app.get("/tactics/extra/gone")
    def gone():
        raise HTTPException(status_code=404, detail="gone")

    @app.exception_handler(StarletteHTTPException)
    async def handle(request, exc):
        body = {"handled": exc.status_code, "detail": exc.detail}
        return JSONResponse(body, status_code=exc.status_code)

    client = TestClient(app)

    missing = client.post("/resources/nope/invoke", json={"input": 1}).json()
    assert missing["handled"] == 404
    assert missing["detail"]["error"]["type"] == "ResourceNotFoundError"
    assert client.get("/tactics/extra/gone").json() == {"handled": 404, "detail": "gone"}
    assert client.get("/nothing-here").json() == {"handled": 404, "detail": "Not Found"}
    # A path under /tactics/ for a name no tactic is mounted under still
    # gets LLLM's TacticNotFound.
    tactic = client.post("/tactics/nope/run", json={"input": 1})
    assert error_detail(tactic)["type"] == "TacticNotFound"


def test_an_app_mounted_under_a_prefix_answers_tactic_not_found():
    outer = FastAPI()
    outer.mount("/api", create_strategy_app(Strategy("desk").add_tactic(Echo())))
    client = TestClient(outer)

    missing = client.post("/api/tactics/nope/run", json={"input": 1}, follow_redirects=False)
    bare = client.get("/api/tactics/nope", follow_redirects=False)

    assert missing.status_code == bare.status_code == 404
    assert error_detail(missing)["type"] == error_detail(bare)["type"] == "TacticNotFound"
    assert error_detail(missing)["tactic"] == "nope"
    assert client.post("/api/tactics/echo/run", json={"input": 1}).json()["tactic"] == "echo"
    resource = client.post("/api/resources/nope/invoke", json={"input": 1})
    assert error_detail(resource)["type"] == "ResourceNotFoundError"
    assert client.get("/api/nothing-here").json() == {"detail": "Not Found"}


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
    strategy.resource("tactic", "bare", handler=lambda text: text)
    strategy.add_resource(StrategyResource(kind="tactic", name="long"), handler=count_words)
    strategy.add_tactic(Echo(), name="blank", description="")
    client = TestClient(create_strategy_app(strategy))

    records = {resource.name: resource.description for resource in strategy.resources}
    assert records == {
        "words": "Count the words in a ticket.",
        "echo": "Echo the input.",
        "bare": "",
        "long": "",  # add_resource adds the record as it was built
        "blank": "",  # add_tactic keeps a description given as ""
    }
    for name in ("words", "echo", "bare"):
        info = client.get(f"/tactics/{name}/info").json()
        assert info["description"] == records[name]


def test_strategy_subclasses_see_every_resource_through_add_resource(tmp_path: Path):
    seen = []

    class Recording(Strategy):
        def add_resource(self, resource, *, handler=None):
            seen.append((resource.kind, resource.name))
            return super().add_resource(resource, handler=handler)

    strategy = Recording("desk").add_tactic(Echo(), name="echo1", description="")
    strategy.tactic("words", handler=count_words)
    package = write_package(tmp_path / "pkg")  # with an "events" channel
    strategy.use_package(package, prefix="p")
    strategy.use_package(package, prefix="ref", bind=False)

    assert seen == [
        ("tactic", "echo1"),
        ("tactic", "words"),
        ("package", "p.analysis-pack"),
        ("tactic", "p.echo"),
        ("channel", "p.events"),
        ("package", "ref.analysis-pack"),
        ("tactic", "ref.echo"),
        ("channel", "ref.events"),
    ]
    assert strategy.resources[0].description == ""
    # The store channel behind a package channel is the manifest's; a
    # package mounted for reference adds the record only.
    assert strategy._channels["p.events"] == {
        "schema": None,
        "form": "log",
        "description": "The events stream.",
        "metadata": {},
        "name": "p.events",
    }
    assert "ref.events" not in strategy._channels


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


def test_a_body_that_is_neither_json_nor_utf8_text_is_a_400():
    strategy = Strategy("desk")
    strategy.runner(lambda value: value)
    strategy.service("svc", handler=lambda value: value)
    strategy.channel("feed", handler=lambda value=None: value)
    client = TestClient(create_strategy_app(strategy))
    binary = {"content": b"\xff\xfe\x00", "headers": {"content-type": "application/octet-stream"}}

    for route in ("/run", "/resources/svc/invoke", "/channels/feed/events"):
        response = client.post(route, **binary)
        assert response.status_code == 400, route
        assert error_detail(response)["type"] == "SchemaError"
        assert error_detail(response)["message"] == "The request body must be JSON or UTF-8 text."


def test_the_openapi_document_keeps_the_named_request_envelope():
    # As AAAX 0.3 documented these routes, so clients generated from the
    # document keep their types.
    strategy = Strategy("desk").service("svc", handler=lambda value: value)
    document = TestClient(create_strategy_app(strategy)).get("/openapi.json").json()

    for path in ("/run", "/resources/{name}/invoke", "/channels/{name}/events"):
        assert document["paths"][path]["post"]["requestBody"] == {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/StrategyRunRequest"}
                }
            },
        }, path
    schema = document["components"]["schemas"]["StrategyRunRequest"]
    model = StrategyRunRequest.model_json_schema()
    assert schema["title"] == "StrategyRunRequest"
    assert list(schema["properties"]) == ["input", "task", "context"]
    for name in ("input", "context"):  # as the installed pydantic writes them
        own = {key: value for key, value in model["properties"][name].items() if value is not None}
        assert schema["properties"][name] == own, name


def _refs(value: Any) -> list[str]:
    if isinstance(value, dict):
        found = [value["$ref"]] if isinstance(value.get("$ref"), str) else []
        return found + [ref for item in value.values() for ref in _refs(item)]
    if isinstance(value, list):
        return [ref for item in value for ref in _refs(item)]
    return []


def test_a_document_built_from_the_apps_routes_is_self_contained():
    # FastAPI's "Extending OpenAPI" recipe, and scripts that export the
    # spec, call get_openapi with the app's routes.
    from fastapi.openapi.utils import get_openapi

    app = create_strategy_app(Strategy("desk").service("svc", handler=lambda value: value))
    document = get_openapi(title="desk", version="1", routes=app.routes)

    schemas = document.get("components", {}).get("schemas", {})
    for ref in _refs(document):
        assert ref.removeprefix("#/components/schemas/") in schemas, ref
    for path in ("/run", "/resources/{name}/invoke", "/channels/{name}/events"):
        body = document["paths"][path]["post"]["requestBody"]
        assert body["required"] is True
        schema = body["content"]["application/json"]["schema"]
        assert list(schema["properties"]) == ["input", "task", "context"], path


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


def _keyed_package(
    root: Path,
    *,
    manifest: str = "lllm.toml",
    module: str = "docs_fix_keyed",
    code: str = "def echo(value):\n    return value\n",
) -> Path:
    root.mkdir(parents=True)
    (root / f"{module}.py").write_text(code)
    (root / manifest).write_text(
        f"""
[package]
org = "demo"
name = "keyed"

[tactics.echo]
entry = "{module}:echo"

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


def test_keys_already_in_the_environment_need_no_env_file_or_keyring(
    tmp_path: Path, serve_here, monkeypatch
):
    _keyed_package(tmp_path / "keyed")
    Path(".env.local").mkdir()  # not a file: reading it would fail

    def keyring_get(name):
        raise AssertionError("the keyring was read")

    monkeypatch.setattr(lllm.credentials, "keyring_get", keyring_get)
    monkeypatch.setenv(KEY, "exported")

    assert main(["serve", "keyed"]) == 0
    assert main(["serve", "keyed", "--env-file", ".env.local"]) == 0
    assert len(serve_here) == 2


def test_an_unreadable_default_env_file_counts_as_absent(
    tmp_path: Path, serve_here, monkeypatch, capsys
):
    _keyed_package(tmp_path / "keyed")
    Path(".env.local").mkdir()
    monkeypatch.setattr(lllm.credentials, "keyring_get", lambda name: "from-the-keyring")

    assert main(["serve", "keyed"]) == 0
    assert os.environ.pop(KEY) == "from-the-keyring"
    # An env file named on the command line has to be readable.
    err = _serve_error(capsys, ["serve", "keyed", "--env-file", ".env.local"])
    assert "env file must be a regular file" in err


def test_missing_keys_say_why_the_default_env_file_was_not_read(
    tmp_path: Path, serve_here, capsys
):
    _keyed_package(tmp_path / "keyed")
    Path(".env.local").mkdir()

    err = _serve_error(capsys, ["serve", "keyed"])

    assert MISSING_KEY in err
    assert ".env.local was not read: env file must be a regular file" in err
    assert "--env-file" in err


@pytest.mark.parametrize(
    "argv", [["--credentials", "env"], ["--no-keyring"]], ids=["env", "no-keyring"]
)
def test_keys_are_not_asked_for_when_they_could_not_be_stored(
    tmp_path: Path, serve_here, monkeypatch, capsys, argv
):
    # Typed into a terminal, they would go to the env file, which cannot be
    # read, and so cannot be written either: they would be lost.
    _keyed_package(tmp_path / "keyed")
    Path(".env.local").mkdir()
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    def configure(*args, **kwargs):
        raise AssertionError("asked for keys it cannot store")

    monkeypatch.setattr(lllm.credentials, "configure_missing_api_keys", configure)

    err = _serve_error(capsys, ["serve", "keyed", *argv])

    assert MISSING_KEY in err
    assert ".env.local was not read" in err
    assert "--env-file" in err
    assert serve_here == []


def test_keys_asked_for_go_to_the_keyring_when_the_default_env_file_is_unreadable(
    tmp_path: Path, serve_here, monkeypatch
):
    _keyed_package(tmp_path / "keyed")
    Path(".env.local").mkdir()
    stored: dict[str, str] = {}
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(lllm.credentials, "keyring_get", lambda name: stored.get(name))

    def configure(missing, *, credentials, env_file):
        assert credentials == "keyring"
        stored.update({requirement.name: "typed-in" for requirement in missing})
        return "keyring"

    monkeypatch.setattr(lllm.credentials, "configure_missing_api_keys", configure)

    assert main(["serve", "keyed", "--credentials", "keyring"]) == 0
    assert os.environ[KEY] == "typed-in"


def test_no_keyring_with_credentials_keyring_is_refused_up_front(serve_here, capsys):
    # Keys stored in the keyring could not be read back under --no-keyring.
    err = _serve_error(
        capsys,
        ["serve", "no-such-target", "--no-keyring", "--credentials", "keyring", "--skip-key-check"],
    )

    assert (
        "--no-keyring does not read the OS keyring, so --credentials keyring would "
        "store keys it cannot see; use --credentials env"
    ) in err


def test_a_package_mounted_from_another_manifest_file_is_checked_from_it(
    tmp_path: Path, serve_here, capsys
):
    custom = _keyed_package(tmp_path / "custom", manifest="desk.toml")
    # Another package in the same folder, which the strategy does not mount.
    (custom / "lllm.toml").write_text(
        '[package]\norg = "demo"\nname = "other"\n\n'
        '[requirements.api_keys]\nDOCS_FIX_OTHER_KEY = "Not this one."\n',
        encoding="utf-8",
    )
    (tmp_path / "strategy.py").write_text(
        "from aaax import Strategy\n"
        "strategy = Strategy('ops')\n"
        "strategy.use_package('custom/desk.toml', prefix='a')\n"
        "strategy.use_package('custom/desk.toml', prefix='b')\n",
        encoding="utf-8",
    )

    err = _serve_error(capsys, ["serve", "strategy.py"])

    assert MISSING_KEY in err
    assert "DOCS_FIX_OTHER_KEY" not in err
    assert "Run `lllm setup custom/desk.toml` or set the missing names" in err
    assert load_strategy("strategy.py")._packages == [(custom / "desk.toml").resolve()]


def test_keys_asked_for_under_no_keyring_go_to_the_env_file(
    tmp_path: Path, serve_here, monkeypatch, capsys
):
    _keyed_package(tmp_path / "keyed")
    asked = []

    def configure(missing, *, credentials, env_file):
        asked.append(credentials)
        lllm.credentials.write_env_file(env_file, {KEY: "typed-in"})
        return str(env_file)

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(lllm.credentials, "configure_missing_api_keys", configure)

    assert main(["serve", "keyed", "--no-keyring"]) == 0
    assert asked == ["env"]
    assert os.environ[KEY] == "typed-in"


TACTIC_KEY = "DOCS_FIX_TACTIC_KEY"


def test_the_keys_every_tactic_of_a_package_declares_are_checked(
    tmp_path: Path, serve_here, monkeypatch, capsys
):
    # lllm serve checks the first tactic, the one it would launch; AAAX
    # serves both.
    root = tmp_path / "pair"
    root.mkdir()
    (root / "docs_fix_pair.py").write_text(
        "def first(value):\n    return value\n\n\ndef second(value):\n    return value\n"
    )
    (root / "lllm.toml").write_text(
        '[package]\norg = "demo"\nname = "pair"\n\n'
        '[tactics.first]\nentry = "docs_fix_pair:first"\n\n'
        '[tactics.second]\nentry = "docs_fix_pair:second"\n'
        f'metadata = {{ required_api_keys = ["{TACTIC_KEY}"] }}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(TACTIC_KEY, "placeholder")
    monkeypatch.delenv(TACTIC_KEY)

    err = _serve_error(capsys, ["serve", "pair"])

    assert f"missing required API key(s):\n- {TACTIC_KEY}" in err
    assert "Run `lllm setup pair --resource tactics.second` or set" in err
    assert serve_here == []
    monkeypatch.setenv(TACTIC_KEY, "exported")
    assert main(["serve", "pair"]) == 0


def test_stored_keys_reach_package_code_that_reads_them_on_import(
    tmp_path: Path, serve_here, monkeypatch
):
    code = f"import os\n\nKEY = os.environ[{KEY!r}]\n\n\ndef echo(value):\n    return KEY\n"
    for module in ("docs_fix_import_env", "docs_fix_import_keyring"):
        _keyed_package(tmp_path / module, module=module, code=code)
        monkeypatch.delitem(sys.modules, module, raising=False)
    lllm.credentials.write_env_file(".env.local", {KEY: "from-the-env-file"})

    assert main(["serve", "docs_fix_import_env"]) == 0
    reply = TestClient(serve_here[-1]).post("/tactics/echo/run", json={"input": 1})
    assert reply.json()["output"] == "from-the-env-file"

    os.environ.pop(KEY)
    Path(".env.local").unlink()
    monkeypatch.setattr(lllm.credentials, "keyring_get", lambda name: "from-the-keyring")
    assert main(["serve", "docs_fix_import_keyring"]) == 0
    reply = TestClient(serve_here[-1]).post("/tactics/echo/run", json={"input": 1})
    assert reply.json()["output"] == "from-the-keyring"


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


# Docs fix 7: relative package paths in a strategy file resolved against the
# working directory, not the file's folder.


def test_a_strategy_file_mounts_packages_relative_to_its_folder(
    tmp_path: Path, monkeypatch, capsys
):
    project = tmp_path / "project"
    package = write_package(project / "packages" / "desk", "desk", channels=())
    (project / "strategy.py").write_text(
        """
from aaax import Strategy, add_package, strategy_from_package

single = strategy_from_package("packages/desk")
mounted = Strategy("mounted").use_package("packages/desk", prefix="top")


def build_strategy():
    strategy = Strategy("ops")
    strategy.use_package("packages/desk", prefix="a")
    add_package(strategy, "packages/desk/lllm.toml", prefix="b")
    return strategy
""".lstrip(),
        encoding="utf-8",
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    # Loading also runs the file's top level, which mounts the package too.
    for target in (project / "strategy.py", project, "../project/strategy.py"):
        strategy = load_strategy(target)
        assert {"a.echo", "b.echo"} <= {resource.name for resource in strategy.resources}
    assert main(["inspect", "../project"]) == 0
    assert "tactic a.echo lllm://demo/desk/tactics/echo" in capsys.readouterr().out
    records = [resource for resource in strategy.resources if resource.kind == "package"]
    assert [record.metadata["path"] for record in records] == [str(package.resolve())] * 2
    # Outside a strategy file, relative paths stay relative to the working
    # directory.
    with pytest.raises(OSError):
        Strategy("loose").use_package("packages/desk")


def test_a_0_3_strategy_file_with_working_directory_paths_still_loads(
    tmp_path: Path, monkeypatch
):
    # AAAX 0.3 resolved package paths in a strategy file against the working
    # directory, so files run from another folder named them from there.
    project = tmp_path / "project"
    write_package(project / "packages" / "desk", "desk", channels=())
    strategy_file = project / "strategy.py"
    strategy_file.write_text(
        "from aaax import Strategy\n"
        "strategy = Strategy('ops')\n"
        "strategy.use_package('project/packages/desk', prefix='old')\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with pytest.warns(FutureWarning) as caught:
        strategy = load_strategy("project/strategy.py")

    assert "old.echo" in {resource.name for resource in strategy.resources}
    assert len(caught) == 1
    message = str(caught[0].message)
    assert "'project/packages/desk' was found in the working directory" in message
    assert "A future minor release of AAAX looks in the file's folder only" in message
    # The warning points at the line in the strategy file that mounts it.
    assert Path(caught[0].filename) == strategy_file.absolute()
    assert caught[0].lineno == 3
    # A path found in the file's folder is used without a warning.
    monkeypatch.chdir(project)
    strategy_file.write_text(
        strategy_file.read_text().replace("project/packages", "packages"),
        encoding="utf-8",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert "old.echo" in {resource.name for resource in load_strategy("strategy.py").resources}


def test_package_paths_from_helpers_a_strategy_file_calls_use_its_folder(
    tmp_path: Path, monkeypatch
):
    # The helper sits in a subfolder that has a "packages/desk" of its own,
    # so the test tells the strategy file's folder from the caller's.
    project = tmp_path / "project"
    write_package(project / "packages" / "desk", "desk", channels=())
    helpers = project / "docs_fix_helpers"
    write_package(helpers / "packages" / "desk", "helper-desk", channels=())
    (helpers / "mounts.py").write_text(
        "def mount(strategy):\n"
        "    return strategy.use_package('packages/desk', prefix='helper')\n",
        encoding="utf-8",
    )
    (project / "strategy.py").write_text(
        "from aaax import Strategy\n"
        "from docs_fix_helpers.mounts import mount\n"
        "def build_strategy():\n"
        "    return mount(Strategy('ops'))\n",
        encoding="utf-8",
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    for module in ("docs_fix_helpers", "docs_fix_helpers.mounts"):
        monkeypatch.delitem(sys.modules, module, raising=False)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        strategy = load_strategy(project)

    assert "helper.desk" in {resource.name for resource in strategy.resources}


@pytest.mark.parametrize("target", ["other", "other/lllm.toml"])
def test_a_nested_load_strategy_loads_the_package_it_checked(
    tmp_path: Path, monkeypatch, target
):
    # The working directory and the strategy file's folder both hold an
    # "other" package; load_strategy checks the target relative to the
    # working directory, so that is the one it must load.
    write_package(tmp_path / "other", "here", channels=())
    project = tmp_path / "project"
    write_package(project / "other", "there", channels=())
    (project / "strategy.py").write_text(
        "from aaax import load_strategy\n"
        "def build_strategy():\n"
        f"    return load_strategy({target!r})\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert load_strategy(project / "strategy.py").name == "here"


@pytest.mark.parametrize("case", ["dot", "same-named-folder"])
def test_a_0_3_path_to_a_folder_without_a_package_falls_back_to_the_working_directory(
    tmp_path: Path, monkeypatch, case
):
    # The strategy file's folder has something at the path, but no package.
    if case == "dot":
        # A 0.3 launcher that mounts the package it is run from.
        launcher = tmp_path / "launcher"
        launcher.mkdir()
        (launcher / "strategy.py").write_text(
            "from aaax import strategy_from_package\n"
            "strategy = strategy_from_package('.')\n",
            encoding="utf-8",
        )
        strategy_file, path = launcher / "strategy.py", "."
        monkeypatch.chdir(write_package(tmp_path / "desk", "desk", channels=()))
    else:
        project = tmp_path / "project"
        (project / "packages" / "desk").mkdir(parents=True)  # no lllm.toml
        (project / "strategy.py").write_text(
            "from aaax import strategy_from_package\n"
            "strategy = strategy_from_package('packages/desk')\n",
            encoding="utf-8",
        )
        strategy_file, path = project / "strategy.py", "packages/desk"
        write_package(tmp_path / "packages" / "desk", "desk", channels=())
        monkeypatch.chdir(tmp_path)

    with pytest.warns(FutureWarning, match="found in the working directory") as caught:
        strategy = load_strategy(strategy_file)

    assert strategy.name == "desk"
    assert f"package path {path!r}" in str(caught[0].message)


def test_a_path_to_two_packages_keeps_the_working_directorys_with_a_warning(
    tmp_path: Path, monkeypatch
):
    project = tmp_path / "project"
    write_package(project / "packages" / "desk", "there", channels=())
    (project / "strategy.py").write_text(
        "from aaax import strategy_from_package\n"
        "strategy = strategy_from_package('packages/desk')\n",
        encoding="utf-8",
    )
    elsewhere = tmp_path / "elsewhere"
    write_package(elsewhere / "packages" / "desk", "here", channels=())
    monkeypatch.chdir(elsewhere)

    # As errors, the warning tells which branch the loader took.
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        with pytest.raises(FutureWarning) as raised:
            load_strategy(project / "strategy.py")
    with pytest.warns(FutureWarning):
        strategy = load_strategy(project / "strategy.py")

    message = str(raised.value)
    assert "names one package in the working directory" in message
    assert str(elsewhere / "packages" / "desk") in message
    assert str(project / "packages" / "desk") in message
    assert strategy.name == "here"  # the working directory's, as AAAX 0.3 chose


def test_a_path_to_no_package_names_the_strategy_files_folder(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "strategy.py").write_text(
        "from aaax import strategy_from_package\n"
        "strategy = strategy_from_package('packages/desk')\n",
        encoding="utf-8",
    )
    (tmp_path / "packages" / "desk").mkdir(parents=True)  # no lllm.toml here either
    monkeypatch.chdir(tmp_path)

    with pytest.raises(OSError, match=re.escape(str(project / "packages" / "desk"))):
        load_strategy(project / "strategy.py")


# Docs fix 8: ResourceNotFoundError was importable only from aaax.strategy.


def test_resource_not_found_error_is_exported_from_aaax():
    assert aaax.ResourceNotFoundError is aaax.strategy.ResourceNotFoundError
    assert "ResourceNotFoundError" in aaax.__all__
    with pytest.raises(aaax.ResourceNotFoundError, match="Strategy resource not found"):
        asyncio.run(Strategy("empty").invoke_resource("nope"))


def test_the_api_reference_lists_every_export():
    index = Path(__file__).resolve().parents[1] / "docs" / "api" / "index.md"
    documented = re.findall(r"^::: aaax\.\w+\.(\w+)$", index.read_text(), re.M)

    assert sorted(documented) == sorted(set(aaax.__all__) - {"__version__"})


# Review 2: the strategy routes read any body, so a page on another site
# could make a visitor's browser POST a form or text body to a strategy on
# 127.0.0.1 without a CORS preflight.

CROSS_SITE = {"origin": "https://evil.example"}
TEXT = {"content-type": "text/plain"}


def _guarded_client(calls: list[Any]) -> TestClient:
    strategy = Strategy("desk").add_tactic(Echo())
    strategy.runner(lambda value: calls.append(value) or "ran")
    strategy.service("svc", handler=lambda value: calls.append(value) or "called")
    strategy.channel("feed", handler=lambda value=None: calls.append(value) or "fed")
    return TestClient(create_strategy_app(strategy))


@pytest.mark.parametrize(
    ("route", "headers", "body"),
    [
        ("/run", {**CROSS_SITE, **TEXT}, "x"),
        ("/resources/svc/invoke", {**CROSS_SITE, "content-type": "application/x-www-form-urlencoded"}, "a=1"),
        ("/channels/feed/events", {"sec-fetch-site": "cross-site"}, None),
        ("/run", {"origin": "null", **TEXT}, "x"),
        ("/run", {"origin": "http://testserver:8400", **TEXT}, "x"),
        ("/tactics/echo/run", {**CROSS_SITE, "content-type": "multipart/form-data; boundary=b"}, "--b--"),
    ],
    ids=["text", "form", "fetch-metadata-no-body", "null-origin", "other-port", "mounted-tactic"],
)
def test_a_cross_site_post_that_is_not_json_is_refused(route, headers, body):
    calls: list[Any] = []
    client = _guarded_client(calls)

    response = client.post(route, headers=headers, content=body)

    assert response.status_code == 403
    assert error_detail(response)["type"] == "CrossSiteRequestError"
    assert "must send JSON" in error_detail(response)["message"]
    assert calls == []


@pytest.mark.parametrize(
    ("headers", "body"),
    [
        ({**CROSS_SITE, "content-type": "application/json"}, '{"input": 1}'),
        ({**CROSS_SITE, "content-type": "application/vnd.api+json; charset=utf-8"}, '{"input": 1}'),
        ({"sec-fetch-site": "cross-site", "content-type": "application/json"}, '{"input": 1}'),
        (TEXT, "from a script"),  # no Origin: not a browser
        ({"origin": "http://testserver", **TEXT}, "same origin"),
        ({"origin": "http://testserver:80", "sec-fetch-site": "same-origin", **TEXT}, "x"),
    ],
    ids=["json", "json-suffix", "fetch-metadata-json", "no-origin", "same-origin", "default-port"],
)
def test_json_non_browser_and_same_origin_posts_still_work(headers, body):
    calls: list[Any] = []
    client = _guarded_client(calls)

    for route in ("/run", "/resources/svc/invoke", "/tactics/echo/run"):
        assert client.post(route, headers=headers, content=body).status_code == 200, route
    assert len(calls) == 2


def test_cross_site_reads_and_preflights_are_not_refused():
    client = _guarded_client([])

    assert client.get("/strategy", headers={**CROSS_SITE, "sec-fetch-site": "cross-site"}).status_code == 200
    preflight = client.options(
        "/run",
        headers={**CROSS_SITE, "access-control-request-method": "POST"},
    )
    assert preflight.status_code != 403


class Explainer(Tactic[Any, Any]):
    """A tactic with custom endpoints, which run its code."""

    name = "explainer"
    calls: list[Any] = []

    def _run(self, input_value, *, context=None):
        return input_value

    @endpoint.get("/explain")
    def explain(self, input_value, *, context=None):
        self.calls.append(("explain", input_value))
        return {"explained": input_value}

    @endpoint.put("/notes")
    def put_note(self, input_value, *, context=None):
        self.calls.append(("put", input_value))
        return {"put": input_value}

    @endpoint.delete("/notes")
    def delete_note(self, input_value, *, context=None):
        self.calls.append(("delete", input_value))
        return {"deleted": input_value}


CROSS_SITE_FETCH = {**CROSS_SITE, "sec-fetch-site": "cross-site"}


def test_a_cross_site_get_to_a_tactics_custom_endpoint_is_refused(monkeypatch):
    monkeypatch.setattr(Explainer, "calls", [])
    client = TestClient(create_strategy_app(Strategy("desk").add_tactic(Explainer())))

    for method in ("GET", "HEAD"):
        for headers in (CROSS_SITE_FETCH, CROSS_SITE, {"sec-fetch-site": "same-site"}):
            response = client.request(method, "/tactics/explainer/explain?q=1", headers=headers)
            assert response.status_code == 403, (method, headers)
    json_get = client.get(
        "/tactics/explainer/explain", headers={**CROSS_SITE_FETCH, "content-type": "application/json"}
    )
    assert json_get.status_code == 403
    assert error_detail(json_get)["type"] == "CrossSiteRequestError"
    assert Explainer.calls == []
    # The built-in routes that only read stay open, and so do callers on the
    # same origin and those that are not browsers.
    for path in ("/info", "/openapi.json", "/docs", "/health", "/tactics/explainer/info"):
        response = client.get(f"/tactics/explainer{path}", headers=CROSS_SITE_FETCH)
        assert response.status_code == 200, path
    for path in ("/strategy", "/resources", "/tactics", "/channels", "/packages", "/health", "/docs", "/openapi.json"):
        assert client.get(path, headers=CROSS_SITE_FETCH).status_code == 200, path
    assert client.get("/tactics/explainer/explain?q=1").json() == {"explained": {"q": "1"}}
    same_origin = {"origin": "http://testserver", "sec-fetch-site": "same-origin"}
    assert client.get("/tactics/explainer/explain", headers=same_origin).status_code == 200


def test_put_patch_and_delete_are_never_refused(monkeypatch):
    # Browsers preflight them across origins, so the app's CORS settings
    # decide; a request that arrives was approved.
    monkeypatch.setattr(Explainer, "calls", [])
    client = TestClient(create_strategy_app(Strategy("desk").add_tactic(Explainer())))

    put = client.put("/tactics/explainer/notes", headers={**CROSS_SITE_FETCH, **TEXT}, content="x")
    delete = client.delete("/tactics/explainer/notes", headers=CROSS_SITE_FETCH)
    patch = client.patch("/run", headers={**CROSS_SITE_FETCH, **TEXT}, content="x")

    assert (put.status_code, delete.status_code) == (200, 200)
    assert patch.status_code == 405  # the route's own answer, not the guard's
    assert [call[0] for call in Explainer.calls] == ["put", "delete"]


@pytest.mark.parametrize(
    "headers",
    [
        # A proxy that terminates TLS: the page is https, the app sees http.
        {"host": "desk.example.com", "origin": "https://desk.example.com"},
        {"host": "desk.example.com:443", "origin": "https://desk.example.com"},
        # A proxy that rewrites Host: Sec-Fetch-Site alone decides.
        {"host": "127.0.0.1:8400", "origin": "https://desk.example.com", "sec-fetch-site": "same-origin"},
        {"origin": "https://evil.example", "sec-fetch-site": "none"},
    ],
    ids=["tls-proxy", "tls-proxy-explicit-port", "host-rewriting-proxy", "fetch-site-none"],
)
def test_requests_from_the_same_origin_behind_a_proxy_are_not_refused(headers):
    calls: list[Any] = []
    client = _guarded_client(calls)

    response = client.post("/run", headers={**headers, **TEXT}, content="from the page")

    assert response.status_code == 200
    assert calls == ["from the page"]


def test_sec_fetch_site_decides_alone_when_present():
    calls: list[Any] = []
    client = _guarded_client(calls)
    same_site = {"origin": "http://testserver", "sec-fetch-site": "same-site", **TEXT}

    # The Origin matches the Host, but the browser says the page is on
    # another origin of the same site.
    assert client.post("/run", headers=same_site, content="x").status_code == 403
    assert calls == []


def test_allow_cross_site_requests_turns_the_guard_off(monkeypatch):
    monkeypatch.setattr(Explainer, "calls", [])
    strategy = Strategy("desk").add_tactic(Explainer())
    strategy.runner(lambda value: value)
    client = TestClient(create_strategy_app(strategy, allow_cross_site_requests=True))

    assert client.post("/run", headers={**CROSS_SITE_FETCH, **TEXT}, content="x").status_code == 200
    assert client.get("/tactics/explainer/explain", headers=CROSS_SITE_FETCH).status_code == 200


def test_allow_cross_site_requests_reaches_an_lllm_that_takes_it(monkeypatch):
    # LLLM's own tactic services gain the same switch; pass it on when they do.
    import aaax.server

    seen = []
    real = aaax.server.create_tactic_app

    def create_tactic_app(tactic, *, allow_cross_site_requests=False):
        seen.append(allow_cross_site_requests)
        return real(tactic)

    monkeypatch.setattr(aaax.server, "create_tactic_app", create_tactic_app)
    create_strategy_app(Strategy("desk").add_tactic(Echo()), allow_cross_site_requests=True)
    create_strategy_app(Strategy("desk").add_tactic(Echo()))

    assert seen == [True, False]


# Review 8: lllm-core 0.4.1 raises OutputSchemaError, a SchemaError, for an
# output that fails its schema, and its services answer it with 500; the
# strategy's runner and handlers answered every SchemaError with 400.


def test_an_output_schema_error_from_the_runner_or_a_handler_is_a_500(monkeypatch):
    class OutputSchemaError(SchemaError):
        pass

    monkeypatch.setattr(lllm.protocol, "OutputSchemaError", OutputSchemaError, raising=False)

    def bad_output(value):
        raise OutputSchemaError("the output does not match its schema")

    def bad_input(value):
        raise SchemaError("the input does not match its schema")

    strategy = Strategy("desk")
    strategy.runner(bad_output)
    strategy.service("output", handler=bad_output)
    strategy.service("input", handler=bad_input)
    client = TestClient(create_strategy_app(strategy))

    for route in ("/run", "/resources/output/invoke"):
        response = client.post(route, json={"input": 1})
        assert response.status_code == 500, route
        assert error_detail(response)["type"] == "OutputSchemaError"
    assert client.post("/resources/input/invoke", json={"input": 1}).status_code == 400


# Review 9: tests the first pass missed.


def _package_with_code(root: Path, module: str, code: str, tactic: str, entry: str) -> Path:
    root.mkdir(parents=True)
    (root / f"{module}.py").write_text(code, encoding="utf-8")
    (root / "lllm.toml").write_text(
        f'[package]\norg = "demo"\nname = "{root.name}"\n\n'
        f'[tactics.{tactic}]\nentry = "{module}:{entry}"\n',
        encoding="utf-8",
    )
    return root


def test_a_package_tactic_whose_code_sets_a_package_ref_keeps_it(tmp_path: Path, monkeypatch):
    own = "lllm://elsewhere/shared/tactics/owned"
    package = _package_with_code(
        tmp_path / "owning",
        "docs_fix_owned",
        "from lllm.protocol import Tactic\n\n\n"
        "class Owned(Tactic):\n"
        "    def _run(self, input_value, *, context=None):\n"
        "        return context.tactic_ref\n\n\n"
        f"owned = Owned(name='owned', package_ref={own!r})\n",
        "owned",
        "owned",
    )
    monkeypatch.delitem(sys.modules, "docs_fix_owned", raising=False)
    strategy = Strategy("ops").use_package(package, prefix="p")
    client = TestClient(create_strategy_app(strategy))

    assert client.get("/tactics/p.owned/info").json()["package_ref"] == own
    assert client.post("/tactics/p.owned/run", json={"input": 1}).json()["output"] == own
    assert client.post("/resources/p.owned/invoke", json={"input": 1}).json()["output"] == own
    imported = sys.modules["docs_fix_owned"].owned
    assert (imported.tactic_name, imported.package_ref) == ("owned", own)
    assert strategy.tactics()["p.owned"] is not imported


def test_a_store_path_in_a_strategy_file_stays_relative_to_the_working_directory(
    tmp_path: Path, monkeypatch
):
    project = tmp_path / "project"
    write_package(project / "packages" / "desk", "desk")  # with a channel
    (project / "strategy.py").write_text(
        "from aaax import Strategy\n"
        "strategy = Strategy('ops')\n"
        "strategy.use_package('packages/desk', store='state/network')\n",
        encoding="utf-8",
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    strategy = load_strategy(project / "strategy.py")

    assert strategy.store.root == (elsewhere / "state" / "network").resolve()


@pytest.mark.parametrize(
    "body",
    [
        "raise RuntimeError('broken at the top')\n",
        "def build_strategy():\n    raise RuntimeError('broken in build_strategy')\n",
    ],
    ids=["top-level", "build_strategy"],
)
def test_the_strategy_folder_is_forgotten_when_a_strategy_file_raises(
    tmp_path: Path, monkeypatch, body
):
    import aaax.packages

    project = tmp_path / "project"
    write_package(project / "packages" / "desk", "desk", channels=())
    (project / "broken.py").write_text(body, encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    with pytest.raises(RuntimeError, match="broken"):
        load_strategy(project / "broken.py")

    assert aaax.packages._strategy_folder.get() is None
    with pytest.raises(OSError):
        Strategy("loose").use_package("packages/desk")


def test_a_tactic_mounted_without_overrides_is_the_callers_object():
    echo = Echo()
    again = Echo(name="again")
    strategy = Strategy("desk").add_tactic(echo)
    strategy.tactic("again", handler=again)  # its own name

    assert strategy.tactics()["echo"] is echo
    assert strategy.tactics()["again"] is again


def test_a_renamed_copy_keeps_the_tactics_service_ref_and_metadata():
    served = Echo(service_ref="https://desk.example/tactics/echo", metadata={"team": "support"})
    strategy = Strategy("desk").add_tactic(served, name="desk.echo")

    info = TestClient(create_strategy_app(strategy)).get("/tactics/desk.echo/info").json()

    assert info["name"] == "desk.echo"
    assert info["service_ref"] == "https://desk.example/tactics/echo"
    assert info["metadata"] == {"team": "support"}
    assert strategy.tactics()["desk.echo"] is not served


def test_a_package_tactic_without_a_description_keeps_an_empty_record(
    tmp_path: Path, monkeypatch
):
    from aaax.packages import PackageTactic

    package = _package_with_code(
        tmp_path / "undescribed",
        "docs_fix_undescribed",
        'def run(value):\n    """Described in code."""\n    return value\n',
        "run",
        "run",
    )
    monkeypatch.delitem(sys.modules, "docs_fix_undescribed", raising=False)
    strategy = Strategy("ops").use_package(package)
    # A package tactic mounted by hand is not imported to describe it either.
    strategy.tactic(
        "lazy",
        handler=PackageTactic("docs_fix_undescribed:run", base_dir=package, name="run"),
    )

    records = {resource.name: resource.description for resource in strategy.resources}
    assert records["run"] == records["lazy"] == ""
    assert "docs_fix_undescribed" not in sys.modules
    # Its /info, once loaded, still has the code's description.
    assert strategy.tactics()["run"].info().description == "Described in code."
