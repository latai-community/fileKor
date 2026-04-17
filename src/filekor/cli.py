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

    # Find all supported files (recursive, unique, excluding .filekor/ directories)
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(dir_path.glob(f"**/*.{ext}"))

    # Remove duplicates and exclude files in .filekor/ directories
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
        return
    else:
        _sidecar_file(path, output, no_cache, config, verbose)
        return


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
    try:
        _, word_count, page_count = extract_text(path)
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

    # Find files (recursive, unique, excluding .filekor/ directories)
    from filekor.processor import SUPPORTED_EXTENSIONS

    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(dir_path.glob(f"**/*.{ext}"))

    # Remove duplicates and exclude files in .filekor/ directories
    seen = set()
    unique_files = []
    for f in files:
        if f not in seen and ".filekor" not in f.parts:
            seen.add(f)
            unique_files.append(f)
    files = unique_files

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
            # Auto-sync to database if enabled
            if result.output_path:
                _auto_sync_hook(result.output_path, llm_config, verbose)
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

    # Get kor path in .filekor/ subdirectory
    file_ext = file_path.suffix.lstrip(".").lower()
    filekor_dir = file_path.parent / ".filekor"
    kor_path = filekor_dir / f"{file_path.stem}.{file_ext}.kor"
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
        # Ensure .filekor directory exists
        filekor_dir.mkdir(parents=True, exist_ok=True)
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

    # Find files (recursive, unique, excluding .filekor/ directories)
    from filekor.processor import SUPPORTED_EXTENSIONS

    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(dir_path.glob(f"**/*.{ext}"))

    # Remove duplicates and exclude files in .filekor/ directories
    seen = set()
    unique_files = []
    for f in files:
        if f not in seen and ".filekor" not in f.parts:
            seen.add(f)
            unique_files.append(f)
    files = unique_files

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

            # Load or create sidecar (in .filekor/ subdirectory)
            file_ext = file_path.suffix.lstrip(".").lower()
            filekor_dir = file_path.parent / ".filekor"
            kor_path = filekor_dir / f"{file_path.stem}.{file_ext}.kor"

            if kor_path.exists():
                sidecar = Sidecar.load(str(kor_path))
            else:
                # Create sidecar with file info
                sidecar = Sidecar.create(str(file_path), metadata=None, content=None)
                # Ensure .filekor directory exists
                filekor_dir.mkdir(parents=True, exist_ok=True)

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
                # Get the kor_path (defined in process_file closure)
                file_ext = file_path.suffix.lstrip(".").lower()
                kor_path = (
                    file_path.parent / ".filekor" / f"{file_path.stem}.{file_ext}.kor"
                )
                emitter.completed(str(file_path), str(kor_path), labels)
                console.print(
                    f"[green]OK[/green] {file_path.name}: {', '.join(labels) if labels else 'no labels'}"
                )
                # Auto-sync to database if enabled (kor_path defined in process_file)
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
    """Show status for a single file using status module."""
    from filekor.status import get_file_status, summarize

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

    # Load and display sidecar info
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
    from filekor.status import get_directory_status

    dir_path = Path(directory)
    if not dir_path.is_dir():
        console.print(f"[red]Error: Not a directory: {directory}[/red]")
        sys.exit(1)

    # Get directory status from status module
    status = get_directory_status(directory, recursive=True)

    # Create emitter
    emitter = create_emitter(watch=watch)
    emitter.status(
        directory,
        [str(s.file_path) for s in status.file_statuses],
        [str(s.kor_path) for s in status.file_statuses if s.exists],
    )

    # Display summary
    console.print(f"\n[bold]Directory:[/bold] {directory}")
    console.print(f"[blue]Supported files:[/blue] {status.total_files}")
    console.print(f"[green].kor files:[/green] {status.kor_files}")

    if status.file_statuses:
        # Show .kor files with status
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

        # Show files without .kor
        if status.files_without_kor:
            console.print("\n[yellow]Files without .kor:[/yellow]")
            for f in status.files_without_kor:
                console.print(f"  - {f.name}")

    sys.exit(0)


@cli.command()
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
    from filekor.db import sync_file

    if directory or Path(path).is_dir():
        dir_path = Path(path)
        # Find all .kor files (excluding .filekor/ directories to avoid recursion)
        kor_files = list(dir_path.glob("**/*.kor"))
        kor_files = [f for f in kor_files if ".filekor" not in f.parts]

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
        # Single file
        kor_path = Path(path)
        if not kor_path.suffix == ".kor":
            console.print("[red]Error: File must have .kor extension[/red]")
            sys.exit(1)

        try:
            sync_file(str(kor_path))
            console.print(f"[bold green]Synced:[/bold green] {kor_path}")
            sys.exit(0)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)


if __name__ == "__main__":
    cli()
