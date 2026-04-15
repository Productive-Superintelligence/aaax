import click

from aaax.cli_kernel import launch, modules


@click.group()
@click.version_option(package_name="aaax")
def main() -> None:
    """AAAX CLI."""


main.add_command(launch)
main.add_command(modules)
