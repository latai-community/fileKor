"""List command for filekor CLI."""

from pathlib import Path
from typing import Optional

import click

from filekor.cli.base import console
from filekor.core.list import (
    list_kor_files,
    list_as_text,
    list_as_json,
    list_as_csv,
    list_sha_only,
)


@click.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option(
    "--format",
    "-f",
    type=click.Choice(["text", "json", "csv", "sha"]),
    default="text",
    help="Output format",
)
@click.option(
    "--ext",
    "extension",
    type=str,
    default=None,
    help="Filter by file extension (e.g., pdf, md, txt)",
)
@click.option(
    "--no-merged",
    "no_merged",
    is_flag=True,
    default=False,
    help="Exclude entries from merged.kor files",
)
def list(
    directory: str,
    format: str,
    extension: Optional[str],
    no_merged: bool,
) -> None:
    """List SHA256 hashes and file names for all .kor files in a directory."""
    include_merged = not no_merged
    results = list_kor_files(
        directory=directory,
        extension=extension,
        include_merged=include_merged,
        recursive=True,
    )

    if format == "json":
        output = list_as_json(directory, extension, include_merged)
    elif format == "csv":
        output = list_as_csv(directory, extension, include_merged)
    elif format == "sha":
        output = list_sha_only(directory, extension, include_merged)
    else:
        output = list_as_text(directory, extension, include_merged)

    console.print(output)
    console.print(f"\n[bold]Total:[/bold] {len(results)} files")
