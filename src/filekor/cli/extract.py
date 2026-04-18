"""Extract command for filekor CLI."""

import sys
from pathlib import Path
from typing import Optional

import click

from filekor.cli.base import console, extract_text, HAS_PYPDF
from filekor.core.labels import LabelsConfig, LLMConfig
from filekor.core.processor import DirectoryProcessor, SUPPORTED_EXTENSIONS
from filekor.core.events import create_emitter


@click.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file (default: stdout)",
)
@click.option(
    "--dir",
    "-d",
    "directory",
    is_flag=True,
    default=False,
    help="Process directory instead of single file",
)
def extract(path: str, output: Optional[str], directory: bool) -> None:
    """Extract text content from a file or directory.

    Args:
        path: Path to the input file or directory.
        output: Optional output file path.
        directory: Whether to process a directory.
    """
    if directory:
        _extract_directory(path, output)
    else:
        _extract_file(path, output)
    sys.exit(0)


def _extract_file(path: str, output: Optional[str]) -> None:
    """Extract text from a single file."""
    file_path = Path(path)
    ext = file_path.suffix.lstrip(".").lower()
    supported = {"pdf", "txt", "md"}

    if ext not in supported:
        click.echo(f"Error: Unsupported file type: .{ext}", err=True)
        click.echo(f"Supported: {', '.join(sorted(supported))}", err=True)
        sys.exit(1)

    try:
        content, word_count, page_count = extract_text(path)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error extracting text: {e}", err=True)
        sys.exit(1)

    if output:
        Path(output).write_text(content, encoding="utf-8")
        click.echo(f"Extracted: {output}")
    else:
        click.echo(content)


def _extract_directory(directory: str, output: Optional[str]) -> None:
    """Extract text from all supported files in a directory."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        click.echo(f"Error: Not a directory: {directory}", err=True)
        sys.exit(1)

    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(dir_path.glob(f"**/*.{ext}"))

    seen = set()
    unique_files = []
    for f in files:
        if f not in seen and ".filekor" not in f.parts:
            seen.add(f)
            unique_files.append(f)
    files = unique_files

    if not files:
        click.echo(f"No supported files found in {directory}", err=True)
        sys.exit(0)

    console.print(f"[blue]Found {len(files)} files to process[/blue]")

    llm_config = LLMConfig.load()
    labels_config = LabelsConfig.load()

    emitter = create_emitter()

    def on_result(result):
        if result.success:
            console.print(f"[green]OK[/green] {result.file_path.name}")
        else:
            console.print(f"[red]FAIL[/red] {result.file_path.name}: {result.error}")

    processor = DirectoryProcessor(
        workers=llm_config.workers,
        llm_config=llm_config,
        labels_config=labels_config,
    )

    results = []
    for file_path in files:
        try:
            content, word_count, page_count = extract_text(str(file_path))
            if output:
                out_file = Path(output) / f"{file_path.stem}.txt"
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_text(content, encoding="utf-8")
            results.append((file_path, True, None))
        except Exception as e:
            results.append((file_path, False, str(e)))

    successful = sum(1 for _, s, _ in results if s)
    console.print(f"\n[bold]Completed:[/bold] {successful}/{len(results)} files")