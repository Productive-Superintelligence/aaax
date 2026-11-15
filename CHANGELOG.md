# Changelog

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
  imports `aaax`; import `aaax` instead. The loader still finds a
  directory's `shell.py`, the strategy file `lllm shell` loaded, after
  `strategy.py` and `aaax.py`.

**Channels**

- Channel stores come from SSSN, imported only where a store is used.
  Without `sssn`, everything but the store works, and using the store
  raises `ImportError: Channel stores need the sssn package: pip install
  sssn` (`aaax serve` reports it as a usage error). A store that is not an
  SSSN store works without SSSN.
- A strategy has one channel store, `strategy.store`, served with SSSN's
  store API at `/network/`. Every channel resource without a handler, from a
  package or from `strategy.channel()`, is backed by the store channel of
  the same name. `attach_store()` sets the store; attaching a different one
  raises `ValueError` instead of replacing it. Packages share it: the first
  package with channels gives the strategy its store, at `store=` or
  `<package>/.lllm/network`, and its channels are created under their
  prefixed names.
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
