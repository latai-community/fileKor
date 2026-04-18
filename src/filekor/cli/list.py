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
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output as JSON",
)
@click.option(
    "--csv",
    "output_csv",
    is_flag=True,
    default=False,
    help="Output as CSV",
)
@click.option(
    "--sha-only",
    "sha_only",
    is_flag=True,
    default=False,
    help="Output only SHA256 hashes (one per line)",
)
@click.option(
    "--ext",
    "extension",
    type=str,
    default=None,
    help="Filter by file extension (e.g., pdf, md, txt)",
)
@click.option(
    "--include-merged",
    "include_merged",
    is_flag=True,
    default=False,
    help="Include individual entries from merged.kor files",
)
def list(
    directory: str,
    output_json: bool,
    output_csv: bool,
    sha_only: bool,
    extension: Optional[str],
    include_merged: bool,
) -> None:
    """List SHA256 hashes and file names for all .kor files in a directory."""
    results = list_kor_files(
        directory=directory,
        extension=extension,
        include_merged=include_merged,
        recursive=True,
    )

    if sha_only:
        output = list_sha_only(directory, extension, include_merged)
        console.print(output)
    elif output_json:
        output = list_as_json(directory, extension, include_merged)
        console.print(output)
    elif output_csv:
        output = list_as_csv(directory, extension, include_merged)
        console.print(output)
    else:
        output = list_as_text(directory, extension, include_merged)
        console.print(output)

    console.print(f"\n[bold]Total:[/bold] {len(results)} files")