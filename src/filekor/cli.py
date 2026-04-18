"""CLI interface using Click."""

import sys
from pathlib import Path
from typing import Optional, List

import click
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from filekor.adapters.exiftool import PyExifToolAdapter
from filekor.hasher import calculate_sha256
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
@click.option(
    "--merge",
    "merge",
    is_flag=True,
    default=None,
    help="Generate merged .kor file (default for directories)",
)
@click.option(
    "--no-merge",
    "no_merge",
    is_flag=True,
    default=False,
    help="Generate individual .kor files (one per file)",
)
@click.option(
    "--db",
    "use_db",
    is_flag=True,
    default=False,
    help="Use database to regenerate .kor files when available",
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
    merge: Optional[bool],
    no_merge: bool,
    use_db: bool,
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
        _sidecar_directory(
            path, output, config, verbose, workers, watch, merge, no_merge, use_db
        )
        return
    else:
        _sidecar_file(path, output, no_cache, config, verbose, merge, no_merge, use_db)
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
    merge: Optional[bool] = None,
    no_merge: bool = False,
    use_db: bool = False,
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

    # Handle --db: check database first for this file
    import hashlib

    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    file_hash = h.hexdigest()

    db_record = None
    if use_db:
        try:
            from filekor.db import get_file_by_hash

            db_record = get_file_by_hash(file_hash)
            if db_record:
                console.print(
                    f"[green]DB hit:[/green] {file_path.name} ({file_hash[:16]}...)"
                )
        except Exception:
            pass  # Continue with normal processing

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
    # Handle merge for single files: by default generates merged.kor unless --no-merge
    do_merge = (
        not no_merge
    )  # Default for single file is merge (unless --no-merge is set)

    output_to_sync = None

    if do_merge:
        # Generate merged.kor even for single file
        filekor_dir = file_path.parent / ".filekor"
        filekor_dir.mkdir(parents=True, exist_ok=True)
        merged_path = filekor_dir / "merged.kor"
        merged_path.write_text(sidecar.to_yaml())
        console.print(f"[bold green]Created:[/bold green] {merged_path}")
        output_to_sync = merged_path
    else:
        # Individual .kor
        sidecar_path.write_text(sidecar.to_yaml())
        console.print(f"[bold green]Created:[/bold green] {sidecar_path}")
        output_to_sync = sidecar_path

    # Auto-sync to database if enabled
    if output_to_sync:
        _auto_sync_hook(output_to_sync, llm_config, verbose)


def _sidecar_directory(
    directory: str,
    output: Optional[str],
    config: Optional[str],
    verbose: bool,
    workers: Optional[int],
    watch: bool,
    merge: Optional[bool] = None,
    no_merge: bool = False,
    use_db: bool = False,
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

    # Determine merge behavior
    # Default for directories is merge=True, unless --no-merge is explicitly set
    do_merge = merge if merge is not None else True
    if no_merge:
        do_merge = False

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
    import hashlib

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

    # Handle --db flag: check database first
    processed_sidecars = []
    db_available = False

    if use_db:
        try:
            from filekor.db import get_file_by_hash

            db_available = True
            console.print("[blue]Using database for regeneration when available[/blue]")
        except Exception:
            console.print(
                "[yellow]Database not available, processing normally[/yellow]"
            )

    # Pre-process: check DB for each file if --db is specified
    if use_db and db_available:
        processed_files = []
        for file_path in files:
            h = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            file_hash = h.hexdigest()

            db_record = get_file_by_hash(file_hash)
            if db_record:
                console.print(
                    f"[green]DB hit:[/green] {file_path.name} ({file_hash[:16]}...)"
                )
                try:
                    sidecar = Sidecar.load(db_record["kor_path"])
                    processed_sidecars.append((file_path, sidecar))
                except Exception:
                    processed_files.append(file_path)
            else:
                processed_files.append(file_path)

        files = processed_files

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

    # Add processed results to merged sidecars list
    for result in results:
        if result.success and result.output_path:
            try:
                sidecar = Sidecar.load(str(result.output_path))
                processed_sidecars.append((result.file_path, sidecar))
            except Exception:
                pass

    # Handle merge output
    if do_merge and processed_sidecars:
        filekor_dir = dir_path / ".filekor"
        filekor_dir.mkdir(parents=True, exist_ok=True)
        merged_path = filekor_dir / "merged.kor"

        merged_yaml = ""
        for _, sidecar in processed_sidecars:
            merged_yaml += sidecar.to_yaml() + "\n"

        merged_path.write_text(merged_yaml)
        console.print(
            f"[bold green]Merged:[/bold green] {len(processed_sidecars)} files -> {merged_path}"
        )

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


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file for merged .kor (default: {directory}/.filekor/merged.kor)",
)
@click.option(
    "--no-erase",
    "no_erase",
    is_flag=True,
    default=False,
    help="Keep original .kor files after merge",
)
def merge(directory: str, output: Optional[str], no_erase: bool) -> None:
    """Merge multiple .kor files into a single aggregated .kor file.

    Finds all *.kor files in the .filekor/ subdirectory of the specified path
    and combines them into a single merged .kor file (YAML list format).

    Args:
        directory: Path containing .kor files to merge.
        output: Optional output path for merged .kor file.
        no_erase: Keep original .kor files after merge.
    """
    import yaml

    dir_path = Path(directory)
    filekor_dir = dir_path / ".filekor"

    if not filekor_dir.is_dir():
        console.print(f"[red]Error: .filekor directory not found: {filekor_dir}[/red]")
        sys.exit(1)

    kor_files = list(filekor_dir.glob("*.kor"))
    if not kor_files:
        console.print(f"[yellow]No .kor files found in {filekor_dir}[/yellow]")
        sys.exit(0)

    console.print(f"[blue]Found {len(kor_files)} .kor files to merge[/blue]")

    merged_sidecars = []
    for kor_file in kor_files:
        try:
            sidecar = Sidecar.load(str(kor_file))
            merged_sidecars.append(sidecar)
        except Exception as e:
            console.print(f"[red]Error loading {kor_file.name}: {e}[/red]")
            continue

    if not merged_sidecars:
        console.print("[red]Error: No valid .kor files could be loaded[/red]")
        sys.exit(1)

    merged_yaml = ""
    for sidecar in merged_sidecars:
        yaml_str = sidecar.to_yaml()
        merged_yaml += yaml_str + "\n"

    output_path = Path(output) if output else filekor_dir / "merged.kor"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(merged_yaml)

    console.print(
        f"[bold green]Merged:[/bold green] {len(merged_sidecars)} files -> {output_path}"
    )

    if not no_erase:
        for kor_file in kor_files:
            try:
                kor_file.unlink()
                if verbose:
                    console.print(f"[dim]Deleted:[/dim] {kor_file.name}")
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not delete {kor_file.name}: {e}[/yellow]"
                )

    console.print(f"[bold]Completed:[/bold] {len(merged_sidecars)} files merged")


@cli.command()
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

    Args:
        directory: Directory to search for .kor files.
        sha: Direct SHA256 hash of file to delete.
        path: Path to file (SHA256 calculated internally).
        input: File with SHA256 hashes (one per line).
        db: Delete only from database.
        file_flag: Delete only .kor files (not from database).
        all: Delete from both database and .kor files.
        verbose: Show detailed output.
        dry_run: Show what would be deleted without actually deleting.
        force: Skip confirmation prompt.
        no_recursive: Do not search in subdirectories.
        max_depth: Maximum directory depth to search.
    """
    import hashlib

    if not sha and not path and not input:
        console.print("[red]Error: Must specify --sha, --path, or --input[/red]")
        sys.exit(1)

    target_scope = "all"
    if db:
        target_scope = "db"
    elif file_flag:
        target_scope = "file"
    elif all:
        target_scope = "all"

    def get_target_hashes() -> List[str]:
        """Get list of target hashes to delete."""
        hashes = []
        if sha:
            hashes.append(sha)
        if path:
            file_hash = calculate_sha256(path)
            hashes.append(file_hash)
        if input:
            input_path = Path(input)
            for line in input_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    hashes.append(line)
        return hashes

    hashes = get_target_hashes()

    dir_path = Path(directory)
    recursive = not no_recursive
    depth = max_depth if max_depth else -1

    console.print(
        f"[blue]Processing {len(hashes)} hash(es) in {directory} with scope: {target_scope}[/blue]"
    )

    deleted_db = 0
    deleted_files = 0
    to_delete_files = []
    to_delete_db = []

    for target_sha in hashes:
        if target_scope in ("all", "db"):
            if dry_run:
                to_delete_db.append(target_sha)
            else:
                try:
                    from filekor.db import delete_file_by_hash

                    count = delete_file_by_hash(target_sha)
                    deleted_db += count
                    if verbose:
                        console.print(
                            f"[green]DB deleted:[/green] {count} record(s) for {target_sha[:16]}..."
                        )
                except Exception as e:
                    if verbose:
                        console.print(f"[red]DB error:[/red] {e}")

        if target_scope in ("all", "file"):
            from filekor.status import get_directory_status

            try:
                status = get_directory_status(str(dir_path), recursive=recursive, max_depth=depth)
                for file_status in status.file_statuses:
                    if (
                        file_status.sidecar
                        and file_status.sidecar.file.hash_sha256 == target_sha
                    ):
                        if dry_run:
                            to_delete_files.append((file_status.sidecar.file.name, str(file_status.kor_path)))
                        else:
                            try:
                                file_status.kor_path.unlink()
                                deleted_files += 1
                                if verbose:
                                    console.print(
                                        f"[green]File deleted:[/green] {file_status.kor_path}"
                                    )
                            except Exception as e:
                                if verbose:
                                    console.print(f"[red]File error:[/red] {e}")
            except Exception as e:
                if verbose:
                    console.print(f"[red]Search error:[/red] {e}")

    if dry_run:
        console.print("\n[bold yellow]Dry Run - Would delete:[/bold yellow]")
        if to_delete_db:
            console.print("[blue]From database:[/blue]")
            for h in to_delete_db:
                console.print(f"  - {h[:16]}...")
        if to_delete_files:
            console.print("[blue]Files:[/blue]")
            for name, path in to_delete_files:
                console.print(f"  - {name} ({path})")
    else:
        if not force and (deleted_db > 0 or deleted_files > 0):
            confirm = click.confirm(
                f"Delete {deleted_files} file(s) and {deleted_db} DB record(s)?",
                default=False,
            )
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                sys.exit(0)

    console.print(f"[bold]Deleted:[/bold] {deleted_db} from DB, {deleted_files} files")


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output as JSON",
)
@click.option(
    "--csv",
    "output_csv",
    is_flag=True,
    default=False,
    help="Output as CSV",
)
@click.option(
    "--sha-only",
    "sha_only",
    is_flag=True,
    default=False,
    help="Output only SHA256 hashes (one per line)",
)
@click.option(
    "--ext",
    "extension",
    type=str,
    default=None,
    help="Filter by file extension (e.g., pdf, md, txt)",
)
@click.option(
    "--include-merged",
    "include_merged",
    is_flag=True,
    default=False,
    help="Include individual entries from merged.kor files",
)
def list(
    directory: str,
    output_json: bool,
    output_csv: bool,
    sha_only: bool,
    extension: Optional[str],
    include_merged: bool,
) -> None:
    """List SHA256 hashes and file names for all .kor files in a directory.

    Args:
        directory: Path to directory containing .kor files.
        output_json: Output as JSON.
        output_csv: Output as CSV.
        sha_only: Output only SHA256 hashes.
        extension: Filter by file extension.
        include_merged: Include entries from merged.kor files.
    """
    from filekor.sidecar import Sidecar
    from filekor.status import get_directory_status
    from filekor.merge import load_merged_kor

    dir_path = Path(directory)

    results = []

    if include_merged:
        filekor_dir = dir_path / ".filekor"
        if filekor_dir.is_dir():
            merged_files = list(filekor_dir.glob("merged*.kor"))
            for merged_file in merged_files:
                try:
                    sidecar_list = load_merged_kor(str(merged_file))
                    for sc in sidecar_list:
                        results.append({
                            "sha256": sc.file.hash_sha256,
                            "name": sc.file.name,
                            "path": str(merged_file),
                            "type": "merged",
                        })
                except Exception:
                    pass

    status = get_directory_status(str(dir_path), recursive=True)

    for file_status in status.file_statuses:
        if not file_status.exists or not file_status.sidecar:
            continue

        file_ext = file_status.sidecar.file.extension
        if extension and file_ext.lower() != extension.lower():
            continue

        results.append({
            "sha256": file_status.sidecar.file.hash_sha256,
            "name": file_status.sidecar.file.name,
            "path": str(file_status.kor_path),
            "type": "individual",
        })

    if sha_only:
        for r in results:
            console.print(r["sha256"])
    elif output_json:
        import json
        console.print(json.dumps(results, indent=2))
    elif output_csv:
        console.print("sha256,name,path,type")
        for r in results:
            console.print(f"{r['sha256']},{r['name']},{r['path']},{r['type']}")
    else:
        for r in results:
            short_sha = r["sha256"][:16] + "..."
            type_marker = f"({r['type']})" if r["type"] == "merged" else ""
            console.print(f"{short_sha} {r['name']} {type_marker}")

    console.print(f"\n[bold]Total:[/bold] {len(results)} files")


if __name__ == "__main__":
    cli()
