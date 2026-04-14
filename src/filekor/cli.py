"""CLI interface using Click."""
import json
import sys
from pathlib import Path

import click

from filekor.adapters.exiftool import PyExifToolAdapter
from filekor.sidecar import Sidecar


@click.group()
def cli() -> None:
    """filekor - PDF metadata extraction CLI."""
    pass


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file for sidecar JSON (default: stdout)",
)
def process(path: str, output: str | None) -> None:
    """Process a PDF file and extract metadata.

    Args:
        path: Path to the PDF file.
        output: Optional output file path.
    """
    # Check exiftool availability
    adapter = PyExifToolAdapter()
    if not adapter.is_available():
        click.echo(
            "Error: exiftool not found. Please install exiftool first.", err=True
        )
        sys.exit(1)

    # Check file exists
    if not Path(path).exists():
        click.echo(f"Error: File not found: {path}", err=True)
        sys.exit(2)

    # Extract metadata
    try:
        metadata = adapter.extract_metadata(path)
    except FileNotFoundError:
        click.echo(f"Error: File not found: {path}", err=True)
        sys.exit(2)
    except PermissionError:
        click.echo(f"Error: Permission denied: {path}", err=True)
        sys.exit(3)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Create sidecar
    sidecar = Sidecar.create(path, metadata)

    # Output
    json_output = sidecar.to_json()
    if output:
        Path(output).write_text(json_output)
    else:
        click.echo(json_output)

    sys.exit(0)


if __name__ == "__main__":
    cli()