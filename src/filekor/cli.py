"""CLI interface using Click."""

import sys
from pathlib import Path
from typing import Optional

import click

from filekor.adapters.exiftool import PyExifToolAdapter
from filekor.labels import LabelsConfig, suggest_labels, LLMConfig
from filekor.sidecar import Content, Sidecar

# Text extraction try-imports (optional dependencies)
try:
    from pypdf import PdfReader

    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


def extract_text(path: str) -> tuple[str, int, int]:
    """Extract text content from a file.

    Args:
        path: Path to the file.

    Returns:
        Tuple of (text_content, word_count, page_count).

    Raises:
        ValueError: If file type is not supported.
    """
    file_path = Path(path)
    ext = file_path.suffix.lstrip(".").lower()

    if ext == "txt":
        content = file_path.read_text(encoding="utf-8")
        words = len(content.split())
        return content, words, 1

    elif ext == "md":
        content = file_path.read_text(encoding="utf-8")
        words = len(content.split())
        # Estimate pages: ~3000 chars per page
        pages = max(1, len(content) // 3000)
        return content, words, pages

    elif ext == "pdf":
        if not HAS_PYPDF:
            raise ValueError("pypdf not installed. Install: pip install pypdf")
        reader = PdfReader(path)
        pages = len(reader.pages)
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text())
        content = "\n".join(text_parts)
        words = len(content.split())
        return content, words, pages

    else:
        raise ValueError(f"Unsupported file type: .{ext}")


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
    help="Output file (default: stdout)",
)
def extract(path: str, output: Optional[str]) -> None:
    """Extract text content from a file.

    Args:
        path: Path to the input file.
        output: Optional output file path.
    """
    # Validate extension
    file_path = Path(path)
    ext = file_path.suffix.lstrip(".").lower()
    supported = {"pdf", "txt", "md"}

    if ext not in supported:
        click.echo(f"Error: Unsupported file type: .{ext}", err=True)
        click.echo(f"Supported: {', '.join(sorted(supported))}", err=True)
        sys.exit(1)

    # Extract text
    try:
        content, word_count, page_count = extract_text(path)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error extracting text: {e}", err=True)
        sys.exit(1)

    # Output
    if output:
        Path(output).write_text(content, encoding="utf-8")
        click.echo(f"Extracted: {output}")
    else:
        click.echo(content)

    sys.exit(0)


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file for sidecar (default: stdout)",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["yaml", "json"]),
    default="yaml",
    help="Output format",
)
def process(path: str, output: Optional[str], format: str) -> None:
    """Process a PDF file and extract metadata.

    Args:
        path: Path to the PDF file.
        output: Optional output file path.
        format: Output format (yaml or json).
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
    if format == "yaml":
        output_text = sidecar.to_yaml()
    else:
        output_text = sidecar.to_json()

    if output:
        Path(output).write_text(output_text)
    else:
        click.echo(output_text)

    sys.exit(0)


@cli.command()
@click.argument("path")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file for sidecar (default: {input}.kor)",
)
@click.option(
    "--no-cache",
    is_flag=True,
    default=False,
    help="Force regeneration, ignore existing sidecar file",
)
@click.option(
    "--no-cache",
    "no_cache",
    is_flag=True,
    default=False,
    help="Force regeneration, ignore existing sidecar file",
)
def sidecar(
    path: str,
    output: Optional[str],
    no_cache: bool,
) -> None:
    """Generate a .kor sidecar file with full metadata for a supported file.

    Args:
        path: Path to the file.
        output: Optional output file path for sidecar.
        no_cache: Force regeneration, ignore existing sidecar file.

    Raises:
        RuntimeError: If LLM is not configured in config.yaml.
    """
    # Check if LLM is configured
    llm_config = LLMConfig.load()
    if not llm_config.enabled or not llm_config.api_key:
        click.echo(
            "Error: LLM is not configured. Please enable LLM in config.yaml "
            "with a valid API key.",
            err=True,
        )
        sys.exit(1)

    file_path = Path(path)

    if not file_path.exists():
        click.echo(f"Error: File not found: {path}", err=True)
        sys.exit(2)

    supported_extensions = {"pdf", "txt", "md"}
    file_ext = file_path.suffix.lstrip(".").lower()
    if file_ext not in supported_extensions:
        click.echo(f"Error: Unsupported file type: .{file_ext}", err=True)
        sys.exit(1)

    # Output path: .kor extension
    if output:
        sidecar_path = Path(output)
    else:
        sidecar_path = file_path.with_suffix(".kor")

    if sidecar_path.exists() and not no_cache:
        click.echo(f"Info: Sidecar already exists: {sidecar_path}", err=True)
        sys.exit(0)

    # Extract metadata (exiftool)
    adapter = PyExifToolAdapter()
    exif_available = adapter.is_available()

    metadata = None
    if exif_available:
        try:
            metadata = adapter.extract_metadata(path)
        except (FileNotFoundError, PermissionError, Exception):
            pass  # Continue without metadata

    # Extract text content
    content_obj = None
    text_content = None
    try:
        text, word_count, page_count = extract_text(path)
        text_content = text  # Save for LLM
        content_obj = Content(
            language="en",  # Could detect language, default to "en"
            word_count=word_count,
            page_count=page_count,
        )
    except Exception:
        pass  # Continue without content

    # Create sidecar with YAML output
    sidecar = Sidecar.create(
        path,
        metadata=metadata,
        content=content_obj,
        labels_config=LabelsConfig.load(),
        text_content=text_content,
    )

    # Write YAML
    sidecar_path.write_text(sidecar.to_yaml())

    click.echo(f"Created: {sidecar_path}")
    sys.exit(0)


@cli.command()
@click.argument("path")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default=None,
    help="Custom labels.properties file",
)
def labels(
    path: str,
    config: Optional[str],
) -> None:
    """Suggest labels based on file content using LLM.

    Analyzes the file content and suggests labels using LLM-based
    extraction from the labels configuration.

    Args:
        path: Path to the file to analyze.
        config: Optional custom labels.properties file path.

    Raises:
        RuntimeError: If LLM is not configured in config.yaml.
    """
    # Check if LLM is configured
    llm_config = LLMConfig.load()
    if not llm_config.enabled or not llm_config.api_key:
        click.echo(
            "Error: LLM is not configured. Please enable LLM in config.yaml "
            "with a valid API key.",
            err=True,
        )
        sys.exit(1)

    # Load config (custom or default)
    labels_config = None
    if config:
        labels_config = LabelsConfig.load(config)
    else:
        labels_config = LabelsConfig.load()

    # Get text content for LLM
    text_content = None
    try:
        text_content, _, _ = extract_text(path)
    except Exception:
        click.echo("Error: Could not read file content.", err=True)
        sys.exit(1)

    # Get suggestions using LLM only
    try:
        suggestions = suggest_labels(
            content=text_content,
            config=labels_config,
        )
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if not suggestions:
        click.echo("No labels suggested for this file.")
        sys.exit(0)

    # Output labels
    for label in suggestions:
        click.echo(label)

    sys.exit(0)


if __name__ == "__main__":
    cli()
