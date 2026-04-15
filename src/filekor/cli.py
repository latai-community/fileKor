"""CLI interface using Click."""

import sys
from pathlib import Path
from typing import Optional, List

import click
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from filekor.adapters.exiftool import PyExifToolAdapter
from filekor.labels import LabelsConfig, suggest_labels, LLMConfig
from filekor.sidecar import Content, Sidecar
from filekor.processor import (
    process_directory,
    DirectoryProcessor,
    SUPPORTED_EXTENSIONS,
)
from filekor.events import EventEmitter, create_emitter, EventType, FilekorEvent

console = Console()

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


def _extract_directory(directory: str, output: Optional[str]) -> None:
    """Extract text from all supported files in a directory."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        click.echo(f"Error: Not a directory: {directory}", err=True)
        sys.exit(1)

    # Find all supported files
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(dir_path.glob(f"*.{ext}"))
        files.extend(dir_path.glob(f"**/*. {ext}"))  # For .md files

    if not files:
        click.echo(f"No supported files found in {directory}", err=True)
        sys.exit(0)

    console.print(f"[blue]Found {len(files)} files to process[/blue]")

    # Load config
    llm_config = LLMConfig.load()
    labels_config = LabelsConfig.load()

    # Process with progress
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

    # Note: For extract, we just want text extraction, not full sidecar creation
    # So we run a simpler version
    results = []
    for file_path in files:
        try:
            content, word_count, page_count = extract_text(str(file_path))
            if output:
                # If output is a directory, write each file there
                out_file = Path(output) / f"{file_path.stem}.txt"
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_text(content, encoding="utf-8")
            results.append((file_path, True, None))
        except Exception as e:
            results.append((file_path, False, str(e)))

    successful = sum(1 for _, s, _ in results if s)
    console.print(f"\n[bold]Completed:[/bold] {successful}/{len(results)} files")


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
    "no_cache",
    is_flag=True,
    default=False,
    help="Force regeneration, ignore existing sidecar file",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default=None,
    help="Custom config.yaml file for LLM settings",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show detailed output",
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
    "--workers",
    "-w",
    type=int,
    default=None,
    help="Number of parallel workers (default from config)",
)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    help="Enable event emitter for real-time progress",
)
def sidecar(
    path: str,
    output: Optional[str],
    no_cache: bool,
    config: Optional[str],
    verbose: bool,
    directory: bool,
    workers: Optional[int],
    watch: bool,
) -> None:
    """Generate a .kor sidecar file with full metadata for a supported file.

    Args:
        path: Path to the file or directory.
        output: Optional output file/directory for sidecar.
        no_cache: Force regeneration, ignore existing sidecar file.
        config: Optional custom config.yaml file for LLM settings.
        verbose: Show detailed output.
        directory: Whether to process a directory.
        workers: Number of parallel workers.
        watch: Enable event emitter for progress.

    Raises:
        RuntimeError: If LLM is not configured in config.yaml.
    """
    if directory:
        _sidecar_directory(path, output, config, verbose, workers, watch)
    else:
        _sidecar_file(path, output, no_cache, config, verbose)
    # Load LLM config (if available)
    llm_config = LLMConfig.load(config) if config else LLMConfig.load()

    # Show config status (verbose only)
    if verbose:
        if config:
            console.print(f"[blue]Config:[/blue] {config}")
        else:
            console.print("[blue]Config:[/blue] auto-search")

        if llm_config.enabled and llm_config.api_key:
            console.print(
                f"[green]LLM:[/green] enabled ({llm_config.provider}, {llm_config.model})"
            )
        else:
            console.print(
                "[yellow]LLM:[/yellow] not configured (sidecar will be generated without labels)"
            )

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
            if verbose:
                console.print("[green]Metadata:[/green] extracted")
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
        if verbose:
            console.print(
                f"[green]Text:[/green] {word_count} words, {page_count} pages"
            )
    except Exception as e:
        if verbose:
            console.print(f"[red]Text extraction failed:[/red] {e}")
        pass  # Continue without content

    # Create sidecar with YAML output
    sidecar = Sidecar.create(
        path,
        metadata=metadata,
        content=content_obj,
        labels_config=LabelsConfig.load(),
        text_content=text_content,
        verbose=verbose,
    )

    # Write YAML
    sidecar_path.write_text(sidecar.to_yaml())

    console.print(f"[bold green]Created:[/bold green] {sidecar_path}")
    sys.exit(0)


def _auto_sync_hook(sidecar_path: Path, llm_config: LLMConfig, verbose: bool) -> None:
    """Auto-sync sidecar to database if enabled.

    Args:
        sidecar_path: Path to the .kor sidecar file.
        llm_config: LLM configuration containing auto_sync setting.
        verbose: Whether to show verbose output.
    """
    if not llm_config.auto_sync:
        return

    try:
        from filekor.db import sync_file

        sync_file(str(sidecar_path))
        if verbose:
            console.print(f"[green]Synced to DB:[/green] {sidecar_path.name}")
    except Exception as e:
        if verbose:
            console.print(f"[yellow]DB sync warning: {e}[/yellow]")


def _sidecar_file(
    path: str,
    output: Optional[str],
    no_cache: bool,
    config: Optional[str],
    verbose: bool,
) -> None:
    """Generate sidecar for a single file."""
    # Load LLM config (if available)
    llm_config = LLMConfig.load(config) if config else LLMConfig.load()

    # Show config status (verbose only)
    if verbose:
        if config:
            console.print(f"[blue]Config:[/blue] {config}")
        else:
            console.print("[blue]Config:[/blue] auto-search")

        if llm_config.enabled and llm_config.api_key:
            console.print(
                f"[green]LLM:[/green] enabled ({llm_config.provider}, {llm_config.model})"
            )
        else:
            console.print(
                "[yellow]LLM:[/yellow] not configured (sidecar will be generated without labels)"
            )

    file_path = Path(path)

    if not file_path.exists():
        click.echo(f"Error: File not found: {path}", err=True)
        sys.exit(2)

    supported_extensions = {"pdf", "txt", "md"}
    file_ext = file_path.suffix.lstrip(".").lower()
    if file_ext not in supported_extensions:
        click.echo(f"Error: Unsupported file type: .{file_ext}", err=True)
        sys.exit(1)

    # Output path: .kor extension in .filekor/ subdirectory
    if output:
        sidecar_path = Path(output)
    else:
        # Create in .filekor/ subdirectory (consistent with directory processing)
        filekor_dir = file_path.parent / ".filekor"
        filekor_dir.mkdir(parents=True, exist_ok=True)
        sidecar_path = filekor_dir / f"{file_path.stem}.{file_ext}.kor"

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
            if verbose:
                console.print("[green]Metadata:[/green] extracted")
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
        if verbose:
            console.print(
                f"[green]Text:[/green] {word_count} words, {page_count} pages"
            )
    except Exception as e:
        if verbose:
            console.print(f"[red]Text extraction failed:[/red] {e}")
        pass  # Continue without content

    # Create sidecar with YAML output
    sidecar = Sidecar.create(
        path,
        metadata=metadata,
        content=content_obj,
        labels_config=LabelsConfig.load(),
        text_content=text_content,
        verbose=verbose,
    )

    # Write YAML
    sidecar_path.write_text(sidecar.to_yaml())

    console.print(f"[bold green]Created:[/bold green] {sidecar_path}")

    # Auto-sync to database if enabled
    _auto_sync_hook(sidecar_path, llm_config, verbose)


def _sidecar_directory(
    directory: str,
    output: Optional[str],
    config: Optional[str],
    verbose: bool,
    workers: Optional[int],
    watch: bool,
) -> None:
    """Generate sidecar files for all supported files in a directory."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        click.echo(f"Error: Not a directory: {directory}", err=True)
        sys.exit(1)

    # Load config
    llm_config = LLMConfig.load(config) if config else LLMConfig.load()
    labels_config = LabelsConfig.load()
    workers = workers or llm_config.workers

    if verbose:
        console.print(f"[blue]Workers:[/blue] {workers}")
        console.print(f"[blue]Directory:[/blue] {directory}")

    # Create event emitter
    emitter = create_emitter(watch=watch)

    # Process directory
    output_dir = Path(output) if output else None

    processor = DirectoryProcessor(
        workers=workers,
        output_dir=output_dir,
        llm_config=llm_config,
        labels_config=labels_config,
    )

    # Find files
    from filekor.processor import SUPPORTED_EXTENSIONS

    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(dir_path.glob(f"*.{ext}"))
        files.extend(dir_path.glob(f"**/*.{ext}"))

    if not files:
        console.print(f"[yellow]No supported files found in {directory}[/yellow]")
        sys.exit(0)

    console.print(f"[blue]Found {len(files)} files to process[/blue]")

    # Emit started event
    emitter.started(directory, len(files))

    # Process with callback for events
    successful = 0
    failed = 0

    def on_result(result):
        nonlocal successful, failed
        if result.success:
            successful += 1
            emitter.completed(
                str(result.file_path),
                str(result.output_path),
                result.labels,
            )
            if verbose:
                console.print(f"[green]OK[/green] {result.file_path.name}")
        else:
            failed += 1
            emitter.error(str(result.file_path), result.error or "Unknown error")
            console.print(f"[red]FAIL[/red] {result.file_path.name}: {result.error}")

    results = processor.process_directory(dir_path, callback=on_result)

    # Emit finished event
    emitter.finished(len(results), successful, failed)

    console.print(
        f"\n[bold]Completed:[/bold] {successful}/{len(results)} successful, {failed} failed"
    )
    sys.exit(0 if failed == 0 else 1)


@cli.command()
@click.argument("path")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default=None,
    help="Custom labels.properties file",
)
@click.option(
    "--llm-config",
    type=click.Path(exists=True),
    default=None,
    help="Custom config.yaml file for LLM settings",
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
    "--workers",
    "-w",
    type=int,
    default=None,
    help="Number of parallel workers (default from config)",
)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    help="Enable event emitter for real-time progress",
)
def labels(
    path: str,
    config: Optional[str],
    llm_config: Optional[str],
    directory: bool,
    workers: Optional[int],
    watch: bool,
) -> None:
    """Suggest labels based on file content using LLM and update/create .kor file.

    If .kor exists: loads it and adds labels (overwrites existing labels).
    If .kor does NOT exist: creates new .kor with file info and labels.

    Args:
        path: Path to the file or directory to analyze.
        config: Optional custom labels.properties file path.
        llm_config: Optional custom config.yaml file for LLM settings.
        directory: Whether to process a directory.
        workers: Number of parallel workers.
        watch: Enable event emitter for progress.

    Raises:
        RuntimeError: If LLM is not configured in config.yaml.
    """
    if directory:
        _labels_directory(path, config, llm_config, workers, watch)
    else:
        _labels_file(path, config, llm_config)


def _labels_file(
    path: str,
    config: Optional[str],
    llm_config_path: Optional[str],
) -> None:
    """Suggest labels for a single file."""
    from filekor.sidecar import Sidecar

    file_path = Path(path)
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        sys.exit(2)

    kor_path = file_path.with_suffix(".kor")
    sidecar_file = None
    existing_kor = kor_path.exists()

    # Check if LLM is configured
    llm_config_obj = (
        LLMConfig.load(llm_config_path) if llm_config_path else LLMConfig.load()
    )
    if not llm_config_obj.enabled or not llm_config_obj.api_key:
        console.print(
            "[red]Error: LLM is not configured. Please enable LLM in config.yaml "
            "with a valid API key.[/red]"
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
        console.print("[red]Error: Could not read file content.[/red]")
        sys.exit(1)

    # Get suggestions using LLM only
    try:
        suggestions = suggest_labels(
            content=text_content,
            config=labels_config,
            llm_config=llm_config_obj,
        )
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    if not suggestions:
        console.print("[yellow]No labels suggested for this file.[/yellow]")
        sys.exit(0)

    # Show suggested labels
    for label in suggestions:
        console.print(f"[green]{label}[/green]")

    # Load existing .kor OR create new one
    if existing_kor:
        console.print(f"[blue]Loading existing: {kor_path}[/blue]")
        sidecar_file = Sidecar.load(str(kor_path))
    else:
        console.print(f"[blue]Creating new: {kor_path}[/blue]")
        # Create new sidecar with file info only (no metadata/content extraction here)
        sidecar_file = Sidecar.create(
            path,
            metadata=None,
            content=None,
        )

    # Update labels (overwrite)
    sidecar_file.update_labels(suggestions)

    # Save .kor file
    kor_path.write_text(sidecar_file.to_yaml())

    console.print(f"[bold green]Saved: {kor_path}[/bold green]")

    # Auto-sync to database if enabled
    _auto_sync_hook(kor_path, llm_config_obj, verbose=False)


def _labels_directory(
    directory: str,
    config: Optional[str],
    llm_config_path: Optional[str],
    workers: Optional[int],
    watch: bool,
) -> None:
    """Suggest labels for all supported files in a directory."""
    from filekor.sidecar import Sidecar

    dir_path = Path(directory)
    if not dir_path.is_dir():
        console.print(f"[red]Error: Not a directory: {directory}[/red]")
        sys.exit(1)

    # Load config
    llm_config_obj = (
        LLMConfig.load(llm_config_path) if llm_config_path else LLMConfig.load()
    )
    if not llm_config_obj.enabled or not llm_config_obj.api_key:
        console.print(
            "[red]Error: LLM is not configured. Please enable LLM in config.yaml "
            "with a valid API key.[/red]"
        )
        sys.exit(1)

    labels_config = LabelsConfig.load(config) if config else LabelsConfig.load()
    workers = workers or llm_config_obj.workers

    # Create event emitter
    emitter = create_emitter(watch=watch)

    # Find files
    from filekor.processor import SUPPORTED_EXTENSIONS

    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(dir_path.glob(f"*.{ext}"))
        files.extend(dir_path.glob(f"**/*.{ext}"))

    if not files:
        console.print(f"[yellow]No supported files found in {directory}[/yellow]")
        sys.exit(0)

    console.print(f"[blue]Found {len(files)} files to process[/blue]")
    emitter.started(directory, len(files))

    # Process each file with labels
    successful = 0
    failed = 0

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def process_file(file_path: Path):
        try:
            # Get text content
            text_content, _, _ = extract_text(str(file_path))

            # Get suggestions
            suggestions = suggest_labels(
                content=text_content,
                config=labels_config,
                llm_config=llm_config_obj,
            )

            # Load or create sidecar
            kor_path = file_path.with_suffix(".kor")
            if kor_path.exists():
                sidecar = Sidecar.load(str(kor_path))
            else:
                sidecar = Sidecar.create(str(file_path), metadata=None, content=None)

            # Update labels
            sidecar.update_labels(suggestions)

            # Save
            kor_path.write_text(sidecar.to_yaml())

            return (file_path, True, suggestions, None)
        except Exception as e:
            return (file_path, False, None, str(e))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_file, f): f for f in files}

        for future in as_completed(futures):
            file_path, success, labels, error = future.result()
            if success:
                successful += 1
                emitter.completed(
                    str(file_path), str(file_path.with_suffix(".kor")), labels
                )
                console.print(
                    f"[green]OK[/green] {file_path.name}: {', '.join(labels) if labels else 'no labels'}"
                )
                # Auto-sync to database if enabled
                kor_path = file_path.with_suffix(".kor")
                _auto_sync_hook(kor_path, llm_config_obj, verbose=False)
            else:
                failed += 1
                emitter.error(str(file_path), error)
                console.print(f"[red]FAIL[/red] {file_path.name}: {error}")

    emitter.finished(len(files), successful, failed)
    console.print(
        f"\n[bold]Completed:[/bold] {successful}/{len(files)} successful, {failed} failed"
    )
    sys.exit(0 if failed == 0 else 1)


# Status command for viewing .kor file information
@cli.command()
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
    """Show status for a single file."""
    path = Path(file_path)
    kor_path = path.with_suffix(".kor")

    if not path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        sys.exit(2)

    if not kor_path.exists():
        console.print(f"[yellow]No .kor file found for {path.name}[/yellow]")
        console.print("Run 'filekor sidecar' to generate one.")
        sys.exit(1)

    # Load and display sidecar info
    sidecar = Sidecar.load(str(kor_path))

    table = Table(title=f"Status: {path.name}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Path", str(path))
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
    """Show status for all .kor files in a directory."""
    from filekor.processor import SUPPORTED_EXTENSIONS

    dir_path = Path(directory)
    if not dir_path.is_dir():
        console.print(f"[red]Error: Not a directory: {directory}[/red]")
        sys.exit(1)

    # Find all supported files and .kor files
    supported_files = []
    kor_files = []

    for ext in SUPPORTED_EXTENSIONS:
        for f in dir_path.glob(f"*.{ext}"):
            if f not in supported_files:
                supported_files.append(f)
        for f in dir_path.glob(f"**/*.{ext}"):
            if f not in supported_files:
                supported_files.append(f)

    for f in dir_path.glob("*.kor"):
        if f not in kor_files:
            kor_files.append(f)
    for f in dir_path.glob("**/*.kor"):
        if f not in kor_files:
            kor_files.append(f)

    # Create emitter
    emitter = create_emitter(watch=watch)
    emitter.status(
        directory, [str(f) for f in supported_files], [str(k) for k in kor_files]
    )

    # Display summary
    console.print(f"\n[bold]Directory:[/bold] {directory}")
    console.print(f"[blue]Supported files:[/blue] {len(supported_files)}")
    console.print(f"[green].kor files:[/green] {len(kor_files)}")

    if kor_files:
        console.print("\n[bold].kor Files:[/bold]")
        for kor_file in kor_files:
            try:
                sidecar = Sidecar.load(str(kor_file))
                labels_str = ""
                if sidecar.labels and sidecar.labels.suggested:
                    labels_str = f" [{', '.join(sidecar.labels.suggested)}]"
                console.print(f"  [green]OK[/green] {kor_file.name}{labels_str}")
            except Exception:
                console.print(f"  [red]FAIL[/red] {kor_file.name} (corrupted)")

    # Show files without .kor
    files_without_kor = [
        f for f in supported_files if not f.with_suffix(".kor").exists()
    ]
    if files_without_kor:
        console.print("\n[yellow]Files without .kor:[/yellow]")
        for f in files_without_kor:
            console.print(f"  - {f.name}")

    sys.exit(0)


if __name__ == "__main__":
    cli()
