"""AAAX command line interface.

It runs as ``aaax`` and, through the ``lllm.commands`` entry point, as
``lllm shell``.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
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
        strategy = _load_or_error(parser, args.target)
        if not args.skip_key_check:
            _ensure_api_keys(parser, strategy, args)
        try:
            app = create_strategy_app(strategy)
        except ImportError as exc:  # e.g. a channel store without sssn
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
        default=".env.local",
        help="Local env file to read for required API keys",
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

    A package needs the keys that `lllm serve` and `lllm setup` check for
    it: its ``[requirements.api_keys]``, plus those of the resource `lllm
    serve` would launch. A key counts when it is in the environment, in the
    env file, or in the OS keyring (unless ``--no-keyring``); one found in
    the file or the keyring is put in the environment for the server. In a
    terminal, missing keys are asked for and stored as `lllm setup` stores
    them; otherwise the command stops and lists them.
    """

    from lllm.credentials import (
        CredentialError,
        configure_missing_api_keys,
        format_missing_requirements,
        resolve_api_keys,
    )
    from lllm.launch import LaunchError, load_launch_api_key_requirements

    use_keyring = not args.no_keyring
    try:
        needed = {path: load_launch_api_key_requirements(path) for path in strategy._packages}
        requirements = [requirement for found in needed.values() for requirement in found]
        if not requirements:
            return
        resolution = resolve_api_keys(
            requirements,
            env_file=args.env_file,
            use_keyring=use_keyring,
        )
        if not resolution.ok and sys.stdin.isatty():
            backend = configure_missing_api_keys(
                resolution.missing,
                credentials=args.credentials,
                env_file=args.env_file,
            )
            print(f"Configured {len(resolution.missing)} API key(s) via {backend}.")
            resolution = resolve_api_keys(
                requirements,
                env_file=args.env_file,
                use_keyring=use_keyring,
            )
    except (CredentialError, LaunchError, OSError, ValueError) as exc:
        parser.error(str(exc))
        raise
    if not resolution.ok:
        missing = {requirement.name for requirement in resolution.missing}
        setup = " or ".join(
            f"`lllm setup {_shown_path(path)}`"
            for path, found in needed.items()
            if any(requirement.name in missing for requirement in found)
        )
        parser.error(
            "missing required API key(s):\n"
            f"{format_missing_requirements(resolution.missing)}\n\n"
            f"Run {setup} or set the missing names in your environment."
        )


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
