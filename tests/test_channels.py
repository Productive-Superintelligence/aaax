"""Channel stores: channel resources, package channels, and /network/.

Channel stores come from sssn, the channels extra; without it these tests
skip. They are LLLM's shell tests that use a store, including the store
fixes of its fix passes (SH1-SH3, SH6, and review finding 33).
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

pytest.importorskip("sssn", reason="channel stores need sssn: pip install sssn")

from sssn import (  # noqa: E402
    ChannelExistsError,
    ChannelNotFoundError,
    InvalidPayloadError,
    LocalStore,
    NetworkError,
    RemoteStore,
    TacticProcessor,
)
from sssn.server import create_app as create_store_app  # noqa: E402

from aaax import Strategy, create_strategy_app, load_strategy  # noqa: E402
from aaax.strategy import StrategyStore  # noqa: E402
from helpers import error_detail, write_demo_package, write_package  # noqa: E402


def _run_together(count: int, fn) -> list[Exception]:
    """Call ``fn(0)`` .. ``fn(count - 1)`` in threads released at once; return their errors."""

    barrier = threading.Barrier(count)
    errors: list[Exception] = []

    def run(index: int) -> None:
        barrier.wait()
        try:
            fn(index)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(index,)) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


def _forward_to(app) -> httpx.MockTransport:
    """An httpx transport that serves requests with ``app`` in-process."""

    client = TestClient(app)

    def handle(request: httpx.Request) -> httpx.Response:
        response = client.request(
            request.method,
            request.url.raw_path.decode(),
            content=request.content,
            headers={"content-type": request.headers.get("content-type", "application/json")},
        )
        return httpx.Response(
            response.status_code,
            content=response.content,
            headers={"content-type": response.headers.get("content-type", "application/json")},
        )

    return httpx.MockTransport(handle)


def test_package_directory_loads_manifest_resources_and_tactic(tmp_path: Path):
    package = write_demo_package(tmp_path / "analysis-pack")

    strategy = load_strategy(package)
    resources = {
        (resource.kind, resource.name): resource
        for resource in strategy.resources
    }
    client = TestClient(create_strategy_app(strategy))

    assert strategy.name == "analysis-pack"
    assert strategy.metadata["package"] == "demo/analysis-pack"
    assert strategy.metadata["card"]["summary"] == "Demo analyst package."
    assert ("package", "analysis-pack") in resources
    assert ("config", "default") in resources
    assert ("schema", "record") in resources
    assert ("tactic", "echo") in resources
    assert ("channel", "events") in resources
    assert ("snapshot", "latest") in resources
    assert ("service", "api") in resources
    assert ("run", "local") in resources
    assert ("doc", "readme") in resources
    assert ("example", "first") in resources
    assert ("asset", "logo") in resources

    response = client.post(
        "/tactics/echo/run",
        json={
            "input": {"text": "hello"},
            "context": {"metadata": {"request": "pkg-test"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["output"] == {
        "echo": {"text": "hello"},
        "context_type": "CallContext",
        "metadata": {"request": "pkg-test"},
    }


def test_package_channels_append_and_query_events(tmp_path: Path):
    package = write_demo_package(tmp_path / "analysis-pack")
    client = TestClient(create_strategy_app(load_strategy(package)))

    append_response = client.post(
        "/channels/events/events",
        json={
            "input": {
                "payload": {"text": "first"},
                "kind": "record",
                "source": "pytest",
            }
        },
    )
    query_response = client.get("/channels/events/events?limit=10")

    assert append_response.status_code == 200
    assert append_response.json()["output"]["channel"] == "events"
    assert append_response.json()["output"]["payload"] == {"text": "first"}
    assert query_response.status_code == 200
    assert query_response.json()["output"][0]["payload"] == {"text": "first"}
    assert query_response.json()["output"][0]["kind"] == "record"


def test_strategy_can_compose_prefixed_package_resources(tmp_path: Path):
    package = write_demo_package(tmp_path / "analysis-pack")
    strategy = Strategy("composed").use_package(
        package,
        prefix="pkg",
        store=tmp_path / "store",
    )
    client = TestClient(create_strategy_app(strategy))

    assert any(resource.name == "pkg.echo" for resource in strategy.resources)
    assert any(resource.name == "pkg.events" for resource in strategy.resources)

    response = client.post(
        "/tactics/pkg.echo/run",
        json={"input": {"text": "prefixed"}},
    )

    assert response.status_code == 200
    assert response.json()["output"]["echo"] == {"text": "prefixed"}


def test_package_channels_are_served_by_the_network_store_api(tmp_path: Path):
    package = write_demo_package(tmp_path / "analysis-pack")
    strategy = load_strategy(package)
    client = TestClient(create_strategy_app(strategy))

    client.post(
        "/channels/events/events",
        json={"input": {"payload": {"text": "via shell"}, "kind": "record"}},
    )

    assert strategy.store is not None
    assert [c["name"] for c in client.get("/network/channels").json()] == ["events"]
    events = client.get("/network/events", params={"channel": "events"}).json()
    assert [event["payload"] for event in events] == [{"text": "via shell"}]


def test_appended_events_default_to_kind_event_and_source_aaax(tmp_path: Path):
    store = LocalStore(tmp_path / "store")
    strategy = Strategy("desk").channel("inbox").attach_store(store)
    client = TestClient(create_strategy_app(strategy))

    client.post("/channels/inbox/events", json={"input": {"payload": "via the route"}})
    asyncio.run(strategy.invoke_resource("inbox", {"op": "append", "payload": "via Python"}))

    assert [(event.kind, event.source) for event in store.query_events("inbox")] == [
        ("event", "aaax"),
        ("event", "aaax"),
    ]


# SH1: channels declared with strategy.channel() are backed by the attached store.


def test_manual_channel_is_backed_by_the_attached_store(tmp_path: Path):
    store = LocalStore(tmp_path / "store")
    strategy = Strategy("manual")
    strategy.channel("log", description="Everything.")
    strategy.attach_store(store)
    client = TestClient(create_strategy_app(strategy))

    appended = client.post(
        "/channels/log/events",
        json={"input": {"payload": {"n": 1}, "kind": "note"}},
    )
    queried = client.get("/channels/log/events")
    info = client.post("/resources/log/invoke", json={"input": {"op": "info"}})

    assert appended.status_code == 200
    assert appended.json()["output"]["payload"] == {"n": 1}
    assert appended.json()["output"]["kind"] == "note"
    assert [event["payload"] for event in queried.json()["output"]] == [{"n": 1}]
    assert info.json()["output"]["description"] == "Everything."
    assert [event.payload for event in store.query_events("log")] == [{"n": 1}]


def test_store_backing_does_not_depend_on_declaration_order(tmp_path: Path):
    store = LocalStore(tmp_path / "store")
    store.create_channel({"name": "log", "description": "Created by hand."})
    strategy = Strategy("manual").attach_store(store)
    strategy.channel("log")
    strategy.channel("custom", handler=lambda request: {"handled": request})

    asyncio.run(strategy.invoke_resource("log", {"op": "append", "payload": 2}))
    custom = asyncio.run(strategy.invoke_resource("custom", {"x": 1}))

    assert [event.payload for event in store.query_events("log")] == [2]
    assert store.get_channel("log").description == "Created by hand."
    assert custom == {"handled": {"x": 1}}
    assert [channel.name for channel in store.list_channels()] == ["log"]


# SH2: one store per strategy, shared by every package; nothing is silently dropped.


def test_packages_share_the_strategy_store_served_at_network(tmp_path: Path):
    alpha = write_package(tmp_path / "alpha", "alpha")
    beta = write_package(tmp_path / "beta", "beta")
    strategy = Strategy("ops").use_package(alpha, prefix="a").use_package(beta, prefix="b")
    client = TestClient(create_strategy_app(strategy))

    client.post("/channels/a.events/events", json={"input": {"payload": "from alpha"}})
    client.post("/channels/b.events/events", json={"input": {"payload": "from beta"}})

    assert strategy.store.root == (alpha / ".lllm" / "network").resolve()
    assert not (beta / ".lllm").exists()
    names = sorted(channel["name"] for channel in client.get("/network/channels").json())
    assert names == ["a.events", "b.events"]
    for channel, payload in (("a.events", "from alpha"), ("b.events", "from beta")):
        events = client.get("/network/events", params={"channel": channel}).json()
        assert [event["payload"] for event in events] == [payload]
    channels = {resource["name"]: resource for resource in client.get("/channels").json()}
    assert channels["b.events"]["metadata"]["store"] == str(strategy.store.root)


def test_prefixed_packages_sharing_a_store_folder_keep_separate_channels(tmp_path: Path):
    shared = tmp_path / "shared"
    strategy = (
        Strategy("ops")
        .use_package(write_package(tmp_path / "alpha", "alpha"), prefix="a", store=shared)
        .use_package(write_package(tmp_path / "beta", "beta"), prefix="b", store=shared)
    )
    client = TestClient(create_strategy_app(strategy))

    client.post("/channels/a.events/events", json={"input": {"payload": "only alpha"}})

    assert [e["payload"] for e in client.get("/channels/a.events/events").json()["output"]] == [
        "only alpha"
    ]
    assert client.get("/channels/b.events/events").json()["output"] == []
    assert strategy.store.root == shared.resolve()


def test_a_strategy_never_swaps_its_store_silently(tmp_path: Path):
    alpha = write_package(tmp_path / "alpha", "alpha")
    beta = write_package(tmp_path / "beta", "beta")
    alpha_store = alpha / ".lllm" / "network"
    strategy = Strategy("ops").use_package(alpha, prefix="a")

    with pytest.raises(ValueError, match="a strategy has one store"):
        strategy.use_package(beta, prefix="b", store=tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="a strategy has one store"):
        strategy.attach_store(LocalStore(tmp_path / "other"))

    assert not any(resource.name.startswith("b.") for resource in strategy.resources)
    assert not (tmp_path / "elsewhere").exists()
    # The same folder is the same store, whether passed as a path or a store.
    strategy.use_package(beta, prefix="b", store=alpha_store)
    strategy.attach_store(LocalStore(alpha_store))
    assert strategy.store.root == alpha_store.resolve()


class _AuditingStore(LocalStore):
    """A store subclass whose own behavior must not be dropped."""

    def __init__(self, root):
        super().__init__(root)
        self.appended: list[Any] = []

    def append_event(self, event):
        appended = super().append_event(event)
        self.appended.append(appended.payload)
        return appended


def test_a_store_object_for_the_package_store_folder_is_the_store_used(tmp_path: Path):
    package = write_package(tmp_path / "pkg")
    strategy = Strategy("audit").use_package(package)
    audit = _AuditingStore(package / ".lllm" / "network")

    strategy.attach_store(audit)
    client = TestClient(create_strategy_app(strategy))
    client.post("/channels/events/events", json={"input": {"payload": 1}})
    client.post("/network/events", json={"channel": "events", "payload": 2})

    assert strategy.store.open() is audit
    assert audit.appended == [1, 2]
    assert [channel.name for channel in audit.list_channels()] == ["events"]


def test_a_store_object_for_a_folder_the_strategy_opened_is_rejected(tmp_path: Path):
    package = write_package(tmp_path / "pkg")
    folder = package / ".lllm" / "network"
    strategy = Strategy("audit").use_package(package)
    opened = strategy.store.open()  # serving the strategy or using a channel opens it

    with pytest.raises(ValueError, match="cannot switch to this _AuditingStore"):
        strategy.attach_store(_AuditingStore(folder))

    assert strategy.store.open() is opened
    # The store in use, or its folder named again, is still the same store.
    strategy.attach_store(opened)
    strategy.use_package(write_package(tmp_path / "beta", "beta"), prefix="b", store=folder)
    attached = Strategy("attached").attach_store(LocalStore(tmp_path / "store"))
    with pytest.raises(ValueError, match="already uses another store object"):
        attached.attach_store(_AuditingStore(tmp_path / "store"))


def test_attaching_none_is_a_no_op_without_a_store_and_never_drops_one(tmp_path: Path):
    bare = Strategy("bare").attach_store(None)
    bare.store = None

    assert bare.store is None

    store = LocalStore(tmp_path / "store")
    strategy = Strategy("kept").attach_store(store)
    with pytest.raises(ValueError, match="cannot drop it: a strategy has one store"):
        strategy.attach_store(None)
    with pytest.raises(ValueError, match="cannot drop it: a strategy has one store"):
        strategy.store = None

    assert strategy.store.same_as(store)


def test_network_serves_the_strategy_store_only_if_it_is_an_sssn_store(tmp_path: Path):
    class Notebook:
        """A store that is not an sssn store."""

        def __init__(self):
            self.channels: list[str] = []

        def create_channel(self, channel):
            self.channels.append(channel["name"])

    notebook = Notebook()
    local = Strategy("local").channel("log").attach_store(LocalStore(tmp_path / "store"))
    plain = Strategy("plain").channel("log").attach_store(notebook)

    local_client = TestClient(create_strategy_app(local))
    plain_client = TestClient(create_strategy_app(plain))

    assert [channel["name"] for channel in local_client.get("/network/channels").json()] == ["log"]
    assert plain_client.get("/network/channels").status_code == 404
    assert notebook.channels == ["log"]


def test_unbound_package_channels_stay_metadata_only(tmp_path: Path):
    store = LocalStore(tmp_path / "store")
    strategy = Strategy("meta").attach_store(store)
    strategy.use_package(write_package(tmp_path / "pkg"), bind=False)

    output = asyncio.run(strategy.invoke_resource("events", {"op": "append", "payload": 1}))
    strategy.store.open()

    assert output["resource"]["name"] == "events"
    assert store.list_channels() == ()


# SH3: shell routes use the services error envelope with meaningful status codes.


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ChannelNotFoundError("Channel not found: gone"), 404),
        (ChannelExistsError("Channel already exists: gone"), 409),
        (InvalidPayloadError("Invalid event."), 400),
    ],
)
def test_channel_handler_network_errors_keep_store_status_codes(error, status):
    def handler(input_value=None, *, context=None):
        raise error

    strategy = Strategy("errs")
    strategy.channel("gone", handler=handler)
    client = TestClient(create_strategy_app(strategy))

    response = client.get("/channels/gone/events")

    assert response.status_code == status
    assert error_detail(response)["type"] == type(error).__name__
    assert error_detail(response)["message"] == str(error)
    assert error_detail(response)["endpoint"] == "channel"
    assert error_detail(response)["metadata"] == {"resource": "gone"}


def test_invalid_input_is_a_400_envelope(tmp_path: Path):
    client = TestClient(create_strategy_app(load_strategy(write_package(tmp_path / "pkg"))))

    store_error = client.post(
        "/channels/events/events",
        json={"input": {"payload": 1, "kind": "not a token"}},
    )
    handler_error = client.get("/channels/events/events", params={"limit": 0})
    body_error = client.post("/resources/events/invoke", json={"context": "nope"})
    query_error = client.get("/channels/events/events", params={"limit": "many"})

    assert store_error.status_code == 400
    assert error_detail(store_error)["type"] == "InvalidPayloadError"
    assert handler_error.status_code == 400
    assert error_detail(handler_error) == {
        "type": "ValueError",
        "message": "limit must be a positive integer",
        "tactic": None,
        "endpoint": "channel",
        "request_id": None,
        "metadata": {"resource": "events"},
    }
    assert body_error.status_code == 400
    assert error_detail(body_error)["type"] == "SchemaError"
    assert error_detail(body_error)["message"] == "context: Input should be a valid dictionary"
    assert query_error.status_code == 400
    assert error_detail(query_error)["message"].startswith("query.limit: ")


def test_store_errors_get_the_store_servers_own_status_codes(monkeypatch):
    import sssn.server.fastapi as store_server

    class EventConflict(NetworkError):
        """A store error the store server reports as a conflict."""

    store_http_error = store_server._http_error

    def http_error(exc):
        error = store_http_error(exc)
        if isinstance(exc, EventConflict):
            error.status_code = 409
        return error

    def handler(input_value=None):
        raise EventConflict("Event already exists: e1")

    monkeypatch.setattr(store_server, "_http_error", http_error)
    strategy = Strategy("errs")
    strategy.channel("dup", handler=handler)

    response = TestClient(create_strategy_app(strategy)).get("/channels/dup/events")

    assert response.status_code == 409
    assert error_detail(response)["type"] == "EventConflict"
    assert error_detail(response)["message"] == "Event already exists: e1"


def test_remote_store_client_errors_keep_the_remote_status(tmp_path: Path):
    backend = LocalStore(tmp_path / "backend")
    remote = RemoteStore("http://store", transport=_forward_to(create_store_app(backend)))
    strategy = Strategy("remote").channel("log").attach_store(remote)
    strategy.service("recreate", handler=lambda value: remote.create_channel({"name": "log"}))
    client = TestClient(create_strategy_app(strategy))

    appended = client.post("/channels/log/events", json={"input": {"payload": 1}})
    orphan = client.post(
        "/channels/log/events",
        json={"input": {"payload": 2, "parent_ids": ["missing"]}},
    )
    conflict = client.post("/resources/recreate/invoke", json={"input": None})

    assert appended.status_code == 200
    assert [event.payload for event in backend.query_events("log")] == [1]
    assert orphan.status_code == 404
    assert error_detail(orphan)["type"] == "RemoteStoreError"
    assert "(EventNotFoundError): Event not found: missing" in error_detail(orphan)["message"]
    assert error_detail(orphan)["metadata"] == {"resource": "log"}
    assert conflict.status_code == 409
    assert "(ChannelExistsError)" in error_detail(conflict)["message"]


def test_other_remote_store_failures_stay_500():
    def broken(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/channels":
            return httpx.Response(200, json={"name": "log"})
        return httpx.Response(200, text="not json")  # a 2xx answer the client rejects

    remote = RemoteStore("http://store", transport=httpx.MockTransport(broken))
    strategy = Strategy("remote").channel("log").attach_store(remote)
    client = TestClient(create_strategy_app(strategy))

    response = client.post("/resources/log/invoke", json={"input": {"op": "info"}})

    assert response.status_code == 500
    assert error_detail(response)["type"] == "RemoteStoreError"


# Finding 33: a non-object input to POST /channels/{name}/events was replaced
# with {}, appending an event without the data that was sent.


@pytest.mark.parametrize(
    "body",
    [
        {"input": "hello world"},
        {"input": ["x", "y"]},
        {"input": 3},
        {"input": None},
        {"payload": "outside the input envelope"},
    ],
)
def test_channel_append_rejects_a_non_object_input(tmp_path: Path, body: dict[str, Any]):
    store = LocalStore(tmp_path / "store")
    strategy = Strategy("srv").channel("log").attach_store(store)
    client = TestClient(create_strategy_app(strategy))

    response = client.post("/channels/log/events", json=body)

    assert response.status_code == 400
    assert error_detail(response) == {
        "type": "SchemaError",
        "message": "input must be an object with the event fields",
        "tactic": None,
        "endpoint": "channel",
        "request_id": None,
        "metadata": {"resource": "log"},
    }
    assert store.query_events("log") == ()
    appended = client.post("/channels/log/events", json={"input": {"payload": "kept"}})
    assert appended.status_code == 200
    assert [event.payload for event in store.query_events("log")] == ["kept"]


# SH6: building or inspecting a strategy never creates its store.


def test_building_a_strategy_defers_the_store_until_a_channel_is_used(tmp_path: Path):
    package = write_package(tmp_path / "pkg")
    strategy = load_strategy(package)
    TacticProcessor(strategy.tactics()["echo"], strategy.store, source="events")

    channel = next(resource for resource in strategy.resources if resource.kind == "channel")

    assert isinstance(strategy.store, StrategyStore)
    assert strategy.store.root == (package / ".lllm" / "network").resolve()
    assert channel.metadata["store"] == str(strategy.store.root)
    assert not (package / ".lllm").exists()

    asyncio.run(strategy.invoke_resource("events", {"op": "append", "payload": 1}))

    assert (package / ".lllm" / "network").is_dir()
    assert [event.payload for event in strategy.store.query_events("events")] == [1]


def test_serving_opens_the_store_with_its_declared_channels(tmp_path: Path):
    package = write_package(tmp_path / "pkg", channels=("events", "alerts"))
    strategy = load_strategy(package)

    client = TestClient(create_strategy_app(strategy))

    assert (package / ".lllm" / "network").is_dir()
    channels = {channel["name"]: channel for channel in client.get("/network/channels").json()}
    assert sorted(channels) == ["alerts", "events"]
    assert channels["alerts"]["description"] == "The alerts stream."


def test_threads_using_an_attached_store_first_create_each_channel_once(tmp_path: Path):
    created: list[str] = []

    class SlowStore(LocalStore):
        def create_channel(self, channel):
            time.sleep(0.01)  # keep the other threads arriving mid-creation
            created.append(channel["name"])
            return super().create_channel(channel)

    strategy = Strategy("busy").attach_store(SlowStore(tmp_path / "store"))
    for index in range(4):
        strategy.channel(f"c{index}")

    errors = _run_together(
        4,
        lambda index: strategy.store.append_event({"channel": f"c{index}", "payload": index}),
    )

    assert errors == []
    assert sorted(created) == ["c0", "c1", "c2", "c3"]
    for index in range(4):
        assert [event.payload for event in strategy.store.query_events(f"c{index}")] == [index]


def test_threads_using_a_package_store_first_open_it_once(tmp_path: Path, monkeypatch):
    opened: list[Path] = []

    class SlowLocalStore(LocalStore):
        def __init__(self, root):
            time.sleep(0.01)  # keep the other threads arriving mid-open
            opened.append(root)
            super().__init__(root)

    monkeypatch.setattr("sssn.stores.LocalStore", SlowLocalStore)
    package = write_package(tmp_path / "pkg", channels=("c0", "c1", "c2", "c3"))
    strategy = load_strategy(package)

    errors = _run_together(
        4,
        lambda index: asyncio.run(
            strategy.invoke_resource(f"c{index}", {"op": "append", "payload": index})
        ),
    )

    assert errors == []
    assert opened == [(package / ".lllm" / "network").resolve()]
    for index in range(4):
        assert [event.payload for event in strategy.store.query_events(f"c{index}")] == [index]
