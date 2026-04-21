"""Sidecar command for filekor CLI."""

import sys
from pathlib import Path
from typing import Optional

import click

from filekor.cli.base import console, extract_text
from filekor.adapters.exiftool import PyExifToolAdapter
from filekor.constants import FILEKOR_DIR, KOR_EXTENSION, MERGED_KOR_FILENAME
from filekor.core.hasher import calculate_sha256
from filekor.core.labels import LabelsConfig, LLMConfig
from filekor.core.processor import DirectoryProcessor, SUPPORTED_EXTENSIONS
from filekor.sidecar import Sidecar, Content
from filekor.core.events import create_emitter


@click.command()
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
    else:
        _sidecar_file(path, output, no_cache, config, verbose, merge, no_merge, use_db)


def _auto_sync_hook(sidecar_path: Path, llm_config: LLMConfig, verbose: bool) -> None:
    """Auto-sync sidecar to database if enabled."""
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
    llm_config = LLMConfig.load(config) if config else LLMConfig.load()

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

    if output:
        sidecar_path = Path(output)
    else:
        filekor_dir = file_path.parent / FILEKOR_DIR
        filekor_dir.mkdir(parents=True, exist_ok=True)
        sidecar_path = filekor_dir / f"{file_path.stem}.{file_ext}{KOR_EXTENSION}"

    if sidecar_path.exists() and not no_cache:
        click.echo(f"Info: Sidecar already exists: {sidecar_path}", err=True)
        sys.exit(0)

    file_hash = calculate_sha256(path)

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
            pass

    adapter = PyExifToolAdapter()
    exif_available = adapter.is_available()

    metadata = None
    if exif_available:
        try:
            metadata = adapter.extract_metadata(path)
            if verbose:
                console.print("[green]Metadata:[/green] extracted")
        except (FileNotFoundError, PermissionError, Exception):
            pass

    content_obj = None
    try:
        _, word_count, page_count = extract_text(path)
        content_obj = Content(
            language="en",
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
        pass

    sidecar = Sidecar.create(
        path,
        metadata=metadata,
        content=content_obj,
        verbose=verbose,
    )

    do_merge = not no_merge

    output_to_sync = None

    if do_merge:
        filekor_dir = file_path.parent / FILEKOR_DIR
        filekor_dir.mkdir(parents=True, exist_ok=True)
        merged_path = filekor_dir / MERGED_KOR_FILENAME
        merged_path.write_text(sidecar.to_yaml())
        console.print(f"[bold green]Created:[/bold green] {merged_path}")
        output_to_sync = merged_path
    else:
        sidecar_path.write_text(sidecar.to_yaml())
        console.print(f"[bold green]Created:[/bold green] {sidecar_path}")
        output_to_sync = sidecar_path

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

    llm_config = LLMConfig.load(config) if config else LLMConfig.load()
    labels_config = LabelsConfig.load()
    workers = workers or llm_config.workers

    if verbose:
        console.print(f"[blue]Workers:[/blue] {workers}")
        console.print(f"[blue]Directory:[/blue] {directory}")

    emitter = create_emitter(watch=watch)

    do_merge = merge if merge is not None else True
    if no_merge:
        do_merge = False

    output_dir = Path(output) if output else None

    processor = DirectoryProcessor(
        workers=workers,
        output_dir=output_dir,
        llm_config=llm_config,
        labels_config=labels_config,
    )

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
        console.print(f"[yellow]No supported files found in {directory}[/yellow]")
        sys.exit(0)

    console.print(f"[blue]Found {len(files)} files to process[/blue]")

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

    if use_db and db_available:
        processed_files = []
        for file_path in files:
            file_hash = calculate_sha256(str(file_path))

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

    emitter.started(directory, len(files))

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
            if result.output_path:
                _auto_sync_hook(result.output_path, llm_config, verbose)
        else:
            failed += 1
            emitter.error(str(result.file_path), result.error or "Unknown error")
            console.print(f"[red]FAIL[/red] {result.file_path.name}: {result.error}")

    results = processor.process_directory(dir_path, callback=on_result)

    for result in results:
        if result.success and result.output_path:
            try:
                sidecar = Sidecar.load(str(result.output_path))
                processed_sidecars.append((result.file_path, sidecar))
            except Exception:
                pass

    if do_merge and processed_sidecars:
        filekor_dir = dir_path / FILEKOR_DIR
        filekor_dir.mkdir(parents=True, exist_ok=True)
        merged_path = filekor_dir / MERGED_KOR_FILENAME

        merged_yaml = ""
        for _, sidecar in processed_sidecars:
            merged_yaml += sidecar.to_yaml() + "\n"

        merged_path.write_text(merged_yaml)
        console.print(
            f"[bold green]Merged:[/bold green] {len(processed_sidecars)} files -> {merged_path}"
        )

    emitter.finished(len(results), successful, failed)

    console.print(
        f"\n[bold]Completed:[/bold] {successful}/{len(results)} successful, {failed} failed"
    )
    sys.exit(0 if failed == 0 else 1)
