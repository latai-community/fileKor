"""Delete command for filekor CLI."""

import sys
from typing import Optional

import click

from filekor.cli.base import console
from filekor.core.delete import (
    delete_by_sha,
    delete_by_path,
    delete_by_input,
    get_deletion_preview,
)


@click.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option(
    "--sha",
    "sha",
    type=str,
    default=None,
    help="SHA256 hash of the file to delete",
)
@click.option(
    "--path",
    "path",
    type=click.Path(exists=True),
    default=None,
    help="Path to the file (SHA256 will be calculated)",
)
@click.option(
    "--input",
    "input",
    type=click.Path(exists=True),
    default=None,
    help="File containing SHA256 hashes (one per line)",
)
@click.option(
    "--db",
    "db",
    is_flag=True,
    default=None,
    help="Delete only from database",
)
@click.option(
    "--file",
    "file_flag",
    is_flag=True,
    default=None,
    help="Delete only .kor files (not from database)",
)
@click.option(
    "--all",
    "all",
    is_flag=True,
    default=None,
    help="Delete from both database and .kor files",
)
@click.option(
    "--verbose",
    "-v",
    "verbose",
    is_flag=True,
    default=False,
    help="Show detailed output",
)
@click.option(
    "--dry-run",
    "dry_run",
    is_flag=True,
    default=False,
    help="Show what would be deleted without actually deleting",
)
@click.option(
    "--force",
    "force",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt",
)
@click.option(
    "--no-recursive",
    "no_recursive",
    is_flag=True,
    default=False,
    help="Do not search in subdirectories",
)
@click.option(
    "--max-depth",
    "max_depth",
    type=int,
    default=None,
    help="Maximum directory depth to search",
)
def delete(
    directory: str,
    sha: Optional[str],
    path: Optional[str],
    input: Optional[str],
    db: Optional[bool],
    file_flag: Optional[bool],
    all: Optional[bool],
    verbose: bool,
    dry_run: bool,
    force: bool,
    no_recursive: bool,
    max_depth: Optional[int],
) -> None:
    """Delete .kor files and/or database records by SHA256 hash.

    The directory argument specifies where to search for .kor files.
    Must specify at least one of: --sha, --path, --input.
    """
    if not sha and not path and not input:
        console.print("[red]Error: Must specify --sha, --path, or --input[/red]")
        sys.exit(1)

    scope = "all"
    if db:
        scope = "db"
    elif file_flag:
        scope = "file"
    elif all:
        scope = "all"

    recursive = not no_recursive
    depth = max_depth if max_depth else -1

    target_hashes = []
    if sha:
        target_hashes.append(sha)
    if path:
        from filekor.core.hasher import calculate_sha256
        target_hashes.append(calculate_sha256(path))
    if input:
        input_path_obj = open(input)
        for line in input_path_obj.read().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                target_hashes.append(line)

    console.print(
        f"[blue]Processing {len(target_hashes)} hash(es) in {directory} with scope: {scope}[/blue]"
    )

    if dry_run:
        all_db_hashes = []
        all_files = []
        for target_sha in target_hashes:
            db_hashes, files = get_deletion_preview(
                target_sha, directory, recursive, depth
            )
            all_db_hashes.extend(db_hashes)
            all_files.extend(files)

        console.print("\n[bold yellow]Dry Run - Would delete:[/bold yellow]")
        if all_db_hashes:
            console.print("[blue]From database:[/blue]")
            for h in all_db_hashes:
                console.print(f"  - {h[:16]}...")
        if all_files:
            console.print("[blue]Files:[/blue]")
            for name, file_path in all_files:
                console.print(f"  - {name} ({file_path})")
    else:
        total_db = 0
        total_files = 0
        for target_sha in target_hashes:
            db_count, files_count = delete_by_sha(
                target_sha,
                directory=directory,
                scope=scope,
                recursive=recursive,
                max_depth=depth,
                verbose=verbose,
            )
            total_db += db_count
            total_files += files_count

        if not force and (total_db > 0 or total_files > 0):
            confirm = click.confirm(
                f"Delete {total_files} file(s) and {total_db} DB record(s)?",
                default=False,
            )
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                sys.exit(0)

    console.print(f"[bold]Deleted:[/bold] {total_db if not dry_run else len(all_db_hashes)} from DB, {total_files if not dry_run else len(all_files)} files")