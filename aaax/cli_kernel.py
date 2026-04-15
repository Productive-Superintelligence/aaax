from __future__ import annotations

import asyncio

import click

from aaax.bootstrap import bootstrap_kernel
from aaax.config import AAAXConfig


def _print_kernel_snapshot(kernel, *, host: str | None = None, port: int | None = None) -> None:
    click.echo(f"kernel_id={kernel.id}")
    click.echo(f"docked_systems={kernel._constellation.system_ids()}")
    click.echo("channels:")
    for channel in kernel.all_channels:
        click.echo(f"  - {channel.id}")
    if host is not None and port is not None:
        click.echo(f"http_transport=http://{host}:{port} (PUBLIC channels only)")


@click.command()
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--publish", is_flag=True, help="Publish public channels over HTTP.")
@click.option(
    "--once",
    is_flag=True,
    help="Bootstrap the kernel, run one step, print a summary, and exit.",
)
def launch(config_path: str, publish: bool, once: bool) -> None:
    """Launch an AAAX kernel from a TOML config."""

    if publish and once:
        raise click.UsageError("--once cannot be combined with --publish.")

    async def _run() -> None:
        config = AAAXConfig.from_file(config_path)
        kernel = await bootstrap_kernel(config, start_channels=once)
        if once:
            await kernel.step()
            _print_kernel_snapshot(kernel)
            return

        click.echo(f"Starting AAAX runtime for '{config.name}' ({kernel.id}).")
        if publish:
            _print_kernel_snapshot(
                kernel,
                host=config.network.host,
                port=config.network.port,
            )
            click.echo("Press Ctrl+C to stop.")
            await kernel.publish(host=config.network.host, port=config.network.port)
        else:
            _print_kernel_snapshot(kernel)
            click.echo("Press Ctrl+C to stop.")
            await kernel.launch()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        click.echo("\nStopped AAAX runtime.")


@click.group()
def modules() -> None:
    """Module management commands."""


@modules.command("list")
def list_modules() -> None:
    """Placeholder until persistent module registry commands are implemented."""
    click.echo("Module registry commands require a running kernel instance.")
