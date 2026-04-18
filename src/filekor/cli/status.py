"""Status command for filekor CLI."""

import sys
from pathlib import Path

import click
from rich.table import Table

from filekor.cli.base import console
from filekor.core.status import get_file_status, get_directory_status, summarize
from filekor.core.events import create_emitter


@click.command()
@click.argument("path", default=".")
@click.option(
    "--dir",
    "-d",
    "directory",
    is_flag=True,
    default=False,
    help="Show status for directory",
)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    help="Watch mode for real-time updates",
)
def status(path: str, directory: bool, watch: bool) -> None:
    """Show status of .kor files for a file or directory.

    Args:
        path: Path to file or directory.
        directory: Whether to show status for directory.
        watch: Enable watch mode for real-time updates.
    """
    if directory or Path(path).is_dir():
        _status_directory(path, watch)
    else:
        _status_file(path)


def _status_file(file_path: str) -> None:
    """Show status for a single file using status module."""
    status = get_file_status(file_path)

    if not status.file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        sys.exit(2)

    if not status.exists:
        console.print(
            f"[yellow]No .kor file found for {status.file_path.name}[/yellow]"
        )
        console.print(f"Expected at: {status.kor_path}")
        console.print("Run 'filekor sidecar' to generate one.")
        sys.exit(1)

    if status.error:
        console.print(f"[red]Error loading .kor: {status.error}[/red]")
        sys.exit(1)

    sidecar = status.sidecar

    table = Table(title=f"Status: {status.file_path.name}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Path", str(status.file_path))
    table.add_row("Kor Path", str(status.kor_path))
    table.add_row("Name", sidecar.file.name)
    table.add_row("Extension", sidecar.file.extension)
    table.add_row("Size", f"{sidecar.file.size_bytes} bytes")
    table.add_row("Modified", str(sidecar.file.modified_at))
    table.add_row("SHA256", sidecar.file.hash_sha256[:16] + "...")
    table.add_row("Status", sidecar.parser_status)

    if sidecar.metadata:
        if sidecar.metadata.author:
            table.add_row("Author", sidecar.metadata.author)
        if sidecar.metadata.pages:
            table.add_row("Pages", str(sidecar.metadata.pages))

    if sidecar.content:
        if sidecar.content.word_count:
            table.add_row("Words", str(sidecar.content.word_count))
        if sidecar.content.page_count:
            table.add_row("Pages", str(sidecar.content.page_count))

    if sidecar.labels and sidecar.labels.suggested:
        table.add_row("Labels", ", ".join(sidecar.labels.suggested))

    console.print(table)


def _status_directory(directory: str, watch: bool) -> None:
    """Show status for all .kor files in a directory using status module."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        console.print(f"[red]Error: Not a directory: {directory}[/red]")
        sys.exit(1)

    status = get_directory_status(directory, recursive=True)

    emitter = create_emitter(watch=watch)
    emitter.status(
        directory,
        [str(s.file_path) for s in status.file_statuses],
        [str(s.kor_path) for s in status.file_statuses if s.exists],
    )

    console.print(f"\n[bold]Directory:[/bold] {directory}")
    console.print(f"[blue]Supported files:[/blue] {status.total_files}")
    console.print(f"[green].kor files:[/green] {status.kor_files}")

    if status.file_statuses:
        kor_statuses = [s for s in status.file_statuses if s.exists]
        if kor_statuses:
            console.print("\n[bold].kor Files:[/bold]")
            for file_status in kor_statuses:
                try:
                    if file_status.sidecar:
                        labels_str = ""
                        if (
                            file_status.sidecar.labels
                            and file_status.sidecar.labels.suggested
                        ):
                            labels_str = (
                                f" [{', '.join(file_status.sidecar.labels.suggested)}]"
                            )
                        console.print(
                            f"  [green]OK[/green] {file_status.kor_path.name}{labels_str}"
                        )
                    else:
                        console.print(
                            f"  [yellow]LOAD[/yellow] {file_status.kor_path.name}"
                        )
                except Exception:
                    console.print(
                        f"  [red]FAIL[/red] {file_status.kor_path.name} (corrupted)"
                    )

        if status.files_without_kor:
            console.print("\n[yellow]Files without .kor:[/yellow]")
            for f in status.files_without_kor:
                console.print(f"  - {f.name}")

    sys.exit(0)