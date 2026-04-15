"""CLI interface using Click."""

import sys
from pathlib import Path
from typing import Optional

import click

from filekor.adapters.exiftool import PyExifToolAdapter
from filekor.labels import LabelsConfig, suggest_from_path, suggest_hybrid, LLMConfig
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
    "--llm",
    "use_llm",
    is_flag=True,
    default=None,
    help="Use LLM for label extraction",
)
@click.option(
    "--no-llm",
    "no_llm",
    is_flag=True,
    default=False,
    help="Use path-based label extraction only",
)
def sidecar(
    path: str,
    output: Optional[str],
    no_cache: bool,
    use_llm: Optional[bool],
    no_llm: bool,
) -> None:
    """Generate a .kor sidecar file with full metadata for a supported file.

    Args:
        path: Path to the file.
        output: Optional output file path for sidecar.
        no_cache: Force regeneration, ignore existing sidecar file.
        use_llm: Use LLM for label extraction.
        no_llm: Use path-based label extraction only.
    """
    # Validate LLM flags
    if use_llm and no_llm:
        click.echo("Error: Cannot use both --llm and --no-llm flags.", err=True)
        sys.exit(1)

    # Determine use_llm value
    llm_enabled = None
    if use_llm:
        llm_enabled = True
    elif no_llm:
        llm_enabled = False

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
        use_llm=llm_enabled,
    )

    # Write YAML
    sidecar_path.write_text(sidecar.to_yaml())

    click.echo(f"Created: {sidecar_path}")
    sys.exit(0)


@cli.command()
@click.argument("path")
@click.option(
    "--show-confidence",
    is_flag=True,
    default=False,
    help="Show confidence scores for each label",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default=None,
    help="Custom labels.properties file",
)
@click.option(
    "--llm",
    "use_llm",
    is_flag=True,
    default=None,
    help="Use LLM for label extraction",
)
@click.option(
    "--no-llm",
    "no_llm",
    is_flag=True,
    default=False,
    help="Use path-based label extraction only",
)
def labels(
    path: str,
    show_confidence: bool,
    config: Optional[str],
    use_llm: Optional[bool],
    no_llm: bool,
) -> None:
    """Suggest labels based on file path.

    Analyzes the file path and suggests labels based on matching synonyms
    from the labels configuration. Can optionally use LLM for content-based
    label extraction.

    Args:
        path: Path to the file to analyze.
        show_confidence: Whether to show confidence scores.
        config: Optional custom labels.properties file path.
        use_llm: Use LLM for label extraction.
        no_llm: Use path-based label extraction only.
    """
    # Validate LLM flags
    if use_llm and no_llm:
        click.echo("Error: Cannot use both --llm and --no-llm flags.", err=True)
        sys.exit(1)

    # Determine use_llm value
    llm_enabled = None
    if use_llm:
        llm_enabled = True
    elif no_llm:
        llm_enabled = False

    # Load config (custom or default)
    labels_config = None
    if config:
        labels_config = LabelsConfig.load(config)
    else:
        labels_config = LabelsConfig.load()

    # Get text content for LLM if needed
    text_content = None
    if llm_enabled:
        try:
            text_content, _, _ = extract_text(path)
        except Exception:
            pass  # Continue without content

    # Get suggestions using hybrid approach
    suggestions, source = suggest_hybrid(
        path,
        content=text_content,
        use_llm=llm_enabled,
        config=labels_config,
        llm_config=LLMConfig.load() if llm_enabled else None,
    )

    if not suggestions:
        click.echo("No labels suggested for this path.")
        sys.exit(0)

    # Output labels
    if show_confidence and source == "path":
        # Show confidence for path-based labels
        for label in suggestions:
            confidence = labels_config.synonyms.get(label, [])
            # Calculate confidence based on matches
            path_obj = Path(path)
            words = set(
                path_obj.stem.lower().replace("-", " ").replace("_", " ").split()
            )
            for part in path_obj.parts[:-1]:
                words.update(part.lower().replace("-", " ").replace("_", " ").split())
            matched = sum(1 for s in confidence if s in words)
            conf = matched / len(confidence) if confidence else 0
            click.echo(f"{label}: {conf:.2f}")
    else:
        for label in suggestions:
            click.echo(label)

    sys.exit(0)


if __name__ == "__main__":
    cli()
