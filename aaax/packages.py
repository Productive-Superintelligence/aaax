"""LLLM hub package integration for AAAX strategies."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from .models import StrategyResource
from .strategy import Strategy, StrategyStore, _mounted_tactic, _tactic_ref

# The folder of the strategy file that load_strategy is running, if any:
# relative package paths in the file are resolved against it.
_strategy_folder: ContextVar[Path | None] = ContextVar("aaax_strategy_folder", default=None)


def strategy_from_package(
    path: str | Path,
    *,
    name: str | None = None,
    prefix: str | None = None,
    store: str | Path | None = None,
    bind: bool = True,
) -> Strategy:
    """Create a strategy from one LLLM hub package folder.

    In a strategy file that :func:`aaax.load_strategy` loads, a relative
    ``path`` is relative to the file's folder.
    """

    path = _package_path(path)
    manifest = _load_manifest(path)
    strategy = Strategy(
        name or manifest.package.name,
        description=manifest.package.description,
        metadata={
            "package": manifest.identifier,
            "version": manifest.package.version,
            "source": str(manifest.base_dir or Path(path)),
            "card": _model_dump(manifest.card),
        },
    )
    return add_package(strategy, path, prefix=prefix, store=store, bind=bind)


def add_package(
    strategy: Strategy,
    path: str | Path,
    *,
    prefix: str | None = None,
    store: str | Path | None = None,
    bind: bool = True,
) -> Strategy:
    """Add package resources and local handlers to an existing strategy.

    Resource names are ``<prefix>.<name>`` with a ``prefix``. A package whose
    names clash with resources already in the strategy is rejected before
    anything is added; mount it with a prefix to keep the names apart.

    With ``bind`` (the default), tactics get handlers that import the package
    on first use, and channels are backed by the strategy's one store under
    their resource names, so prefixed packages never share a channel. If the
    strategy has no store yet, the package opens one at ``store`` (default
    ``<package>/.lllm/network``); packages mounted later share it, and a
    ``store`` other than the strategy's raises ``ValueError``. The store is
    opened, and the channels created, on first use, never while building or
    inspecting. ``bind=False`` adds metadata only.

    In a strategy file that :func:`aaax.load_strategy` loads, a relative
    ``path`` is relative to the file's folder, as if it were built from
    ``Path(__file__).parent``; elsewhere it is relative to the working
    directory.
    """

    path = _package_path(path)
    manifest = _load_manifest(path)
    base_dir = manifest.base_dir or _manifest_base(path)
    package_prefix = _resource_prefix(prefix)
    package_name = _local_name(package_prefix, manifest.package.name)
    _check_names(strategy, manifest, package_prefix)
    if bind and manifest.channels and (strategy.store is None or store is not None):
        root = base_dir / ".lllm" / "network" if store is None else store
        strategy.attach_store(StrategyStore(root=root))
    store_root = strategy.store.root if bind and strategy.store is not None else None
    if bind and base_dir not in strategy._packages:
        strategy._packages.append(base_dir)
    strategy.add_resource(
        StrategyResource(
            kind="package",
            name=package_name,
            ref=f"lllm://{manifest.package.org}/{manifest.package.name}",
            description=manifest.package.description,
            metadata={
                "package": manifest.identifier,
                "version": manifest.package.version,
                "path": str(base_dir),
                "primary": manifest.package.primary,
                "card": _model_dump(manifest.card),
            },
        )
    )

    if manifest.config is not None:
        strategy.add_resource(
            _strategy_resource(
                manifest,
                "config",
                "default",
                description=manifest.config.description,
                metadata={
                    **manifest.config.metadata,
                    "schema": manifest.config.schema,
                    "defaults": manifest.config.defaults,
                },
                prefix=package_prefix,
            )
        )

    for name, resource in manifest.schemas.items():
        strategy.add_resource(
            _strategy_resource(
                manifest,
                "schema",
                name,
                entrypoint=resource.entry,
                description=resource.description,
                metadata=resource.metadata,
                prefix=package_prefix,
            )
        )

    tactic_handlers: dict[str, PackageTactic] = {}
    for name, resource in manifest.tactics.items():
        handler = (
            PackageTactic(
                resource.entry,
                base_dir=base_dir,
                name=name,
                ref=manifest.ref("tactic", name),
                local_name=_local_name(package_prefix, name),
                description=resource.description,
                examples=list(resource.examples),
            )
            if bind
            else None
        )
        if handler is not None:
            tactic_handlers[name] = handler
        strategy.add_resource(
            _strategy_resource(
                manifest,
                "tactic",
                name,
                entrypoint=resource.entry,
                description=resource.description,
                metadata={
                    **resource.metadata,
                    "runtime": resource.runtime,
                    "input": resource.input,
                    "output": resource.output,
                    "examples": list(resource.examples),
                },
                prefix=package_prefix,
            ),
            handler=handler,
        )

    for name, resource in manifest.channels.items():
        channel = {
            "schema": resource.schema,
            "form": resource.form,
            "description": resource.description,
            "metadata": resource.metadata,
        }
        strategy._add_resource(
            _strategy_resource(
                manifest,
                "channel",
                name,
                description=resource.description,
                metadata={
                    **resource.metadata,
                    "schema": resource.schema,
                    "form": resource.form,
                    "store": None if store_root is None else str(store_root),
                },
                prefix=package_prefix,
            ),
            channel=channel if bind else None,
        )

    for name, resource in manifest.snapshots.items():
        strategy.add_resource(
            _strategy_resource(
                manifest,
                "snapshot",
                name,
                description=resource.description,
                metadata={
                    **resource.metadata,
                    "schema": resource.schema,
                    "channel": resource.channel,
                },
                prefix=package_prefix,
            )
        )

    for name, resource in manifest.services.items():
        handler = None
        if bind and resource.tactic and resource.tactic in tactic_handlers:
            handler = tactic_handlers[resource.tactic]
        strategy.add_resource(
            _strategy_resource(
                manifest,
                "service",
                name,
                entrypoint=resource.entry,
                description=resource.description,
                metadata={
                    **resource.metadata,
                    "tactic": resource.tactic,
                    "tactics": list(resource.tactics),
                    "subscribes": list(resource.subscribes),
                    "publishes": list(resource.publishes),
                    "transport": resource.transport,
                },
                prefix=package_prefix,
            ),
            handler=handler,
        )

    for name, resource in manifest.runs.items():
        strategy.add_resource(
            _strategy_resource(
                manifest,
                "run",
                name,
                description=resource.description,
                metadata={
                    **resource.metadata,
                    "services": list(resource.services),
                    "tactics": list(resource.tactics),
                    "channels": list(resource.channels),
                    "snapshots": list(resource.snapshots),
                },
                prefix=package_prefix,
            )
        )

    for name, resource in manifest.docs.items():
        strategy.add_resource(
            _strategy_resource(
                manifest,
                "doc",
                name,
                description=resource.description,
                metadata={
                    **resource.metadata,
                    "path": resource.path,
                    "title": resource.title,
                },
                prefix=package_prefix,
            )
        )

    for name, resource in manifest.examples.items():
        strategy.add_resource(
            _strategy_resource(
                manifest,
                "example",
                name,
                description=resource.description,
                metadata={
                    **resource.metadata,
                    "path": resource.path,
                    "command": resource.command,
                },
                prefix=package_prefix,
            )
        )

    for name, resource in manifest.assets.items():
        strategy.add_resource(
            _strategy_resource(
                manifest,
                "asset",
                name,
                description=resource.description,
                metadata={
                    **resource.metadata,
                    "path": resource.path,
                    "media_type": resource.media_type,
                },
                prefix=package_prefix,
            )
        )

    return strategy


def _strategy_resource(
    manifest: Any,
    kind: str,
    name: str,
    *,
    entrypoint: str | None = None,
    description: str = "",
    metadata: Mapping[str, Any] | None = None,
    prefix: str | None = None,
) -> StrategyResource:
    return StrategyResource(
        kind=kind,
        name=_local_name(prefix, name),
        ref=manifest.ref(kind, name),
        entrypoint=entrypoint,
        description=description,
        metadata={
            "package": manifest.identifier,
            "version": manifest.package.version,
            "resource": name,
            **{
                key: value
                for key, value in dict(metadata or {}).items()
                if value is not None
            },
        },
    )


class PackageTactic:
    """A package tactic entrypoint, imported on first use.

    Building or inspecting a strategy never imports package code; serving it
    (or invoking the resource) does. ``name`` is the tactic's name in the
    manifest, and ``local_name`` its resource name in the strategy, which
    the loaded tactic is served under. A loaded tactic without a
    ``package_ref`` gets ``ref``, the manifest ref
    ``lllm://org/package/tactics/name``, and one without a description or
    examples gets the manifest's ``description`` and ``examples``. All are
    set on a copy: the imported object may be shared with other packages or
    modules, and it is left as it is. A ``ref`` that is not a valid tactic
    ref (the hub accepts tactic names, like ``a#b``, that a ref cannot
    carry) is not used.
    """

    def __init__(
        self,
        entrypoint: str,
        *,
        base_dir: Path,
        name: str,
        ref: str | None = None,
        local_name: str | None = None,
        description: str = "",
        examples: list[dict[str, Any]] | None = None,
    ) -> None:
        self.entrypoint = entrypoint
        self.base_dir = base_dir
        self.name = name
        self.ref = _tactic_ref(ref)
        self.local_name = local_name
        self.description = description
        self.examples = list(examples or ())
        self._tactic: Any = None

    def load(self) -> Any:
        if self._tactic is None:
            tactic = _load_tactic(self.entrypoint, base_dir=self.base_dir, name=self.name)
            info = tactic.info()
            self._tactic = _mounted_tactic(
                tactic,
                name=self.local_name,
                description=None if info.description else (self.description or None),
                ref=None if tactic.package_ref else self.ref,
                examples=None if info.examples else (self.examples or None),
            )
        return self._tactic

    async def __call__(
        self,
        input_value: Any = None,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> Any:
        return await self.load().arun(input_value, context=_call_context(context))


def _load_tactic(entrypoint: str, *, base_dir: Path, name: str) -> Any:
    from lllm.hub import import_entrypoint
    from lllm.runtimes import coerce_tactic

    return coerce_tactic(
        import_entrypoint(entrypoint, base_dir=base_dir, keep_loaded=True),
        name=name,
    )


def _check_names(strategy: Strategy, manifest: Any, prefix: str | None) -> None:
    sections = (
        manifest.schemas,
        manifest.tactics,
        manifest.channels,
        manifest.snapshots,
        manifest.services,
        manifest.runs,
        manifest.docs,
        manifest.examples,
        manifest.assets,
    )
    names = [manifest.package.name, *(["default"] if manifest.config is not None else [])]
    names += [name for section in sections for name in section]
    existing = {resource.name for resource in strategy.resources}
    taken = sorted({_local_name(prefix, name) for name in names} & existing)
    if taken:
        raise ValueError(
            f"Cannot mount package {manifest.identifier}: strategy {strategy.name!r} "
            f"already has resources named {', '.join(taken)}. Mount it with a "
            "prefix to keep the names apart."
        )


@contextmanager
def _packages_relative_to(folder: Path) -> Iterator[None]:
    """Resolve relative package paths against ``folder`` inside the block."""

    token = _strategy_folder.set(folder)
    try:
        yield
    finally:
        _strategy_folder.reset(token)


def _package_path(path: str | Path) -> str | Path:
    """``path`` against the folder of the strategy file being loaded, if relative."""

    folder = _strategy_folder.get()
    if folder is None or not isinstance(path, (str, os.PathLike)):
        return path
    text = os.fspath(path)
    if not isinstance(text, str) or not text or Path(text).expanduser().is_absolute():
        return path
    return folder / text


def _load_manifest(path: str | Path) -> Any:
    from lllm.hub import load_manifest

    return load_manifest(path)


def _manifest_base(path: str | Path) -> Path:
    target = Path(path).expanduser()
    if target.is_file():
        return target.parent
    return target


def _resource_prefix(prefix: str | None) -> str | None:
    if prefix is None or prefix == "":
        return None
    if (
        not isinstance(prefix, str)
        or any(ch.isspace() for ch in prefix)
        or any(ch in prefix for ch in "/:\\")
    ):
        raise ValueError("package prefix must be a path-segment friendly string")
    return prefix


def _local_name(prefix: str | None, name: str) -> str:
    return f"{prefix}.{name}" if prefix else name


def _call_context(context: Mapping[str, Any] | None) -> Any:
    if context is None:
        return None
    try:
        from lllm.protocol import CallContext
    except ImportError:
        return dict(context)
    if isinstance(context, CallContext):
        return context
    return CallContext(metadata=dict(context))


def _model_dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return value.model_dump()
    return value
