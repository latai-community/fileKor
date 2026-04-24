"""Extract command for filekor CLI."""

import json
import sys
from pathlib import Path
from typing import Optional

import click

sys.stdout.reconfigure(encoding="utf-8")

from filekor.cli.base import console, extract_text
from filekor.constants import FILEKOR_DIR, FORMAT_SEPARATED, FORMAT_JSON
from filekor.core.hasher import calculate_sha256
from filekor.core.processor import SUPPORTED_EXTENSIONS


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
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show progress logs and file headers (default: quiet for pipe)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice([FORMAT_SEPARATED, FORMAT_JSON], case_sensitive=False),
    default=FORMAT_SEPARATED,
    help="Output format for directory mode",
)
def extract(path: str, output: Optional[str], directory: bool, verbose: bool, output_format: str) -> None:
    """Extract text content from a file or directory.

    Args:
        path: Path to the input file or directory.
        output: Optional output file path.
        directory: Whether to process a directory.
        verbose: Show progress logs and headers.
        output_format: Output format for directory mode.
    """
    if directory:
        _extract_directory(path, output, verbose, output_format)
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


def _extract_directory(directory: str, output: Optional[str], verbose: bool, output_format: str) -> None:
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
        if f not in seen and FILEKOR_DIR not in f.parts:
            seen.add(f)
            unique_files.append(f)
    files = unique_files

    if not files:
        click.echo(f"No supported files found in {directory}", err=True)
        sys.exit(0)

    if verbose:
        console.print(f"[blue]Found {len(files)} files to process[/blue]")

    results = []
    for file_path in files:
        try:
            content, word_count, page_count = extract_text(str(file_path))
            sha256 = calculate_sha256(str(file_path))

            if output:
                out_file = Path(output) / f"{file_path.stem}.txt"
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_text(content, encoding="utf-8")
            else:
                _output_content(
                    file_path, content, word_count, page_count, sha256, output_format, directory,
                )

            results.append((file_path, True, None))
        except Exception as e:
            if not output and output_format == FORMAT_JSON:
                error_obj = {
                    "file": str(file_path.relative_to(directory)),
                    "error": str(e),
                    "success": False,
                }
                click.echo(json.dumps(error_obj, ensure_ascii=False), err=True)
            results.append((file_path, False, str(e)))

    if verbose:
        successful = sum(1 for _, s, _ in results if s)
        console.print(f"\n[bold]Completed:[/bold] {successful}/{len(results)} files")


def _output_content(
    file_path: Path,
    content: str,
    word_count: int,
    page_count: int,
    sha256: str,
    output_format: str,
    base_directory: str,
) -> None:
    """Output content according to format."""
    relative_path = file_path.relative_to(base_directory)
    sha_short = sha256[:16]

    if output_format == FORMAT_SEPARATED:
        click.echo(f"\n>>> FILE: {relative_path} (sha256: {sha_short})\n")
        click.echo(content)
        click.echo(f"\n<<< END: {relative_path}\n")

    elif output_format == FORMAT_JSON:
        obj = {
            "file": str(relative_path),
            "sha256": sha256,
            "content": content,
            "words": word_count,
            "pages": page_count,
            "success": True,
        }
        click.echo(json.dumps(obj, ensure_ascii=False))