"""FastAPI server for AAAX strategies.

A strategy app is assembled from lllm's own services: every tactic resource is
mounted as a full tactic service at ``/tactics/<name>/`` (``run``, ``stream``,
``info``, and custom endpoints), and a strategy with an sssn channel store
mounts the sssn store API at ``/network/``. The shell adds its own surface on
top: ``/strategy``, ``/resources``, channel shortcuts, and the strategy ``/run``.

The shell routes report errors in the services error envelope,
``{"detail": {"error": {"type": ..., "message": ...}}}``: a resource named in
the URL that does not exist is a 404, as is a resource other than a channel on
the ``/channels/`` routes and a name under ``/tactics/`` that no tactic is
mounted under (``TacticNotFound``, as LLLM's multi-tactic app answers), and a
malformed request is a 400, including an event appended there whose input is
not an object. A tactic resource fails with the
status ``POST /tactics/<name>/run`` uses (400 for ``SchemaError`` and
``TacticUnsupportedError``, 500 for anything else, an ``HTTPException``
included). Other handlers keep the status of an ``HTTPException`` they raise;
a ``ValueError`` or ``SchemaError`` is a 400; channel store errors keep the
store server's codes (404 not found, 409 conflict, 400 otherwise), and a
remote store's 4xx errors keep the code its server returned; anything else is
a 500, including a resource lookup that fails inside a handler.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.routing import Match
from starlette.types import ASGIApp, Receive, Scope, Send

from lllm.protocol import SchemaError, TacticUnsupportedError
from lllm.services import (
    ErrorDetail,
    ErrorResponse,
    create_tactic_app,
    status_code_for_error,
)

from .models import StrategyRunRequest, StrategyRunResponse
from .strategy import (
    ResourceNotFoundError,
    Strategy,
    _imported_sssn,
    _is_sssn_store,
    _require_sssn,
)

# The routes that take a body read it themselves, by LLLM's envelope rules
# (see _run_request), so FastAPI cannot infer it from a typed parameter;
# their OpenAPI operations document the envelope instead.
_ENVELOPE_BODY = {
    "requestBody": {
        "content": {"application/json": {"schema": StrategyRunRequest.model_json_schema()}},
    },
}


def create_strategy_app(strategy: Strategy) -> FastAPI:
    """Expose a strategy as a FastAPI application.

    Building the app serves the strategy: it opens the strategy's store, which
    creates the declared channels, and mounts an sssn store (a package store
    included) at ``/network/``. That needs sssn 0.2 or newer: without it, a
    strategy with an sssn store raises ``ImportError``. A store that is not an
    sssn store is not mounted, and needs no sssn.
    """

    from . import __version__

    app = FastAPI(
        title=strategy.name,
        description=strategy.description,
        version=__version__,
    )
    app.state.aaax_strategy = strategy
    # App-wide, so the mounted tactic services and /network/ are covered too.
    app.add_middleware(_CrossSitePostGuard)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
        error = SchemaError(_validation_message(exc.errors()))
        return JSONResponse(status_code=400, content={"detail": _error_payload(error)})

    mounted: set[str] = set()

    @app.exception_handler(404)
    async def not_found(request: Request, exc: StarletteHTTPException) -> Response:
        # A path under /tactics/ that no route or mount of the app matched,
        # for a name no tactic is mounted under, gets the 404 that LLLM's
        # multi-tactic app gives. Routes added to the app later still match.
        name = _unmatched_tactic_name(request)
        if name is not None and name not in mounted:
            return JSONResponse(status_code=404, content={"detail": _tactic_not_found(name)})
        return await http_exception_handler(request, exc)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "strategy": strategy.name}

    @app.get("/strategy")
    async def strategy_info() -> dict[str, Any]:
        return jsonable_encoder(strategy.info())

    @app.get("/resources")
    async def resources() -> list[dict[str, Any]]:
        return jsonable_encoder(strategy.resources)

    @app.get("/packages")
    async def packages() -> list[dict[str, Any]]:
        return [
            jsonable_encoder(resource)
            for resource in strategy.resources
            if resource.kind == "package"
        ]

    @app.get("/tactics")
    async def tactics() -> list[dict[str, Any]]:
        return [
            jsonable_encoder(resource)
            for resource in strategy.resources
            if resource.kind == "tactic"
        ]

    @app.get("/channels")
    async def channels() -> list[dict[str, Any]]:
        return [
            jsonable_encoder(resource)
            for resource in strategy.resources
            if resource.kind == "channel"
        ]

    @app.get("/channels/{name}/events")
    async def query_channel(
        name: str,
        after_cursor: int = 0,
        limit: int = 100,
        kind: str | None = None,
    ) -> dict[str, Any]:
        request = StrategyRunRequest(
            input={
                "op": "query",
                "after_cursor": after_cursor,
                "limit": limit,
                "kind": kind,
            }
        )
        response = await _invoke(strategy, name, request, endpoint="channel")
        return response.model_dump()

    @app.post(
        "/channels/{name}/events",
        response_model=StrategyRunResponse,
        openapi_extra=_ENVELOPE_BODY,
    )
    async def append_channel_event(name: str, request: Request) -> StrategyRunResponse:
        envelope = await _run_request(request)
        if not isinstance(envelope.input, dict):
            # The input holds the event fields; anything else would be dropped.
            error = SchemaError("input must be an object with the event fields")
            raise _http_error(error, endpoint="channel", resource=name, status_code=400)
        envelope = StrategyRunRequest(
            input={**envelope.input, "op": "append"},
            context=envelope.context,
        )
        return await _invoke(strategy, name, envelope, endpoint="channel")

    @app.post("/run", response_model=StrategyRunResponse, openapi_extra=_ENVELOPE_BODY)
    async def run(request: Request) -> StrategyRunResponse:
        envelope = await _run_request(request)
        try:
            output = await strategy.arun(envelope.input, context=envelope.context)
        except StarletteHTTPException:
            raise
        except Exception as exc:
            raise _http_error(exc, endpoint="run") from exc
        return StrategyRunResponse(
            output=jsonable_encoder(output),
            strategy=strategy.name,
        )

    @app.post(
        "/resources/{name}/invoke",
        response_model=StrategyRunResponse,
        openapi_extra=_ENVELOPE_BODY,
    )
    async def invoke_resource(name: str, request: Request) -> StrategyRunResponse:
        """Call a resource's handler.

        A tactic resource runs as ``POST /tactics/{name}/run`` runs it: the
        ``context`` has the shape of a ``CallContext``, the tactic receives
        one, and its errors get the same status codes. Other handlers receive
        the ``context`` as a plain object.
        """

        envelope = await _run_request(request)
        return await _invoke(strategy, name, envelope, endpoint="resource")

    for name, tactic in strategy.tactics().items():
        app.mount(f"/tactics/{name}", create_tactic_app(tactic))
        mounted.add(name)
    if strategy.store is not None and _is_sssn_store(strategy.store):
        _require_sssn()
        from sssn.server import create_app as create_store_app

        strategy.store.open()
        # Mount the StrategyStore itself so channels declared later are created too.
        app.mount("/network", create_store_app(strategy.store))
    elif strategy.store is not None:
        # Another store has no /network/; serving it still creates its channels.
        strategy.store.open()
    return app


class _CrossSitePostGuard:
    """Refuse a cross-site POST that is not JSON: browsers send one unasked.

    A page on another site can make a visitor's browser POST a form or a
    text body to the app, such as one served on 127.0.0.1, with no CORS
    preflight; only JSON bodies are checked against the app's CORS settings
    first. Such a POST carries an ``Origin`` header whose host and port are
    not the ``Host`` header's, or ``Sec-Fetch-Site: cross-site``; unless its
    body is JSON (``application/json`` or ``+json``), it is answered with a
    403 in the services error envelope. Requests without those headers, from
    scripts and servers, pass, and so do other methods: GET and HEAD read,
    and a browser preflights every other method across origins.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] == "POST" and _cross_site_form(scope):
            error = ErrorDetail(
                type="CrossSiteRequestError",
                message=(
                    "A cross-site POST must send JSON (Content-Type: application/json), "
                    "which browsers check with the app's CORS settings first."
                ),
            )
            content = {"detail": ErrorResponse(error=error).model_dump(mode="json")}
            await JSONResponse(status_code=403, content=content)(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _cross_site_form(scope: Scope) -> bool:
    """Whether a request comes from another site with a body that is not JSON."""

    headers = Headers(scope=scope)
    media_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type == "application/json" or media_type.endswith("+json"):
        return False
    if headers.get("sec-fetch-site", "").lower() == "cross-site":
        return True
    origin = headers.get("origin")
    if origin is None:
        return False
    host = _host_and_port(f"{scope.get('scheme', 'http')}://{headers.get('host', '')}")
    return host is None or _host_and_port(origin) != host


def _host_and_port(url: str) -> tuple[str, int | None] | None:
    """The host and port of ``url``, with the scheme's default port; None if it has none."""

    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if not parts.hostname:
        return None  # an Origin of "null", for one
    return parts.hostname, port or {"http": 80, "https": 443}.get(parts.scheme)


async def _run_request(request: Request) -> StrategyRunRequest:
    """The body of a strategy route, read as LLLM's tactic routes read theirs.

    A JSON object whose keys are ``input`` or ``task``, and optionally
    ``context``, is an envelope: its ``input``, or its ``task`` when the
    input is missing or null, is the input. Any other body, an object with
    other keys included, is the input itself; a body that is not JSON is its
    text, and an empty body is ``None``. A malformed envelope, such as one
    whose ``context`` is not an object, is a 400 ``SchemaError``.
    """

    try:
        body = await request.json()
    except Exception:  # not JSON, or empty
        raw = await request.body()
        try:
            body = raw.decode("utf-8") if raw else None
        except UnicodeDecodeError:
            body = raw
    keys = set(body) if isinstance(body, dict) else set()
    if not (keys & {"input", "task"} and keys <= {"input", "task", "context"}):
        return StrategyRunRequest(input=body)
    value = body.get("input")
    try:
        return StrategyRunRequest(
            input=body.get("task") if value is None else value,
            context=body.get("context"),
        )
    except ValidationError as exc:
        error = SchemaError(_validation_message(exc.errors()))
        raise HTTPException(status_code=400, detail=_error_payload(error)) from exc


async def _invoke(
    strategy: Strategy,
    name: str,
    request: StrategyRunRequest,
    *,
    endpoint: str,
) -> StrategyRunResponse:
    try:
        resource = strategy._lookup(name)
    except ResourceNotFoundError as exc:
        # Only this lookup is a 404: the same error raised inside a handler is
        # that handler's failure, since the resource in the URL exists.
        raise _http_error(exc, endpoint=endpoint, resource=name, status_code=404) from exc
    if endpoint == "channel" and resource.kind != "channel":
        # The channel routes serve channels only, so a GET never runs a tactic.
        error = ResourceNotFoundError(f"Strategy channel not found: {name}")
        raise _http_error(error, endpoint=endpoint, resource=name, status_code=404)
    tactic = name in strategy._tactics
    try:
        output = await strategy.invoke_resource(
            name,
            request.input,
            context=request.context,
        )
    except Exception as exc:
        if isinstance(exc, StarletteHTTPException) and not tactic:
            raise  # a tactic's is a 500, as on /tactics/{name}/run
        raise _http_error(exc, endpoint=endpoint, resource=name, tactic=tactic) from exc
    return StrategyRunResponse(
        output=jsonable_encoder(output),
        strategy=strategy.name,
        metadata={"resource": name, "endpoint": endpoint},
    )


def _http_error(
    exc: Exception,
    *,
    endpoint: str,
    resource: str | None = None,
    tactic: bool = False,
    status_code: int | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=_status_code(exc, tactic=tactic) if status_code is None else status_code,
        detail=_error_payload(
            exc,
            endpoint=endpoint,
            metadata={} if resource is None else {"resource": resource},
        ),
    )


def _unmatched_tactic_name(request: Request) -> str | None:
    """The NAME of a ``/tactics/NAME[/...]`` path that no route of the app matched."""

    scope = request.scope
    path, root_path = scope["path"], scope.get("root_path", "")
    if root_path and path.startswith(root_path):  # the app is mounted under root_path
        path = path[len(root_path):]
    found = re.fullmatch(r"/tactics/([^/]+)(?:/.*)?", path, re.DOTALL)
    if found is None:
        return None
    if any(route.matches(scope)[0] is not Match.NONE for route in request.app.router.routes):
        return None  # a route matched and raised the 404 itself
    return found.group(1)


def _tactic_not_found(name: str) -> dict[str, Any]:
    """The 404 detail LLLM's multi-tactic app gives for a tactic it does not serve."""

    message = f"Tactic not found: {name}"
    try:
        error = ErrorDetail(type="TacticNotFound", message=message, tactic=name)
    except ValueError:  # a name LLLM's errors cannot carry, such as one with ";"
        error = ErrorDetail(type="TacticNotFound", message=message)
    return ErrorResponse(error=error).model_dump(mode="json")


def _error_payload(exc: Exception, **fields: Any) -> dict[str, Any]:
    return ErrorResponse(
        error=ErrorDetail(type=type(exc).__name__, message=str(exc), **fields)
    ).model_dump(mode="json")


def _status_code(exc: Exception, *, tactic: bool = False) -> int:
    if tactic:
        # The tactic service's mapping, so both tactic routes agree.
        return status_code_for_error(exc)
    # Store errors exist only once sssn is imported; looking them up here
    # keeps strategies without channels from importing it.
    errors = _imported_sssn("sssn.core.errors")
    if errors is not None and isinstance(exc, errors.NetworkError):
        # The store server's own mapping, so both report a store error alike.
        from sssn.server.fastapi import _http_error as _store_http_error

        return _store_http_error(exc).status_code
    client = _imported_sssn("sssn.client.http")
    if (
        client is not None
        and isinstance(exc, client.RemoteStoreError)
        and 400 <= exc.status_code < 500
    ):
        # A remote store's server already mapped the store error.
        return exc.status_code
    if isinstance(exc, (ValueError, SchemaError, TacticUnsupportedError)):
        return 400
    return 500


def _validation_message(errors: Sequence[Mapping[str, Any]]) -> str:
    messages = []
    for error in errors:
        location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
        message = str(error.get("msg") or "Invalid request.")
        messages.append(f"{location}: {message}" if location else message)
    return "; ".join(messages) or "Invalid request."
