# Changelog

## 0.3.1

A bug-fix release, with the few additions its fixes need:
`create_strategy_app(..., allow_cross_site_requests=...)`, four API-key
options on `aaax serve`, and the `ResourceNotFoundError` export. It still
works with lllm-core 0.4.0 and SSSN 0.2.0. Some fixes refuse requests that
0.3.0 served or answer them differently, and `aaax serve` now checks API
keys before it starts; each bullet says what changed and, where you need
to act, what to do.

**The strategy's routes**

- `/run`, `/resources/<name>/invoke`, and `/channels/<name>/events` read a
  body by the envelope rules of LLLM's tactic routes. An object whose keys
  are `input` or `task` (used when `input` is missing or `null`), and
  optionally `context`, is the envelope; any other body is the input
  itself, a body that is not JSON is its text, and an empty body is the
  input `None`.
- So some bodies are read differently from 0.3.0, which took a JSON
  object sent as JSON for the envelope and refused any other body with
  a 400. An object that is not an envelope, such as `{"text": "Hi"}`,
  `{}`, `{"context": {...}}`, or `{"input": 1, "note": "x"}`, is now the
  input itself (on `/channels/<name>/events`, the event's fields), where
  0.3.0 took its `input` (or `None`) and `context` and dropped any other
  key. An envelope with `task`, such as `{"task": "Hi"}` or
  `{"input": null, "task": "Hi"}`, now runs with the task as the input,
  where 0.3.0 dropped `task` and ran with `None`. Send an envelope with
  nothing but `input` and `context` to be read as before.
- On `/run` and `/resources/<name>/invoke`, bodies that 0.3.0 refused with
  a 400 are now the input: any other JSON value (a string, number,
  boolean, `null`, or array), text (a form body or malformed JSON
  included), and an empty body. JSON is read as JSON whatever the content
  type, so `{"input": 5}` sent as `text/plain` or as a form (as `curl -d`
  sends it), which 0.3.0 refused, runs with `5`. On
  `/channels/<name>/events` a body that is not an object is still a 400,
  since an event must be an object, now with the message "input must be an
  object with the event fields".
- Bodies are decoded strictly as UTF-8. One that is not UTF-8 is the input
  as `bytes` when its content type is `application/octet-stream`, where
  0.3.0 refused it, and otherwise a 400 `SchemaError` ("The request body
  must be JSON or UTF-8 text.") in the services error envelope, not
  FastAPI's bare `{"detail": ...}` that 0.3.0 gave some of them. JSON sent
  in UTF-16 or UTF-32, which 0.3.0 parsed, is no longer read as JSON: with
  a byte order mark it is that 400, and without one it usually arrives as
  text full of NUL characters. Send UTF-8; a UTF-8 byte order mark before
  JSON is still allowed.
- A body that begins with an array or object nested more than 500 levels
  deep (brackets in strings aside) is now a 400 `SchemaError` ("Request
  body is nested more than 500 levels deep."), whatever its content type
  and whether or not the rest parses: code that walks such a value
  recursively can crash the server. With lllm-core 0.4.0, the routes under
  `/tactics/` still lack this limit; lllm-core 0.4.1 adds it.
- Bodies are decoded, checked, and parsed in a worker thread, so other
  requests are served while a large body is parsed.
- A reply that cannot be encoded, such as bytes that are not UTF-8 or a
  string with a lone surrogate, is a 500 in the services error envelope
  instead of a bare `text/plain` 500.
- With lllm-core 0.4.1 or newer, an `OutputSchemaError` from the runner or
  a handler (a result that fails its output schema) is a 500, as on the
  tactic routes, not a 400.
- In the OpenAPI document, `StrategyRunRequest` documents `task`, and the
  three routes still point at it with `"required": true`; `POST /run` no
  longer lists a 422 response, which the app never sends. A document built
  from `app.routes` another way, such as FastAPI's `get_openapi`, carries
  the schema inline in each operation.

**Cross-site requests**

- The app refuses, with a 403 `CrossSiteRequestError` in the services error
  envelope, the cross-site requests a web page can make a visitor's browser
  send without a CORS preflight: on any route, a POST whose `Content-Type`
  is not JSON (`application/json` or a `+json` type), a POST with no body
  included; and a GET or HEAD to a mounted tactic's custom endpoint, which
  runs its code (any path under `/tactics/<name>/` but the service's read
  routes: `info`, `health`, `tactics`, `tactics/<name>/info`, the docs
  pages, and `openapi.json`). 0.3.0 had no such check: it ran a cross-site
  form or text POST to a tactic's `run`, `stream`, or custom POST
  endpoint, to SSSN routes under `/network/` that take no body (such as
  `POST /network/subscriptions/<id>/pull`, which advances the
  subscription), and to POST routes you added that take no JSON, and a
  cross-site GET to a custom endpoint. Send JSON, or call from the app's
  own origin.
- `Sec-Fetch-Site` decides when a request carries it: any value but
  `same-origin` and `none` is cross-site. Without it, a request is
  cross-site when its `Origin` is `null`, is not http(s), or names another
  host and port than `Host`, or when there is no `Host` to compare it with.
  Scripts and servers send neither header and are not affected. PUT,
  PATCH, and DELETE are never refused: browsers preflight them, so the
  app's CORS settings decide.
- `create_strategy_app(strategy, allow_cross_site_requests=True)` leaves
  the guard out, for an app that browsers on other origins must reach, and
  passes the switch on to LLLM's `create_tactic_app` when it takes one. The
  value must be a `bool`; anything else raises `TypeError`. `aaax serve`
  always keeps the guard.
- The guard does not stop DNS rebinding. A local app also needs a host
  allowlist, such as Starlette's `TrustedHostMiddleware` with `localhost`
  and `127.0.0.1`, or a token.

**Tactic routes**

- A mounted tactic is served under its local name. The `tactic` field of
  the tactic's replies and errors under `/tactics/<name>/`, and the `name`
  on `/info`, are `<name>`, also for a tactic renamed with
  `add_tactic(..., name=...)` or under a package prefix:
  `/tactics/support.triage/run` answers `"tactic": "support.triage"`,
  where 0.3.0 gave the tactic's own name. The service's `/health`, nested
  `/tactics/...` routes, and OpenAPI title use `<name>` too, so for a
  renamed tactic `/tactics/<name>/tactics/<own name>/run`, which 0.3.0
  served, is now a 404; call `/tactics/<name>/run`. A local name with
  `;`, which LLLM's tactic names cannot hold, keeps the tactic's own name.
- The `description` and `ref` a tactic is mounted with, by `add_tactic`,
  `strategy.tactic(name, handler=...)`, or `add_resource` with a tactic
  record, now reach the served tactic: `/info` gives the description, and
  the ref as `package_ref`, and requests on both `/tactics/<name>/run` and
  `/resources/<name>/invoke` carry the ref as the `CallContext`'s
  `tactic_ref`. A ref that is not a tactic ref
  (`lllm://org/package/tactics/name`) labels only the record.
- A tactic served under a name, description, or ref other than its own, a
  package tactic included, is a copy that has them: its code sees them as
  `self.tactic_name`, `self.package_ref`, and `self.info()` wherever the
  strategy runs it, and `strategy.tactics()` returns the copy, so a
  package tactic there is named after its local name, such as
  `support.triage`. The tactic you passed in, or the object a package's
  code made, is left as it is.
- A package tactic's `/info` takes the manifest's `description` and
  `examples` when its code has none.
- A name under `/tactics/` that no tactic is mounted under, such as a
  tactic declared without a handler, is now a 404 with LLLM's
  `TacticNotFound` error envelope (`Tactic not found: <name>`), as LLLM's
  multi-tactic app answers, instead of Starlette's plain
  `{"detail": "Not Found"}`. It is raised as an `HTTPException`, so the
  app's exception handlers still see it.
- A tactic whose name has `{` or `}` cannot be served, since Starlette can
  read braces in a route as a path parameter: 0.3.0 built such an app and
  also served `a{b}` at `/tactics/aXYZ/`. Now `create_strategy_app` raises
  `ValueError` naming it, and `aaax serve` stops with exit status 2.
  `aaax inspect` still lists it; rename it to serve it.
- `aaax serve` and `aaax launch` report any `ValueError` raised while they
  build the app as a usage error with exit status 2, such as LLLM's
  refusal of a custom endpoint that clashes with a built-in route; 0.3.0
  printed a traceback.
- A plain function mounted under a name with `;` is served at
  `/tactics/<name>/` and answers under the function's own name; with
  0.3.0, the app failed to build.

**Strategies and packages**

- While a strategy file loads (its top level and `build_strategy()`,
  helper code they call included), a relative package path given to
  `use_package`, `add_package`, or `strategy_from_package` is relative to
  the file's folder, so the file works from any working directory. Other
  relative paths, such as `store=`, and package paths in a
  `module:attribute` target stay relative to the working directory.
- 0.3.0 resolved those package paths against the working directory, and
  such files still load. A place counts only if it holds a manifest (the
  path is a manifest file, or a folder with an `lllm.toml`). When only the
  working directory holds one, or the two places hold different manifest
  files (two copies of one package included), the working directory's
  loads, with a `FutureWarning` that names the paths: a future minor
  release looks in the file's folder only, so make the path relative to
  the file's folder, or absolute. When neither holds one, the error names
  the path in the file's folder.
- `strategy.tactic(name, handler=...)` without a description now describes
  the record with the function's docstring, or with a tactic object's own
  description, as `add_tactic` does; 0.3.0 left it empty.
- `Strategy` subclasses that override `add_resource` now see the channels
  a package adds, which 0.3.0 added past it.
- `ResourceNotFoundError`, which `invoke_resource` raises for an unknown
  name, is exported from `aaax`.

**API keys**

- `aaax serve` and `aaax launch`, also as `lllm shell serve` and
  `lllm shell launch`, check the API keys of each package the strategy
  binds (a package target, or a package mounted with `bind=True`, the
  default) before they build the app: the keys `lllm serve` checks for the
  package, plus those each of its tactics declares. When the environment
  has them all, nothing else is read. Otherwise a key also counts when it
  is in the env file or the OS keyring, where `lllm setup` stores keys,
  and is put in the server's environment.
- Missing keys stop the command. Without a terminal, it exits with status
  2, naming the keys and the commands that store them: `lllm setup PATH`
  for the keys `lllm serve` checks (the package's, and those of the
  resource it would launch), and `lllm setup PATH --resource tactics.NAME`
  for a key that only its other tactics declare. In a terminal, it asks for
  them and stores them as `lllm setup` does. A package whose key
  declarations LLLM cannot read, such as a key name that is not uppercase,
  stops the command too. 0.3.0 started without checking: set the keys (or
  fix the declarations), or pass `--skip-key-check`.
- The options are `lllm serve`'s: `--env-file` (default `.env.local`),
  `--no-keyring`, `--credentials auto|keyring|env` (where keys typed in are
  stored), and `--skip-key-check`. `--no-keyring` with
  `--credentials keyring` is refused, even with `--skip-key-check`; under
  `--no-keyring`, keys typed in go to the env file.
- The env file is checked only when a key is missing from the environment.
  Then an unreadable default `.env.local`, a symlink included, counts as
  absent: the error for missing keys says why, and keys that would have to
  be stored there are not asked for. A file named with `--env-file` must be
  a regular file you can read, not a symlink (even a broken one), or the
  command stops before it asks for anything; one that does not exist yet
  is created when keys are stored in it. `~` and `~user` are expanded, also
  in `--env-file=~/...`; one that cannot be expanded, such as `~` and a
  user name Linux or macOS does not know, is a usage error (`./~name` reads
  as `~name`, so name such a file by its absolute path).
- A package mounted with `bind=False` runs no code, so its keys are not
  checked, and an app you build with `create_strategy_app` is not checked.

**Docs**

- Serving has an API keys section and covers the cross-site guard, DNS
  rebinding (with a tested `TrustedHostMiddleware` example), the body
  rules, and the new status codes; the CLI and HTTP API references match.
  Strategies drops the `Path(__file__).parent` workaround for package
  paths, and the naming rules say to leave `;`, `{`, and `}` out of tactic
  names.
- The docs follow LLLM's layout: Get started, Guide, Examples, and API
  reference. Every Python example is run by the tests, the Python API page
  is generated from the docstrings (the `docs` extra adds
  `mkdocstrings[python]`), and the old pages' addresses redirect to the new
  ones.

## 0.3.0

AAAX is its own package again, now built on LLLM. LLLM 0.3 carried this code
as `lllm.shell`; AAAX 0.3 is that code, improved there, back under the `aaax`
name. It depends on `lllm-core` (0.4 or newer) for tactics, services, refs,
and package manifests, and plugs into the `lllm` command.

**LLLM integration**

- `aaax` depends on `lllm-core[server]>=0.4`, which brings FastAPI and
  Uvicorn; `pip install "lllm-core[shell]"` installs it from the LLLM side.
  PsiHub is gone, and with it the `packages`, `tactics`, and `integrations`
  extras. `aaax[channels]` adds SSSN (`sssn>=0.2`).
- Installing `aaax` adds `lllm shell` through the `lllm.commands` entry
  point; it is the same CLI as `aaax`, which stays, and `python -m aaax`
  works. Usage and error messages name the command that ran. `--version` and
  the app's OpenAPI document report the AAAX version.
- Every tactic resource is an LLLM tactic, mounted with LLLM's
  `create_tactic_app` at `/tactics/<name>/`: `run`, `stream`, `info`, and
  custom endpoints, with the services request and error envelopes.
  `Strategy.add_tactic` mounts an LLLM tactic, and `strategy.tactics()`
  returns the tactic resources as LLLM tactics (plain functions are wrapped
  with `lllm.as_tactic`).
- Packages are LLLM packages: `lllm.toml` manifests, in a folder or fetched
  from the LLLM hub, with `lllm://` refs. Package tactics load lazily with
  LLLM's `coerce_tactic`, the rule `lllm serve` uses, and report their
  manifest ref as their `package_ref`.
- The old `lllm.shell` import path is a deprecated alias in LLLM 0.4 that
  imports `aaax`; import `aaax` instead. In a directory, the loader looks
  for `strategy.py`, then `shell.py`, the strategy file `lllm shell` loaded.
- `aaax.py`, the other strategy file name AAAX 0.2 loaded, is deprecated: in
  its folder it shadows the `aaax` package, so `lllm shell` and
  `python -m aaax` fail there. It still loads, after `shell.py`, with a
  `FutureWarning` that says to rename it to `strategy.py`.

**Channels**

- Channel stores come from SSSN, imported only where a store is used.
  Without `sssn`, everything but the store works, and using the store
  raises `ImportError: Channel stores need the sssn package: pip install
  sssn` (`aaax serve` reports it as a usage error); with an `sssn` older
  than 0.2, it raises `ImportError: aaax needs sssn>=0.2: pip install -U
  'aaax[channels]'`. A store that is not an SSSN store works without SSSN,
  and so does serving the strategy: only an SSSN store is mounted at
  `/network/`.
- A strategy has one channel store, `strategy.store`; an SSSN store is
  served with SSSN's store API at `/network/`. Every channel resource
  without a handler, from a package or from `strategy.channel()`, is backed
  by the store channel of the same name. `attach_store()` sets the store;
  attaching a different one raises `ValueError` instead of replacing it.
  Packages share it: the first package with channels gives the strategy its
  store, at `store=` or `<package>/.lllm/network`, and its channels are
  created under their prefixed names.
- The store is opened, and its channels created, on first use: when the
  app is built or a channel is used, never while building or inspecting a
  strategy.
- Events appended without a `source` say `aaax`.

**Shell routes and strategies**

- On the tactic routes, and for tactic resources on
  `/resources/<name>/invoke`, the request context has the shape of an LLLM
  `CallContext`: send your own values in `metadata`, since keys that are
  not `CallContext` fields are dropped. The runner and other handlers still
  get a plain dict.
- Errors use LLLM's services error envelope. A missing resource is a 404, a
  malformed request is a 400, and so is an appended event whose `input` is
  not an object (it used to become `{}`); store errors keep the store's
  codes, and other failures are 500s instead of propagating. A lookup that
  fails inside a handler is a 500, not a 404.
- The `/channels/` routes serve channel resources only, so a `GET` never
  runs a tactic.
- Strategy names follow the resource name rule (`Strategy("My Strategy")`
  raises `ValueError`), and a package whose names clash with resources
  already in the strategy is rejected before anything is added.
- Handlers that take no input, or only keyword arguments, are called
  without the input.

**Renamed and changed**

| AAAX 0.2 | AAAX 0.3 |
| --- | --- |
| `psi.toml`, with `psi_version` | `lllm.toml`, with `manifest_version` (optional) |
| `psi://` refs | `lllm://` refs |
| a strategy file named `aaax.py` | `strategy.py` (`aaax.py` loads with a `FutureWarning`) |
| one channel store per package, `<package>/.sssn` | one store per strategy, `<package>/.lllm/network` by default |
| `"context": {"request": "demo"}` on `/tactics/<name>/run` | `"context": {"metadata": {"request": "demo"}}` |
| `/tactics/<name>/run` answers `{"output", "strategy", "metadata"}` | `{"output", "request_id", "tactic"}`, LLLM's service envelope |
| `aaax[packages]`, `aaax[tactics]`, `aaax[integrations]` | `aaax` (LLLM included) and `aaax[channels]` |
| plain-Python tactics without LLLM | every tactic is an LLLM tactic |

To keep a 0.2 package's events, move `<package>/.sssn/sssn.sqlite` to
`<package>/.lllm/network/network.sqlite` and `.sssn/artifacts/` to
`.lllm/network/artifacts/`, the SSSN 0.2 layout.

**Docs**

- aaax.one is AAAX's own site again, deployed to Firebase Hosting. The
  header switches between LLLM, SSSN, and AAAX, the nav has no Home section
  (the logo leads home), and a new "Use with LLLM" page covers LLLM tactics
  and packages, the LLLM hub, channels through SSSN, `lllm shell`, and
  calling a served tactic by ref.
- The PsiHub Packages page is LLLM Packages, at `/composition/packages/`;
  its old address, `/composition/psihub-packages/`, redirects there.

## 0.2.2

- Shipped the AAAX logos in the source release.
- Docs: the shell surfaces (CLI, FastAPI, and agentic), the cross-doc
  switcher, and the shared typography of the family's sites.

## 0.2.1

- Included the docs and tutorials in the source release.

## 0.2.0

- Remade AAAX around strategies: a `Strategy` is a resource table with
  local handlers, served as FastAPI and inspected or served with the `aaax`
  command.
- Mounted packages into strategies, with optional tactic, channel, and
  package bridges.
- Added the aaax.one documentation site.
