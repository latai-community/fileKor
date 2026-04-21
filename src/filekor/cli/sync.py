"""Sync command for filekor CLI."""

import sys
from pathlib import Path

import click

from filekor.cli.base import console
from filekor.constants import FILEKOR_DIR, KOR_EXTENSION
from filekor.db import sync_file


@click.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--dir",
    "-d",
    "directory",
    is_flag=True,
    default=False,
    help="Sync all .kor files in directory",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show detailed output",
)
def sync(path: str, directory: bool, verbose: bool) -> None:
    """Sync .kor files to database.

    Synchronizes existing .kor sidecar files to the SQLite database
    without regenerating or re-labeling them.

    Args:
        path: Path to a .kor file or directory containing .kor files.
        directory: Sync all .kor files in the directory.
        verbose: Show detailed output.

    Examples:
        filekor sync document.kor
        filekor sync ./docs/ --dir
    """
    if directory or Path(path).is_dir():
        dir_path = Path(path)
        kor_files = list(dir_path.glob("**/*.kor"))

        # Filter out .filekor dirs unless the target IS a .filekor dir
        is_filekor_dir = FILEKOR_DIR in dir_path.parts
        if not is_filekor_dir:
            kor_files = [f for f in kor_files if FILEKOR_DIR not in f.parts]

        if not kor_files:
            console.print(f"[yellow]No .kor files found in {path}[/yellow]")
            sys.exit(0)

        console.print(f"[blue]Found {len(kor_files)} .kor files to sync[/blue]")

        successful = 0
        failed = 0

        for kor_file in kor_files:
            try:
                sync_file(str(kor_file))
                successful += 1
                if verbose:
                    console.print(f"[green]Synced:[/green] {kor_file.name}")
            except Exception as e:
                failed += 1
                console.print(f"[red]Failed:[/red] {kor_file.name} - {e}")

        console.print(
            f"\n[bold]Completed:[/bold] {successful}/{len(kor_files)} synced, {failed} failed"
        )
        sys.exit(0 if failed == 0 else 1)
    else:
        kor_path = Path(path)
        if not kor_path.suffix == KOR_EXTENSION:
            console.print("[red]Error: File must have .kor extension[/red]")
            sys.exit(1)

        try:
            sync_file(str(kor_path))
            console.print(f"[bold green]Synced:[/bold green] {kor_path}")
            sys.exit(0)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)
