"""Sidecar command for filekor CLI."""

import sys
from pathlib import Path
from typing import Optional

import click

from filekor.cli.base import console, extract_text
from filekor.adapters.exiftool import PyExifToolAdapter
from filekor.constants import FILEKOR_DIR, KOR_EXTENSION, MERGED_KOR_FILENAME
from filekor.core.hasher import calculate_sha256
from filekor.core.config import FilekorConfig
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
    "--no-merge",
    "no_merge",
    is_flag=True,
    default=False,
    help="Generate individual .kor files instead of merged.kor",
)
@click.option(
    "--db",
    "use_db",
    is_flag=True,
    default=False,
    help="Use database to regenerate .kor files when available",
)
@click.option(
    "--labels",
    "add_labels",
    is_flag=True,
    default=False,
    help="Generate labels via LLM",
)
@click.option(
    "--summary",
    "add_summary",
    is_flag=True,
    default=False,
    help="Generate summaries via LLM (short + long by default)",
)
@click.option(
    "--summary-length",
    type=click.Choice(["short", "long", "both"], case_sensitive=False),
    default=None,
    help="Summary length when --summary is used (default: both)",
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
    no_merge: bool,
    use_db: bool,
    add_labels: bool,
    add_summary: bool,
    summary_length: Optional[str],
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
        no_merge: Generate individual .kor files instead of merged.kor.
        use_db: Use database to regenerate when available.
        add_labels: Generate labels via LLM.
        add_summary: Generate summaries via LLM.
        summary_length: Summary length when add_summary is used ("short", "long", "both").
    """
    if directory:
        _sidecar_directory(
            path, output, config, verbose, workers, watch, no_merge, use_db,
            add_labels, add_summary, summary_length,
        )
    else:
        _sidecar_file(
            path, output, no_cache, config, verbose, no_merge, use_db,
            add_labels, add_summary, summary_length,
        )


def _auto_sync_hook(sidecar_path: Path, auto_sync: bool, verbose: bool) -> None:
    """Auto-sync sidecar to database if enabled."""
    if not auto_sync:
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
    no_merge: bool = False,
    use_db: bool = False,
    add_labels: bool = False,
    add_summary: bool = False,
    summary_length: Optional[str] = None,
) -> None:
    """Generate sidecar for a single file. Uses DirectoryProcessor for consistent behavior."""
    llm_config = LLMConfig.load(config) if config else LLMConfig.load()
    filekor_config = FilekorConfig.load(config) if config else FilekorConfig.load()
    labels_config = LabelsConfig.load()

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

    if add_summary and summary_length is None:
        summary_length = "both"

    do_merge = not no_merge
    output_dir_for_kor = None
    sidecar_path = None

    if not do_merge:
        if output:
            sidecar_path = Path(output)
        else:
            filekor_dir = file_path.parent / FILEKOR_DIR
            filekor_dir.mkdir(parents=True, exist_ok=True)
            sidecar_path = filekor_dir / f"{file_path.stem}.{file_ext}{KOR_EXTENSION}"

        if sidecar_path.exists() and not no_cache:
            click.echo(f"Info: Sidecar already exists: {sidecar_path}", err=True)
            sys.exit(0)
        output_dir_for_kor = sidecar_path.parent

    file_hash = calculate_sha256(path)
    db_record = None
    processed_sidecar = None
    if use_db:
        try:
            from filekor.db import get_file_by_hash

            db_record = get_file_by_hash(file_hash)
            if db_record:
                console.print(
                    f"[green]DB hit:[/green] {file_path.name} ({file_hash[:16]}...)"
                )
                processed_sidecar = Sidecar.load(db_record["kor_path"])
        except Exception:
            pass

    processor = DirectoryProcessor(
        workers=llm_config.workers,
        output_dir=output_dir_for_kor,
        llm_config=llm_config,
        labels_config=labels_config,
        write_kor=not do_merge,
        add_labels=add_labels,
        add_summary=add_summary,
        summary_length=summary_length or "both",
    )

    results = processor.process_directory(file_path.parent, callback=None)

    processed_files = 0
    output_to_sync = None

    for result in results:
        if result.file_path == file_path and result.success:
            processed_files += 1

            if do_merge:
                filekor_dir = file_path.parent / FILEKOR_DIR
                filekor_dir.mkdir(parents=True, exist_ok=True)
                merged_path = filekor_dir / MERGED_KOR_FILENAME

                if result.sidecar:
                    merged_path.write_text(result.sidecar.to_yaml())
                    console.print(f"[bold green]Created:[/bold green] {merged_path}")
                    output_to_sync = merged_path
            else:
                if result.output_path:
                    result.output_path.write_text(result.sidecar.to_yaml())
                    console.print(f"[bold green]Created:[/bold green] {result.output_path}")
                    output_to_sync = result.output_path

    if processed_files == 0 and processed_sidecar:
        if do_merge:
            filekor_dir = file_path.parent / FILEKOR_DIR
            filekor_dir.mkdir(parents=True, exist_ok=True)
            merged_path = filekor_dir / MERGED_KOR_FILENAME
            merged_path.write_text(processed_sidecar.to_yaml())
            console.print(f"[bold green]Created:[/bold green] {merged_path}")
            output_to_sync = merged_path
        else:
            sidecar_path.write_text(processed_sidecar.to_yaml())
            console.print(f"[bold green]Created:[/bold green] {sidecar_path}")
            output_to_sync = sidecar_path

    if output_to_sync:
        _auto_sync_hook(output_to_sync, filekor_config.auto_sync, verbose)


def _discover_files(root: Path) -> dict[Path, list[Path]]:
    """Discover supported files recursively, grouped by parent directory.
    
    Returns:
        Dict mapping parent directory -> list of files in that directory.
    """
    all_files = []
    for ext in SUPPORTED_EXTENSIONS:
        all_files.extend(root.glob(f"**/*.{ext}"))

    seen = set()
    unique_files = [f for f in all_files if f not in seen and FILEKOR_DIR not in f.parts and not seen.add(f)]

    groups: dict[Path, list[Path]] = {}
    for f in unique_files:
        parent = f.parent
        if parent not in groups:
            groups[parent] = []
        groups[parent].append(f)

    return groups





def _write_merged_kor(
    results: list,
    processed_sidecars: list,
    do_merge: bool,
) -> tuple[int, int, list[Path]]:
    """Write merged.kor files for each directory group.
    
    Uses sidecar from result if available, otherwise loads from output_path on disk.
    
    Returns:
        Tuple of (directories_processed, total_files, merged_paths).
    """
    if not do_merge:
        return 0, 0, []

    sidecars_by_dir: dict[Path, list[tuple[Path, Sidecar]]] = {}

    for result in results:
        if not result.success:
            continue
        sidecar = None
        if result.sidecar is not None:
            sidecar = result.sidecar
        elif result.output_path and result.output_path.exists():
            try:
                sidecar = Sidecar.load(str(result.output_path))
            except Exception:
                pass

        if sidecar:
            parent = result.file_path.parent
            if parent not in sidecars_by_dir:
                sidecars_by_dir[parent] = []
            sidecars_by_dir[parent].append((result.file_path, sidecar))

    for file_path, sidecar in processed_sidecars:
        parent = file_path.parent
        if parent not in sidecars_by_dir:
            sidecars_by_dir[parent] = []
        sidecars_by_dir[parent].append((file_path, sidecar))

    total_files = 0
    dirs_merged = 0
    merged_paths: list[Path] = []

    for parent_dir, sidecars in sidecars_by_dir.items():
        if not sidecars:
            continue

        filekor_dir = parent_dir / FILEKOR_DIR
        filekor_dir.mkdir(parents=True, exist_ok=True)
        merged_path = filekor_dir / MERGED_KOR_FILENAME

        merged_yaml = "".join("---\n" + sc.to_yaml() + "\n" for _, sc in sidecars)
        merged_path.write_text(merged_yaml)

        console.print(
            f"[bold green]Merged:[/bold green] {len(sidecars)} files -> {merged_path}"
        )
        merged_paths.append(merged_path)
        total_files += len(sidecars)
        dirs_merged += 1

    return dirs_merged, total_files, merged_paths


def _sidecar_directory(
    directory: str,
    output: Optional[str],
    config: Optional[str],
    verbose: bool,
    workers: Optional[int],
    watch: bool,
    no_merge: bool = False,
    use_db: bool = False,
    add_labels: bool = False,
    add_summary: bool = False,
    summary_length: Optional[str] = None,
) -> None:
    """Generate sidecar files for all supported files in a directory.
    
    Behavior:
        - Default: writes one merged.kor per directory containing files
        - --no-merge: writes individual .kor files per file
        - --labels: adds labels via LLM
        - --summary: adds summaries via LLM
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        click.echo(f"Error: Not a directory: {directory}", err=True)
        sys.exit(1)

    llm_config = LLMConfig.load(config) if config else LLMConfig.load()
    filekor_config = FilekorConfig.load(config) if config else FilekorConfig.load()
    labels_config = LabelsConfig.load()
    workers = workers or llm_config.workers
    do_merge = not no_merge
    if add_summary and summary_length is None:
        summary_length = "both"

    if verbose:
        console.print(f"[blue]Workers:[/blue] {workers}")
        console.print(f"[blue]Directory:[/blue] {directory}")

    emitter = create_emitter(watch=watch)

    file_groups = _discover_files(dir_path)

    flat_files = [f for files in file_groups.values() for f in files]
    if not flat_files:
        console.print(f"[yellow]No supported files found in {directory}[/yellow]")
        sys.exit(0)

    console.print(f"[blue]Found {len(flat_files)} files to process[/blue]")

    processed_sidecars = []
    if use_db:
        try:
            from filekor.db import get_file_by_hash

            console.print("[blue]Using database for regeneration when available[/blue]")
            for file_path in flat_files:
                file_hash = calculate_sha256(str(file_path))
                db_record = get_file_by_hash(file_hash)
                if db_record:
                    console.print(
                        f"[green]DB hit:[/green] {file_path.name} ({file_hash[:16]}...)"
                    )
                    try:
                        sidecar = Sidecar.load(db_record["kor_path"])
                        processed_sidecars.append((file_path, sidecar))
                        flat_files.remove(file_path)
                    except Exception:
                        pass
        except Exception:
            console.print(
                "[yellow]Database not available, processing normally[/yellow]"
            )

    output_dir = Path(output) if output else None

    processor = DirectoryProcessor(
        workers=workers,
        output_dir=output_dir,
        llm_config=llm_config,
        labels_config=labels_config,
        write_kor=not do_merge,
        add_labels=add_labels,
        add_summary=add_summary,
        summary_length=summary_length or "both",
    )

    emitter.started(directory, len(flat_files))

    successful = 0
    failed = 0

    def on_result(result):
        nonlocal successful, failed
        if result.success:
            successful += 1
            emitter.completed(
                str(result.file_path),
                str(result.output_path) if result.output_path else "",
                result.labels,
            )
            if verbose:
                console.print(f"[green]OK[/green] {result.file_path.name}")
            if result.output_path:
                _auto_sync_hook(result.output_path, filekor_config.auto_sync, verbose)
        else:
            failed += 1
            emitter.error(str(result.file_path), result.error or "Unknown error")
            console.print(f"[red]FAIL[/red] {result.file_path.name}: {result.error}")

    results = processor.process_directory(dir_path, callback=on_result)

    dirs_merged, total_files, merged_paths = _write_merged_kor(
        results, processed_sidecars, do_merge
    )

    for merged_path in merged_paths:
        _auto_sync_hook(merged_path, filekor_config.auto_sync, verbose)

    emitter.finished(len(results), successful, failed)

    console.print(
        f"\n[bold]Completed:[/bold] {successful}/{len(results)} successful, {failed} failed"
    )

    sys.exit(0 if failed == 0 else 1)
