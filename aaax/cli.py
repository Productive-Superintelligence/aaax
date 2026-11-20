"""AAAX command line interface.

It runs as ``aaax`` and, through the ``lllm.commands`` entry point, as
``lllm shell``.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder

from . import __version__
from .loader import load_strategy
from .server import create_strategy_app

LOG_LEVELS = {"critical", "debug", "error", "info", "trace", "warning"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=_prog(), description="AAAX strategy tools")
    parser.add_argument("--version", action="version", version=f"aaax {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    inspect_cmd = subcommands.add_parser("inspect", help="Inspect a strategy")
    inspect_cmd.add_argument("target", help="strategy.py, directory, or module:factory")
    inspect_cmd.add_argument("--json", action="store_true")

    serve_cmd = subcommands.add_parser("serve", help="Serve a strategy as FastAPI")
    _add_serve_options(serve_cmd)

    launch_cmd = subcommands.add_parser("launch", help="Alias for serve")
    _add_serve_options(launch_cmd)

    args = parser.parse_args(argv)

    if args.command == "inspect":
        strategy = _load_or_error(parser, args.target)
        payload = jsonable_encoder(strategy.info())
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"{payload['name']}: {payload.get('description', '')}")
            for resource in payload.get("resources", []):
                ref = resource.get("ref") or resource.get("entrypoint") or ""
                print(f"{resource['kind']} {resource['name']} {ref}".rstrip())
        return 0

    if args.command in {"serve", "launch"}:
        try:
            host = _serve_host(args.host)
            port = _serve_port(args.port)
            log_level = _serve_log_level(args.log_level)
        except ValueError as exc:
            parser.error(str(exc))
        if args.no_keyring and args.credentials == "keyring":
            # As lllm serve refuses it.
            parser.error(
                "--no-keyring does not read the OS keyring, so --credentials keyring "
                "would store keys it cannot see; use --credentials env"
            )
        strategy = _load_or_error(parser, args.target)
        if not args.skip_key_check:
            _ensure_api_keys(parser, strategy, args)
        try:
            app = create_strategy_app(strategy)
        except (ImportError, ValueError) as exc:  # a store without sssn, a bad name
            parser.error(str(exc))
        import uvicorn

        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level=log_level,
        )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _add_serve_options(command: argparse.ArgumentParser) -> None:
    command.add_argument("target", help="strategy.py, directory, or module:factory")
    command.add_argument("--host", default="127.0.0.1")
    command.add_argument("--port", type=int, default=8400)
    command.add_argument("--log-level", default="info")
    # The API-key options of `lllm serve`, which mean the same here.
    command.add_argument(
        "--env-file",
        default=None,
        help="Local env file to read for required API keys (default: .env.local)",
    )
    command.add_argument(
        "--no-keyring",
        action="store_true",
        help="Do not read API keys from the OS keyring",
    )
    command.add_argument(
        "--credentials",
        choices=("auto", "keyring", "env"),
        default="auto",
        help="Where interactive setup should store missing keys",
    )
    command.add_argument(
        "--skip-key-check",
        action="store_true",
        help="Start without checking the API keys the packages declare",
    )


def _ensure_api_keys(parser: argparse.ArgumentParser, strategy: Any, args: Any) -> None:
    """Check the API keys of the packages a strategy serves, as `lllm serve` does.

    A package needs what `lllm serve` and `lllm setup` check for it (its
    ``[requirements.api_keys]``, plus the keys of the resource `lllm serve`
    would launch) and the keys each of its tactics declares, since AAAX
    serves them all. When the environment has every key, nothing else is
    read. Otherwise a key counts when it is in the env file or in the OS
    keyring (unless ``--no-keyring``), and one found there is put in the
    environment for the server; an unreadable default ``.env.local``
    counts as absent. In a terminal, missing keys are asked for and stored
    as `lllm setup` stores them (in the env file under ``--no-keyring``);
    otherwise the command stops and lists them.
    """

    from lllm.credentials import (
        CredentialError,
        choose_credential_backend,
        configure_missing_api_keys,
        read_env_file,
        resolve_api_keys,
    )
    from lllm.launch import LaunchError

    requirements: dict[str, Any] = {}
    setup: dict[str, str] = {}  # key name -> the `lllm setup` command that stores it
    try:
        for manifest_file in strategy._packages:
            for requirement, command in _package_api_keys(manifest_file):
                requirements.setdefault(requirement.name, requirement)
                setup.setdefault(requirement.name, command)
    except (CredentialError, LaunchError, OSError, ValueError) as exc:
        parser.error(str(exc))
        raise
    if all(os.environ.get(name) for name in requirements):
        return
    env_file = ".env.local" if args.env_file is None else args.env_file
    read_from: str | None = env_file
    unread = ""  # why the default env file was not read, if it was not
    if args.env_file is None:
        try:
            read_env_file(env_file)
        except (CredentialError, OSError, ValueError) as exc:
            # An unreadable default env file counts as absent, but the
            # error for missing keys says why.
            read_from = None
            unread = f"{env_file} was not read: {exc}. Name another env file with --env-file."
    use_keyring = not args.no_keyring
    # Keys stored in the keyring would not be found again under --no-keyring.
    credentials = "env" if args.no_keyring else args.credentials
    try:
        resolution = resolve_api_keys(
            requirements.values(),
            env_file=read_from,
            use_keyring=use_keyring,
        )
        if not resolution.ok and sys.stdin.isatty():
            if unread and choose_credential_backend(credentials) == "env":
                # Keys typed now would be lost: the file cannot take them.
                _missing_keys(parser, resolution, setup, unread)
            backend = configure_missing_api_keys(
                resolution.missing,
                credentials=credentials,
                env_file=env_file,
            )
            print(f"Configured {len(resolution.missing)} API key(s) via {backend}.")
            resolution = resolve_api_keys(
                requirements.values(),
                env_file=read_from,
                use_keyring=use_keyring,
            )
    except (CredentialError, OSError, ValueError) as exc:
        parser.error(str(exc))
        raise
    if not resolution.ok:
        _missing_keys(parser, resolution, setup, unread)


def _missing_keys(
    parser: argparse.ArgumentParser,
    resolution: Any,
    setup: dict[str, str],
    unread: str,
) -> None:
    """Stop with the missing keys, why the env file was not read, and how to set them."""

    from lllm.credentials import format_missing_requirements

    commands = dict.fromkeys(setup[requirement.name] for requirement in resolution.missing)
    reason = f"{unread}\n" if unread else ""
    parser.error(
        "missing required API key(s):\n"
        f"{format_missing_requirements(resolution.missing)}\n\n"
        f"{reason}"
        f"Run {' and '.join(f'`{command}`' for command in commands)} "
        "or set the missing names in your environment."
    )


def _package_api_keys(manifest_file: Path) -> list[tuple[Any, str]]:
    """The keys a package needs, each with the `lllm setup` command that stores it.

    The keys `lllm setup PACKAGE` stores (those `lllm serve` checks) come
    first; a tactic's own keys are stored with ``--resource tactics.NAME``.
    """

    from lllm.credentials import collect_manifest_api_key_requirements
    from lllm.hub import load_manifest
    from lllm.launch import load_launch_api_key_requirements

    target = manifest_file.parent if manifest_file.name == "lllm.toml" else manifest_file
    command = f"lllm setup {_shown_path(target)}"
    found = [
        (requirement, command)
        for requirement in load_launch_api_key_requirements(manifest_file)
    ]
    manifest = load_manifest(manifest_file)
    for name in manifest.tactics:
        found.extend(
            (requirement, f"{command} --resource tactics.{name}")
            for requirement in collect_manifest_api_key_requirements(
                manifest, section="tactics", name=name
            )
        )
    return found


def _shown_path(path: Path) -> str:
    """``path`` relative to the working directory when it is inside it."""

    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _load_or_error(parser: argparse.ArgumentParser, target: str) -> Any:
    try:
        return load_strategy(target)
    except (OSError, TypeError, ValueError, AttributeError, ImportError) as exc:
        parser.error(str(exc))
        raise


def _prog() -> str:
    # The lllm command runs this CLI as `lllm shell`; name the command the
    # user typed in usage and error messages.
    if sys.argv and Path(sys.argv[0]).name == "lllm":
        return "lllm shell"
    return "aaax"


def _serve_host(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("serve host must be a non-empty string")
    host = value
    if any(ch.isspace() for ch in host) or "/" in host or "\\" in host:
        raise ValueError("serve host must be a host name or address, not a URL or path")
    if ":" in host:
        try:
            ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("serve host must be a host name or address, not host:port") from exc
    return host


def _serve_port(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not (1 <= value <= 65535)
    ):
        raise ValueError("serve port must be an integer between 1 and 65535")
    return value


def _serve_log_level(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ch.isspace() for ch in value)
    ):
        raise ValueError(_log_level_error())
    log_level = value.lower()
    if log_level not in LOG_LEVELS:
        raise ValueError(_log_level_error())
    return log_level


def _log_level_error() -> str:
    return "serve log level must be one of: critical, debug, error, info, trace, warning"
