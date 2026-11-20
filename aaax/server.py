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
not an object. A tactic resource fails with the status
``POST /tactics/<name>/run`` uses, LLLM's ``status_code_for_error``. The
runner and other handlers keep the status of an ``HTTPException`` they raise;
a ``ValueError`` or ``SchemaError`` is a 400, except an ``OutputSchemaError``
(lllm-core 0.4.1), a 500; channel store errors keep the store server's codes
(404 not found, 409 conflict, 400 otherwise), and a remote store's 4xx errors
keep the code its server returned; anything else is a 500, including a
resource lookup that fails inside a handler.

The app refuses, with a 403 ``CrossSiteRequestError``, the cross-site
requests a browser sends for any web page without asking first: a POST whose
body is not JSON, on every route, and a GET or HEAD to a mounted tactic's
custom endpoints, which run its code (its built-in read routes stay open).
``Sec-Fetch-Site`` decides whether a request is cross-site when it is
present; otherwise ``Origin`` is compared with ``Host``. PUT, PATCH, and
DELETE are never refused. ``create_strategy_app(...,
allow_cross_site_requests=True)`` serves both kinds.
"""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

import lllm.protocol
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

def _envelope_schema() -> dict[str, Any]:
    """StrategyRunRequest's schema, encoded as FastAPI encodes the schemas it
    generates, with ``task``, which the routes take in place of ``input``."""

    schema = jsonable_encoder(StrategyRunRequest.model_json_schema(), exclude_none=True)
    properties = schema["properties"]
    schema["properties"] = {
        "input": properties["input"],
        "task": {"title": "Task", "description": "The input, when input is missing or null."},
        "context": properties["context"],
    }
    return schema


# The routes that take a body read it themselves, by LLLM's envelope rules
# (see _run_request), so FastAPI cannot document it from a typed parameter.
# Their operations carry the schema inline, so any document built from the
# app's routes is complete; the app's own document names it
# StrategyRunRequest, as AAAX 0.3 did (see _document_envelope).
_ENVELOPE_PATHS = ("/run", "/resources/{name}/invoke", "/channels/{name}/events")
_ENVELOPE_BODY = {
    "requestBody": {
        "required": True,
        "content": {"application/json": {"schema": _envelope_schema()}},
    },
}


def create_strategy_app(
    strategy: Strategy,
    *,
    allow_cross_site_requests: bool = False,
) -> FastAPI:
    """Expose a strategy as a FastAPI application.

    Building the app serves the strategy: it opens the strategy's store, which
    creates the declared channels, and mounts an sssn store (a package store
    included) at ``/network/``. That needs sssn 0.2 or newer: without it, a
    strategy with an sssn store raises ``ImportError``. A store that is not an
    sssn store is not mounted, and needs no sssn.

    A tactic named with ``{`` or ``}``, which can mark parameters in
    routes, cannot be served: building the app raises ``ValueError``.

    The app refuses the cross-site requests a page on another site can make
    a visitor's browser send without asking first: a POST whose body is not
    JSON, and a GET or HEAD to a mounted tactic's custom endpoints, which
    run its code. ``allow_cross_site_requests=True`` serves them, for an app
    that browsers on other origins must reach; it is passed on to LLLM's
    tactic services when they take it.
    """

    if not isinstance(allow_cross_site_requests, bool):
        raise TypeError("allow_cross_site_requests must be a boolean.")
    for name in strategy._tactics:
        # Checked here, not when the tactic is added, so a package that
        # declares one can still be inspected.
        if "{" in name or "}" in name:
            raise ValueError(
                f"Tactic {name!r} cannot be served: '{{' and '}}' can mark parameters "
                "in routes, so a served tactic's name cannot hold them; rename it."
            )
    from . import __version__

    app = FastAPI(
        title=strategy.name,
        description=strategy.description,
        version=__version__,
    )
    app.state.aaax_strategy = strategy
    mounted: set[str] = set()
    if not allow_cross_site_requests:
        # App-wide, so the mounted tactic services and /network/ are covered too.
        app.add_middleware(_CrossSiteGuard, tactics=mounted)
    _document_envelope(app)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
        error = SchemaError(_validation_message(exc.errors()))
        return JSONResponse(status_code=400, content={"detail": _error_payload(error)})

    not_found = app.router.default

    async def tactic_not_found(scope: Scope, receive: Receive, send: Send) -> None:
        # The router calls this when no route or mount of the app matched
        # (routes added to the app later included). A path under /tactics/
        # for a name no tactic is mounted under gets the 404 that LLLM's
        # multi-tactic app raises; any other goes on to Starlette's
        # not_found. Both raise the 404 to the app's exception handlers, as
        # Starlette's not_found does inside an app.
        if scope["type"] == "http":
            found = re.fullmatch(r"/tactics/([^/]+)(?:/.*)?", _route_path(scope), re.DOTALL)
            if found is not None and found.group(1) not in mounted:
                detail = _tactic_not_found(found.group(1))
                if "app" in scope:
                    raise HTTPException(status_code=404, detail=detail)
                response = JSONResponse(status_code=404, content={"detail": detail})
                await response(scope, receive, send)
                return
        await not_found(scope, receive, send)

    app.router.default = tactic_not_found

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
        return await _invoke(strategy, name, request, endpoint="channel")

    @app.post(
        "/channels/{name}/events",
        response_model=StrategyRunResponse,
        openapi_extra=_ENVELOPE_BODY,
    )
    async def append_channel_event(name: str, request: Request) -> JSONResponse:
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
    async def run(request: Request) -> JSONResponse:
        envelope = await _run_request(request)
        try:
            output = await strategy.arun(envelope.input, context=envelope.context)
        except StarletteHTTPException:
            raise
        except Exception as exc:
            raise _http_error(exc, endpoint="run") from exc
        return _reply(strategy, output, endpoint="run")

    @app.post(
        "/resources/{name}/invoke",
        response_model=StrategyRunResponse,
        openapi_extra=_ENVELOPE_BODY,
    )
    async def invoke_resource(name: str, request: Request) -> JSONResponse:
        """Call a resource's handler.

        A tactic resource runs as ``POST /tactics/{name}/run`` runs it: the
        ``context`` has the shape of a ``CallContext``, the tactic receives
        one, and its errors get the same status codes. Other handlers receive
        the ``context`` as a plain object.
        """

        envelope = await _run_request(request)
        return await _invoke(strategy, name, envelope, endpoint="resource")

    for name, tactic in strategy.tactics().items():
        app.mount(f"/tactics/{name}", _tactic_app(tactic, allow_cross_site_requests))
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


def _document_envelope(app: FastAPI) -> None:
    """Name the envelope schema StrategyRunRequest in ``app``'s OpenAPI document.

    The envelope routes' operations carry the schema inline; the app's
    document moves it into a ``StrategyRunRequest`` component and points
    them at it, as LLLM's ``_document_tactic_schemas`` patches a tactic's.
    """

    generate_openapi = app.openapi
    ref = {"$ref": "#/components/schemas/StrategyRunRequest"}

    def openapi() -> dict[str, Any]:
        document = generate_openapi()
        schemas = document.setdefault("components", {}).setdefault("schemas", {})
        if "StrategyRunRequest" not in schemas:
            schemas["StrategyRunRequest"] = _envelope_schema()
            for path in _ENVELOPE_PATHS:
                operation = document.get("paths", {}).get(path, {}).get("post", {})
                content = operation.get("requestBody", {}).get("content", {})
                if "application/json" in content:
                    content["application/json"]["schema"] = dict(ref)
        return document

    app.openapi = openapi  # type: ignore[method-assign]


def _tactic_app(tactic: Any, allow_cross_site_requests: bool) -> Any:
    """LLLM's service for ``tactic``, passing the cross-site switch on when it takes one."""

    if allow_cross_site_requests and "allow_cross_site_requests" in (
        inspect.signature(create_tactic_app).parameters
    ):
        return create_tactic_app(tactic, allow_cross_site_requests=True)
    return create_tactic_app(tactic)


# The GET routes of a mounted tactic service that only read (its info,
# health, and docs), as paths under /tactics/NAME; every other GET or HEAD
# there reaches a custom endpoint, which runs the tactic's code.
_TACTIC_READ_ROUTES = re.compile(
    r"/?|/info|/health|/tactics|/tactics/[^/]+/info|/docs|/docs/oauth2-redirect|/redoc"
    r"|/openapi\.json"
)


class _CrossSiteGuard:
    """Refuse the cross-site requests a browser sends for any web page, unasked.

    A page on another site can make a visitor's browser send a form or a
    text body, or a GET, to any address, a server on 127.0.0.1 included,
    without a CORS preflight. A request is cross-site when its
    ``Sec-Fetch-Site`` says ``cross-site`` or ``same-site``; without that
    header, when its ``Origin`` is ``null``, not http(s), or names another
    host and port than its ``Host`` (each port defaulting from the Origin's
    scheme). Such a request is answered with a 403 ``CrossSiteRequestError``
    in the services error envelope when it is a POST whose body is not JSON
    (``application/json`` or ``+json``), or a GET or HEAD to a custom
    endpoint of a mounted tactic: any path under ``/tactics/NAME/`` but its
    built-in read routes. Nothing else is refused: browsers preflight PUT,
    PATCH, and DELETE across origins, so the app's CORS settings decide them.
    """

    def __init__(self, app: ASGIApp, *, tactics: set[str]) -> None:
        self.app = app
        self.tactics = tactics  # the names of the mounted tactics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        message = self._refusal(scope) if scope["type"] == "http" else None
        if message is None:
            await self.app(scope, receive, send)
            return
        error = ErrorDetail(type="CrossSiteRequestError", message=message)
        content = {"detail": ErrorResponse(error=error).model_dump(mode="json")}
        await JSONResponse(status_code=403, content=content)(scope, receive, send)

    def _refusal(self, scope: Scope) -> str | None:
        """Why the request is refused, or None to serve it."""

        method = scope["method"]
        headers = Headers(scope=scope)
        if method == "POST":
            media_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if media_type == "application/json" or media_type.endswith("+json"):
                return None
            if _is_cross_site(headers):
                return (
                    "A cross-site POST must send JSON (Content-Type: application/json), "
                    "which browsers check with the app's CORS settings first."
                )
            return None
        if method in ("GET", "HEAD"):
            found = re.fullmatch(r"/tactics/([^/]+)(/.*)", _route_path(scope), re.DOTALL)
            if (
                found is not None
                and found.group(1) in self.tactics
                and _TACTIC_READ_ROUTES.fullmatch(found.group(2)) is None
                and _is_cross_site(headers)
            ):
                return (
                    "A cross-site GET or HEAD cannot reach a tactic's custom endpoint, "
                    "which runs its code: call it from the app's own origin."
                )
        return None


def _is_cross_site(headers: Headers) -> bool:
    """Whether a browser sent the request for a page on another site.

    ``Sec-Fetch-Site`` decides when the browser sends it, even where a proxy
    rewrites ``Host``. Otherwise ``Origin`` is compared with ``Host``, a
    missing port defaulting from the Origin's scheme, the scheme the page
    used, which a proxy that terminates TLS hides from the app. A request
    with neither header is not from a browser.
    """

    site = headers.get("sec-fetch-site")
    if site is not None:
        return site.strip().lower() not in ("same-origin", "none")
    origin = headers.get("origin")
    if origin is None:
        return False
    host = headers.get("host")
    try:
        source = urlsplit(origin)
        target = urlsplit(f"//{host}") if host else None
        if (
            source.scheme not in ("http", "https")
            or not source.hostname
            or target is None
            or not target.hostname
        ):
            return True  # an Origin of "null", or nothing to compare it with
        default = 443 if source.scheme == "https" else 80
        return (source.hostname, source.port or default) != (
            target.hostname,
            target.port or default,
        )
    except ValueError:  # a malformed host or port
        return True


def _route_path(scope: Scope) -> str:
    """The request path within the app, without the prefix it is mounted under."""

    path, root_path = scope["path"], scope.get("root_path", "")
    if root_path and path.startswith(root_path):
        return path[len(root_path):]
    return path


async def _run_request(request: Request) -> StrategyRunRequest:
    """The body of a strategy route, read as LLLM's tactic routes read theirs.

    A JSON object whose keys are ``input`` or ``task``, and optionally
    ``context``, is an envelope: its ``input``, or its ``task`` when the
    input is missing or null, is the input. Any other body, an object with
    other keys included, is the input itself; a body that is not JSON is its
    text, and an empty body is ``None``. The body is decoded strictly as
    UTF-8: one that is not UTF-8 is the input as bytes when its content type
    is ``application/octet-stream``, and a 400 ``SchemaError`` otherwise, as
    is a body whose first value is an array or object nested more than 500
    levels deep (brackets in strings aside), and a malformed envelope, such
    as one whose ``context`` is not an object.
    LLLM's tactic routes read bodies so from lllm-core 0.4.1. With 0.4.0,
    they parse JSON in any UTF encoding (UTF-16 and UTF-32 included, and
    UTF-8-encoded surrogates pass through) and take any other body that is
    not UTF-8 as bytes.
    """

    raw = await request.body()
    content_type = request.headers.get("content-type", "")
    try:
        # In a worker thread: decoding, scanning, and parsing a big body take
        # a while, and the event loop serves other requests meanwhile.
        body = await run_in_threadpool(_body_value, raw, content_type)
    except SchemaError as exc:
        raise HTTPException(status_code=400, detail=_error_payload(exc)) from exc
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


def _body_value(raw: bytes, content_type: str) -> Any:
    """What a request body holds, before any envelope in it is read.

    The body is decoded strictly as UTF-8, unlike json.loads(bytes), which
    lets UTF-8-encoded surrogates through to fail when the reply is encoded;
    then it is the JSON it parses as, or else its text, or None when empty.
    One that is not UTF-8 is bytes for ``application/octet-stream``, and a
    ``SchemaError`` otherwise, as is one whose first value is an array or
    object nested more than 500 levels deep (brackets in strings aside).
    The depth is checked before json.loads, so json.loads never recurses
    deeply in the worker thread this runs in.
    """

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        if content_type.split(";", 1)[0].strip().lower() != "application/octet-stream":
            raise SchemaError("The request body must be JSON or UTF-8 text.") from exc
        return raw  # bytes, as LLLM's tactic routes pass such a body
    if _nested_too_deep(text):
        raise _too_deep_error()
    try:
        # A UTF-8 byte order mark is allowed before JSON, as json.loads allows it.
        return json.loads(text.removeprefix("\ufeff"))
    except RecursionError as exc:
        raise _too_deep_error() from exc
    except ValueError:
        return text or None  # not JSON: the text, or None for an empty body


# How deep a body's first value, if it is an array or object, may nest
# (brackets in strings aside). A body whose first value is nested deeper is
# refused before it is parsed: code that walks such a value recursively, as
# a native tactic's repr() of its task does in a worker thread, can overflow
# a small thread stack and crash the process.
_MAX_JSON_DEPTH = 500
_JSON_STRUCTURE = re.compile(r'[\[\]{}"\\]')
# A body json.loads would recurse into: an array or object first, after an
# optional byte order mark and JSON whitespace.
_JSON_CONTAINER_FIRST = re.compile(r"\ufeff?[ \t\n\r]*[\[{]")


def _nested_too_deep(text: str) -> bool:
    """Whether json.loads would recurse into ``text`` more than ``_MAX_JSON_DEPTH`` deep.

    json.loads recurses only into a first value that is an array or an
    object, and refuses anything after that value, so the scan starts at
    that value's first bracket and ends where it closes. The brackets
    outside strings are counted one at a time, so the scan never recurses,
    and a body that is not valid JSON is judged the same way.
    """

    first = _JSON_CONTAINER_FIRST.match(text)
    if first is None or text.count("[") + text.count("{") <= _MAX_JSON_DEPTH:
        return False
    depth = 0
    in_string = False
    escaped_at = -1  # the position of a character a backslash escapes
    for match in _JSON_STRUCTURE.finditer(text, first.end() - 1):
        position, char = match.start(), match.group()
        if position == escaped_at:
            continue
        if in_string:
            if char == "\\":
                escaped_at = position + 1
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            if depth > _MAX_JSON_DEPTH:
                return True
        elif char in "]}":
            depth -= 1
            if depth == 0:
                return False  # the first value closed
    return False


def _too_deep_error() -> SchemaError:
    return SchemaError(f"Request body is nested more than {_MAX_JSON_DEPTH} levels deep.")


async def _invoke(
    strategy: Strategy,
    name: str,
    request: StrategyRunRequest,
    *,
    endpoint: str,
) -> JSONResponse:
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
    return _reply(strategy, output, endpoint=endpoint, resource=name)


def _reply(
    strategy: Strategy,
    output: Any,
    *,
    endpoint: str,
    resource: str | None = None,
) -> JSONResponse:
    """A route's ``StrategyRunResponse``, encoded here, not after the route returns.

    So a reply that cannot be encoded, such as bytes that are not UTF-8 or
    a string with a lone surrogate, is a 500 in the services error envelope
    rather than a bare 500.
    """

    metadata = {} if resource is None else {"resource": resource, "endpoint": endpoint}
    try:
        reply = StrategyRunResponse(
            output=jsonable_encoder(output),
            strategy=strategy.name,
            metadata=metadata,
        )
        return JSONResponse(reply.model_dump(mode="json"))
    except Exception as exc:
        raise _http_error(exc, endpoint=endpoint, resource=resource, status_code=500) from exc


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
    # lllm-core 0.4.1 raises OutputSchemaError, a SchemaError, for a result
    # that fails its output schema: a bug in the code, which its services
    # answer with 500. Looked up here, since lllm-core 0.4.0 has none.
    output_error = getattr(lllm.protocol, "OutputSchemaError", None)
    if output_error is not None and isinstance(exc, output_error):
        return 500
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
