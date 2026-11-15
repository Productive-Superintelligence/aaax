"""Regression tests for strategy fixes that need no channel store.

From LLLM's shell fix passes: SH1-SH6, and review findings 7, 26, and 34.
The fixes that involve channel stores are tested in test_channels.py.
"""

from __future__ import annotations

import asyncio
import builtins
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from lllm import Tactic
from lllm.protocol import CallContext, SchemaError

from aaax import Strategy, create_strategy_app, load_strategy
from aaax.cli import main
from aaax.strategy import ResourceNotFoundError
from helpers import error_detail, write_package


def _tactic_package(root: Path, name: str, tactic: str, entry: str) -> Path:
    root.mkdir(parents=True)
    (root / "lllm.toml").write_text(
        f"""
[package]
org = "demo"
name = "{name}"
version = "0.1.0"
kind = "app"

[tactics."{tactic}"]
entry = "{entry}"
""".lstrip(),
        encoding="utf-8",
    )
    return root


# SH1: channels declared with strategy.channel() are backed by the attached store.


def test_channel_without_a_store_still_echoes():
    strategy = Strategy("bare")
    strategy.channel("log")

    output = asyncio.run(strategy.invoke_resource("log", {"op": "append"}))

    assert output["resource"]["name"] == "log"
    assert output["input"] == {"op": "append"}


# SH2: one store per strategy, shared by every package; nothing is silently dropped.


def test_clashing_package_names_are_rejected_before_anything_is_added(tmp_path: Path):
    alpha = write_package(tmp_path / "alpha", "alpha")
    beta = write_package(tmp_path / "beta", "beta")
    strategy = Strategy("ops").use_package(alpha)
    before = strategy.resources

    with pytest.raises(ValueError, match="echo, events. Mount it with a prefix"):
        strategy.use_package(beta)

    assert strategy.resources == before
    strategy.use_package(beta, prefix="b")
    assert {"b.beta", "b.echo", "b.events"} <= {resource.name for resource in strategy.resources}


# SH3: shell routes use the services error envelope with meaningful status codes.


def test_unknown_resource_is_a_clean_404():
    client = TestClient(create_strategy_app(Strategy("empty")))

    response = client.post("/resources/nope/invoke", json={"input": 1})

    assert response.status_code == 404
    assert error_detail(response)["type"] == "ResourceNotFoundError"
    assert error_detail(response)["message"] == "Strategy resource not found: nope"
    with pytest.raises(KeyError):
        asyncio.run(Strategy("empty").invoke_resource("nope"))
    assert str(ResourceNotFoundError("Strategy resource not found: x")) == (
        "Strategy resource not found: x"
    )


def test_unexpected_handler_errors_are_500_envelopes_not_404():
    strategy = Strategy("keys")
    strategy.service("lookup", handler=lambda payload: payload["missing"])

    @strategy.runner
    def run(input_value):
        raise RuntimeError("runner broke")

    client = TestClient(create_strategy_app(strategy))

    lookup = client.post("/resources/lookup/invoke", json={"input": {}})
    run_response = client.post("/run", json={"input": 1})

    assert lookup.status_code == 500
    assert error_detail(lookup)["type"] == "KeyError"
    assert run_response.status_code == 500
    assert error_detail(run_response)["message"] == "runner broke"
    assert error_detail(run_response)["endpoint"] == "run"


def test_shell_errors_have_the_tactic_service_envelope_shape():
    class Broken(Tactic[Any, Any]):
        name = "broken"

        def _run(self, input_value, *, context=None):
            raise RuntimeError("tactic broke")

    strategy = Strategy("shape").add_tactic(Broken())
    client = TestClient(create_strategy_app(strategy))

    service_error = client.post("/tactics/broken/run", json={"input": 1})
    shell_error = client.post("/resources/broken/invoke", json={"input": 1})
    missing = client.post("/resources/missing/invoke", json={"input": 1})

    assert service_error.status_code == shell_error.status_code == 500
    assert set(error_detail(shell_error)) == set(error_detail(service_error))
    assert set(error_detail(missing)) == set(error_detail(service_error))
    assert error_detail(shell_error)["message"] == "tactic broke"


@pytest.mark.parametrize(
    ("error", "status"),
    [(ValueError("value must be positive"), 500), (SchemaError("value must be a number"), 400)],
)
def test_a_tactic_error_has_the_same_status_on_both_tactic_routes(error, status):
    class Picky(Tactic[Any, Any]):
        name = "picky"

        def _run(self, input_value, *, context=None):
            raise error

    def plain(input_value, *, context=None):
        raise error

    strategy = Strategy("status").add_tactic(Picky())
    strategy.tactic("plain", handler=plain)
    client = TestClient(create_strategy_app(strategy))

    for name in ("picky", "plain"):
        via_tactic = client.post(f"/tactics/{name}/run", json={"input": -1})
        via_resource = client.post(f"/resources/{name}/invoke", json={"input": -1})

        assert via_tactic.status_code == via_resource.status_code == status
        assert error_detail(via_resource)["type"] == error_detail(via_tactic)["type"] == type(error).__name__
        assert error_detail(via_resource)["message"] == str(error)


def test_a_lookup_that_fails_inside_a_handler_is_not_a_404():
    strategy = Strategy("router")

    async def route(value, *, context=None):
        return await strategy.invoke_resource(value["target"])

    strategy.tactic("router", handler=route)
    strategy.service("relay", handler=route)
    strategy.runner(route)
    client = TestClient(create_strategy_app(strategy))
    body = {"input": {"target": "missing"}}

    via_tactic = client.post("/tactics/router/run", json=body)
    via_resource = client.post("/resources/router/invoke", json=body)
    relay = client.post("/resources/relay/invoke", json=body)
    run = client.post("/run", json=body)
    missing = client.post("/resources/missing/invoke", json=body)
    missing_channel = client.get("/channels/missing/events")

    assert via_tactic.status_code == via_resource.status_code == 500
    assert relay.status_code == run.status_code == 500
    for response in (via_tactic, via_resource, relay, run):
        assert error_detail(response)["type"] == "ResourceNotFoundError"
        assert error_detail(response)["message"] == "Strategy resource not found: missing"
    assert error_detail(via_resource)["metadata"] == {"resource": "router"}
    # Only the resource named in the URL is looked up by the route.
    assert missing.status_code == missing_channel.status_code == 404
    assert error_detail(missing)["metadata"] == {"resource": "missing"}
    assert error_detail(missing_channel)["endpoint"] == "channel"


def test_an_http_exception_in_a_tactic_has_the_same_status_on_both_tactic_routes():
    def guarded(input_value, *, context=None):
        raise HTTPException(status_code=403, detail="no")

    strategy = Strategy("http")
    strategy.tactic("guarded", handler=guarded)
    client = TestClient(create_strategy_app(strategy))

    via_tactic = client.post("/tactics/guarded/run", json={"input": 1})
    via_resource = client.post("/resources/guarded/invoke", json={"input": 1})

    assert via_tactic.status_code == via_resource.status_code == 500
    assert error_detail(via_resource)["type"] == error_detail(via_tactic)["type"] == "HTTPException"
    assert error_detail(via_resource)["message"] == error_detail(via_tactic)["message"] == "403: no"


def test_handler_http_exceptions_keep_their_status():
    def handler(input_value=None):
        raise HTTPException(status_code=403, detail="no")

    strategy = Strategy("http")
    strategy.service("guarded", handler=handler)
    client = TestClient(create_strategy_app(strategy))

    response = client.post("/resources/guarded/invoke", json={"input": 1})

    assert response.status_code == 403
    assert response.json() == {"detail": "no"}


def test_error_mapping_does_not_import_sssn(monkeypatch):
    def handler(input_value=None):
        raise ValueError("bad input")

    strategy = Strategy("plain")
    strategy.service("check", handler=handler)
    client = TestClient(create_strategy_app(strategy))
    real_import = builtins.__import__

    def blocked_sssn_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name.split(".", 1)[0] == "sssn":
            raise ImportError(f"blocked sssn: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_sssn_import)
    response = client.post("/resources/check/invoke", json={"input": 1})

    assert response.status_code == 400
    assert error_detail(response)["message"] == "bad input"


# SH4: tactic resources run through the tactic path on /resources/{name}/invoke.


def test_plain_function_tactic_gets_the_same_call_context_on_both_routes():
    def probe(input_value, *, context=None):
        return {
            "context_type": type(context).__name__,
            "metadata": context.metadata,
            "endpoint": context.endpoint,
            "request_id": context.request_id,
        }

    strategy = Strategy("ctx")
    strategy.tactic("probe", handler=probe)
    client = TestClient(create_strategy_app(strategy))
    body = {
        "input": {"x": 1},
        "context": {"metadata": {"request": "r1"}, "request_id": "req-1"},
    }

    via_tactic = client.post("/tactics/probe/run", json=body).json()["output"]
    via_resource = client.post("/resources/probe/invoke", json=body).json()["output"]

    assert via_resource == via_tactic == {
        "context_type": "CallContext",
        "metadata": {"request": "r1"},
        "endpoint": "run",
        "request_id": "req-1",
    }


def test_tactic_objects_and_package_tactics_get_the_request_call_context(tmp_path: Path):
    class Probe(Tactic[Any, Any]):
        name = "probe"

        def _run(self, input_value, *, context=None):
            return {"metadata": context.metadata, "tags": context.tags}

    strategy = Strategy("ctx").add_tactic(Probe())
    strategy.use_package(write_package(tmp_path / "pkg", channels=()), prefix="pkg")
    client = TestClient(create_strategy_app(strategy))
    body = {"input": 1, "context": {"metadata": {"k": "v"}, "tags": {"team": "a"}}}

    probe = client.post("/resources/probe/invoke", json=body).json()["output"]
    echo = client.post("/resources/pkg.echo/invoke", json=body).json()["output"]

    assert probe == {"metadata": {"k": "v"}, "tags": {"team": "a"}}
    assert echo["context_type"] == "CallContext"
    assert echo["metadata"] == {"k": "v"}


def test_non_tactic_resources_keep_the_dict_context():
    seen: list[Any] = []

    def handler(input_value, context=None):
        seen.append(context)
        return input_value

    class Metadata(Tactic[Any, Any]):
        name = "metadata"

        def _run(self, input_value, *, context=None):
            return context.metadata

    strategy = Strategy("ctx")
    strategy.service("svc", handler=handler)
    strategy.service("wrapped", handler=Metadata())
    client = TestClient(create_strategy_app(strategy))
    body = {"input": 1, "context": {"request": "r1"}}

    client.post("/resources/svc/invoke", json=body)
    wrapped = client.post("/resources/wrapped/invoke", json=body).json()["output"]

    assert seen == [{"request": "r1"}]
    assert wrapped == {"request": "r1"}


async def _async_tick(*, context=None):
    return {"metadata": context.metadata}


@pytest.mark.parametrize(
    ("handler", "output"),
    [
        (lambda: {"ticked": True}, {"ticked": True}),
        (lambda *, context=None: {"metadata": context.metadata}, {"metadata": {"k": "v"}}),
        (lambda **kwargs: sorted(kwargs), ["context"]),
        (_async_tick, {"metadata": {"k": "v"}}),
    ],
    ids=["no-parameters", "context-only", "keywords-only", "async"],
)
def test_tactic_handlers_without_an_input_run_on_both_routes(handler, output):
    strategy = Strategy("tick")
    strategy.tactic("tick", handler=handler)
    client = TestClient(create_strategy_app(strategy))
    body = {"input": 1, "context": {"metadata": {"k": "v"}}}

    via_resource = client.post("/resources/tick/invoke", json=body)
    via_tactic = client.post("/tactics/tick/run", json=body)

    assert via_resource.status_code == via_tactic.status_code == 200
    assert via_resource.json()["output"] == via_tactic.json()["output"] == output


def test_an_async_callable_object_tactic_is_awaited_on_both_routes():
    class Probe:
        async def __call__(self, input_value, *, context=None):
            return {"input": input_value, "context_type": type(context).__name__}

    strategy = Strategy("probe")
    strategy.tactic("probe", handler=Probe())
    client = TestClient(create_strategy_app(strategy))

    via_resource = client.post("/resources/probe/invoke", json={"input": 1})
    via_tactic = client.post("/tactics/probe/run", json={"input": 1})

    assert via_resource.status_code == via_tactic.status_code == 200
    assert via_resource.json()["output"] == via_tactic.json()["output"] == {
        "input": 1,
        "context_type": "CallContext",
    }


def test_an_input_less_tactic_keeps_its_description_and_runs_synchronously():
    def refresh():
        """Refresh the cache."""
        return {"refreshed": True}

    strategy = Strategy("tick")
    strategy.tactic("refresh", handler=refresh)
    tactic = strategy.tactics()["refresh"]

    assert tactic.info().name == "refresh"
    assert tactic.info().description == "Refresh the cache."
    assert tactic.run(None) == {"refreshed": True}
    assert asyncio.run(strategy.invoke_resource("refresh")) == {"refreshed": True}


def test_invoke_resource_accepts_a_call_context_from_python():
    strategy = Strategy("ctx")
    strategy.tactic("probe", handler=lambda value, context=None: context.request_id)

    output = asyncio.run(
        strategy.invoke_resource("probe", 1, context=CallContext(request_id="py-1"))
    )

    assert output == "py-1"


# SH5: package tactics carry their manifest ref.


def test_package_tactics_report_the_manifest_ref(tmp_path: Path):
    ref = "lllm://demo/analysis-pack/tactics/echo"
    strategy = load_strategy(write_package(tmp_path / "pkg", channels=()))
    prefixed = Strategy("ops").use_package(
        write_package(tmp_path / "pkg2", channels=()), prefix="p"
    )
    client = TestClient(create_strategy_app(strategy))
    prefixed_client = TestClient(create_strategy_app(prefixed))

    assert client.get("/tactics/echo/info").json()["package_ref"] == ref
    assert prefixed_client.get("/tactics/p.echo/info").json()["package_ref"] == ref
    assert strategy.tactics()["echo"].package_ref == ref
    invoked = client.post("/resources/echo/invoke", json={"input": 1}).json()["output"]
    assert invoked["tactic_ref"] == ref


def test_packages_sharing_a_tactic_object_each_report_their_own_ref(
    tmp_path: Path, monkeypatch
):
    class Summarize(Tactic[Any, Any]):
        name = "summarize"

        def _run(self, input_value, *, context=None):
            return context.tactic_ref

    # A module-level instance in an installed module, which both packages name.
    shared = Summarize()
    module = types.ModuleType("fix_shell_shared_tactics")
    module.summarize = shared
    monkeypatch.setitem(sys.modules, "fix_shell_shared_tactics", module)
    entry = "fix_shell_shared_tactics:summarize"
    strategy = (
        Strategy("ops")
        .use_package(_tactic_package(tmp_path / "alpha", "alpha", "summarize", entry), prefix="a")
        .use_package(_tactic_package(tmp_path / "beta", "beta", "summarize", entry), prefix="b")
    )
    client = TestClient(create_strategy_app(strategy))

    for prefix, package in (("a", "alpha"), ("b", "beta")):
        ref = f"lllm://demo/{package}/tactics/summarize"
        assert client.get(f"/tactics/{prefix}.summarize/info").json()["package_ref"] == ref
        run = client.post(f"/tactics/{prefix}.summarize/run", json={"input": 1})
        assert run.json()["output"] == ref
    assert shared.package_ref is None


def test_a_tactic_name_a_ref_cannot_carry_still_serves(tmp_path: Path):
    package = _tactic_package(tmp_path / "pkg", "odd", "a#b", "odd_code:run")
    (package / "odd_code.py").write_text(
        "def run(input_value, *, context=None):\n    return context.tactic_ref\n",
        encoding="utf-8",
    )

    client = TestClient(create_strategy_app(load_strategy(package)))

    assert client.get("/tactics/a%23b/info").json()["package_ref"] is None
    invoked = client.post("/resources/a%23b/invoke", json={"input": 1})
    assert invoked.status_code == 200
    assert invoked.json()["output"] is None


# SH6: building or inspecting a strategy never creates its store.


def test_inspecting_a_package_never_creates_its_store(tmp_path: Path, capsys):
    package = write_package(tmp_path / "pkg")

    assert main(["inspect", str(package)]) == 0
    assert main(["inspect", str(package), "--json"]) == 0

    assert "channel events lllm://demo/analysis-pack/channels/events" in capsys.readouterr().out
    assert not (package / ".lllm").exists()


# Finding 7: the channel routes served any resource, so a GET ran a tactic.


@pytest.mark.parametrize("kind", ["tactic", "service"])
def test_channel_routes_serve_only_channel_resources(kind: str):
    calls = []

    def deploy(input_value, context=None):
        calls.append(input_value)
        return {"deployed": True}

    strategy = Strategy("srv").resource(kind, "deploy", handler=deploy)
    client = TestClient(create_strategy_app(strategy))

    query = client.get("/channels/deploy/events")
    append = client.post("/channels/deploy/events", json={"input": {"payload": 1}})

    assert query.status_code == append.status_code == 404
    for response in (query, append):
        assert error_detail(response)["type"] == "ResourceNotFoundError"
        assert error_detail(response)["message"] == "Strategy channel not found: deploy"
        assert error_detail(response)["endpoint"] == "channel"
        assert error_detail(response)["metadata"] == {"resource": "deploy"}
    assert calls == []
    # The resource is still served by its own route.
    assert client.post("/resources/deploy/invoke", json={"input": 1}).status_code == 200
    assert calls == [1]


def test_channel_routes_still_call_a_channel_handler():
    seen = []

    def feed(input_value=None, *, context=None):
        seen.append(input_value)
        return {"op": input_value["op"]}

    client = TestClient(create_strategy_app(Strategy("srv").channel("feed", handler=feed)))

    assert client.get("/channels/feed/events").json()["output"] == {"op": "query"}
    appended = client.post("/channels/feed/events", json={"input": {"payload": 1}})
    assert appended.json()["output"] == {"op": "append"}
    assert seen[1] == {"payload": 1, "op": "append"}


# Finding 26: keyword-only handlers were passed the input positionally.


def test_keyword_only_handlers_are_called_without_the_input():
    async def kwonly(*, context=None, verbose=False):
        return {"context": context, "verbose": verbose}

    strategy = Strategy("srv").service("kwonly", handler=kwonly)
    strategy.service("plain", handler=lambda *, verbose=False: {"verbose": verbose})
    strategy.runner(lambda *, context=None, dry_run=False: {"ran": True, "dry_run": dry_run})
    client = TestClient(create_strategy_app(strategy))

    assert asyncio.run(strategy.invoke_resource("kwonly", {"x": 1}, context={"a": 1})) == {
        "context": {"a": 1},
        "verbose": False,
    }
    assert asyncio.run(strategy.arun({"x": 1})) == {"ran": True, "dry_run": False}
    invoked = client.post("/resources/kwonly/invoke", json={"input": None})
    assert invoked.status_code == 200
    assert invoked.json()["output"] == {"context": {}, "verbose": False}
    plain = client.post("/resources/plain/invoke", json={"input": 1})
    assert plain.json()["output"] == {"verbose": False}
    assert client.post("/run", json={"input": 1}).json()["output"] == {
        "ran": True,
        "dry_run": False,
    }


def test_keyword_only_tactic_handlers_run_on_both_tactic_routes():
    async def kwonly(*, context=None, verbose=False):
        return {"context": type(context).__name__, "verbose": verbose}

    strategy = Strategy("srv").tactic("kwonly", handler=kwonly)
    strategy.tactic("takes_input", handler=lambda value, *, verbose=False: {"value": value})
    client = TestClient(create_strategy_app(strategy))

    for route in ("/tactics/kwonly/run", "/resources/kwonly/invoke"):
        response = client.post(route, json={"input": 7})
        assert response.status_code == 200
        assert response.json()["output"] == {"context": "CallContext", "verbose": False}
    # A positional parameter still takes the input, keyword-only extras or not.
    for route in ("/tactics/takes_input/run", "/resources/takes_input/invoke"):
        assert client.post(route, json={"input": 7}).json()["output"] == {"value": 7}


# Finding 34: a name StrategyInfo rejects was accepted, then GET /strategy was a 500.


@pytest.mark.parametrize("name", ["My Strategy", "a/b", "a:b", "x%y", "", "..", None])
def test_strategy_rejects_a_name_its_info_cannot_carry(name):
    with pytest.raises(ValueError, match="strategy.name must be a non-empty path segment"):
        Strategy(name)


def test_strategy_info_is_served_for_a_valid_name():
    strategy = Strategy("my-strategy.v2")
    client = TestClient(create_strategy_app(strategy))

    assert strategy.info().name == "my-strategy.v2"
    assert client.get("/strategy").json()["name"] == "my-strategy.v2"


def test_cli_reports_an_invalid_strategy_name(tmp_path: Path, capsys):
    (tmp_path / "strategy.py").write_text(
        "from aaax import Strategy\nstrategy = Strategy('My Strategy')\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exit_info:
        main(["inspect", str(tmp_path)])

    assert exit_info.value.code == 2
    assert "strategy.name must be a non-empty path segment" in capsys.readouterr().err
