"""CLI commands package."""

import click

from filekor.cli.base import console, extract_text, HAS_PYPDF
from filekor.cli.delete import delete
from filekor.cli.extract import extract
from filekor.cli.labels import labels
from filekor.cli.list import list
from filekor.cli.merge import merge
from filekor.cli.process import process
from filekor.cli.sidecar import sidecar
from filekor.cli.sync import sync
from filekor.cli.status import status


@click.group()
def cli() -> None:
    """filekor - PDF metadata extraction CLI."""
    pass


# Register commands
cli.add_command(extract)
cli.add_command(process)
cli.add_command(sidecar)
cli.add_command(labels)
cli.add_command(status)
cli.add_command(sync)
cli.add_command(merge)
cli.add_command(delete)
cli.add_command(list)


__all__ = [
    "console",
    "extract_text",
    "HAS_PYPDF",
    "cli",
    "delete",
    "extract",
    "labels",
    "list",
    "merge",
    "process",
    "sidecar",
    "sync",
    "status",
]