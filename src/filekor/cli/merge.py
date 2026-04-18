"""Merge command for filekor CLI."""

import sys
from pathlib import Path
from typing import Optional

import click

from filekor.cli.base import console
from filekor.core.merge import merge_kor_files


@click.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file for merged .kor (default: {directory}/.filekor/merged.kor)",
)
@click.option(
    "--no-erase",
    "no_erase",
    is_flag=True,
    default=False,
    help="Keep original .kor files after merge",
)
def merge(directory: str, output: Optional[str], no_erase: bool) -> None:
    """Merge multiple .kor files into a single aggregated .kor file.

    Finds all *.kor files in the .filekor/ subdirectory of the specified path
    and combines them into a single merged .kor file (YAML list format).
    """
    delete_sources = not no_erase

    try:
        merged_sidecars = merge_kor_files(
            directory=directory,
            output_path=output,
            delete_sources=delete_sources,
        )
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if not merged_sidecars:
        console.print("[yellow]No .kor files found to merge[/yellow]")
        sys.exit(0)

    output_path = Path(output) if output else Path(directory) / ".filekor" / "merged.kor"
    console.print(
        f"[bold green]Merged:[/bold green] {len(merged_sidecars)} files -> {output_path}"
    )
    console.print(f"[bold]Completed:[/bold] {len(merged_sidecars)} files merged")