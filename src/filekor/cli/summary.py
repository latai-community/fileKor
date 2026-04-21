"""Summary command for filekor CLI."""

import sys
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import click

from filekor.cli.base import console, extract_text
from filekor.core.labels import LLMConfig
from filekor.core.summary import generate_summary, SummaryResult
from filekor.core.processor import SUPPORTED_EXTENSIONS
from filekor.sidecar import Sidecar, FileSummary
from filekor.core.events import create_emitter


@click.command()
@click.argument("path")
@click.option(
    "--short",
    "length_short",
    is_flag=True,
    default=False,
    help="Generate short summary only",
)
@click.option(
    "--long",
    "length_long",
    is_flag=True,
    default=False,
    help="Generate long summary only",
)
@click.option(
    "--max-chars",
    type=int,
    default=None,
    help="Maximum characters to send to LLM (overrides config)",
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
def summary(
    path: str,
    length_short: bool,
    length_long: bool,
    max_chars: Optional[int],
    llm_config: Optional[str],
    directory: bool,
    workers: Optional[int],
    watch: bool,
) -> None:
    """Generate summaries for files using LLM and update/create .kor file.

    If .kor exists: loads it and updates summary (overwrites existing).
    If .kor does NOT exist: creates new .kor with file info and summary.

    By default generates both short and long summaries.
    Use --short or --long to generate only one.
    """
    if directory:
        _summary_directory(
            path, length_short, length_long, max_chars, llm_config, workers, watch
        )
    else:
        _summary_file(path, length_short, length_long, max_chars, llm_config)


def _resolve_length(short: bool, long: bool) -> str:
    """Resolve which summaries to generate based on flags.

    Args:
        short: --short flag.
        long: --long flag.

    Returns:
        "short", "long", or "both".
    """
    if short and long:
        return "both"
    if short:
        return "short"
    if long:
        return "long"
    return "both"


def _summary_file(
    path: str,
    length_short: bool,
    length_long: bool,
    max_chars: Optional[int],
    llm_config_path: Optional[str],
) -> None:
    """Generate summary for a single file."""
    file_path = Path(path)
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        sys.exit(2)

    file_ext = file_path.suffix.lstrip(".").lower()
    filekor_dir = file_path.parent / ".filekor"
    kor_path = filekor_dir / f"{file_path.stem}.{file_ext}.kor"
    existing_kor = kor_path.exists()

    llm_config_obj = (
        LLMConfig.load(llm_config_path) if llm_config_path else LLMConfig.load()
    )
    if not llm_config_obj.enabled or not llm_config_obj.api_key:
        console.print(
            "[red]Error: LLM is not configured. Please enable LLM in config.yaml "
            "with a valid API key.[/red]"
        )
        sys.exit(1)

    length = _resolve_length(length_short, length_long)

    text_content = None
    try:
        text_content, _, _ = extract_text(path)
    except Exception:
        console.print("[red]Error: Could not read file content.[/red]")
        sys.exit(1)

    try:
        result = generate_summary(
            content=text_content,
            length=length,
            llm_config=llm_config_obj,
            max_chars=max_chars,
        )
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    if result.short:
        console.print(f"[green]Short:[/green] {result.short}")
    if result.long:
        console.print(f"[green]Long:[/green]  {result.long}")

    if existing_kor:
        console.print(f"[blue]Loading existing: {kor_path}[/blue]")
        sidecar_file = Sidecar.load(str(kor_path))
    else:
        console.print(f"[blue]Creating new: {kor_path}[/blue]")
        filekor_dir.mkdir(parents=True, exist_ok=True)
        sidecar_file = Sidecar.create(
            path,
            metadata=None,
            content=None,
        )

    if sidecar_file.summary is None:
        sidecar_file.summary = FileSummary()

    if result.short:
        sidecar_file.summary.short = result.short
    if result.long:
        sidecar_file.summary.long = result.long

    kor_path.write_text(sidecar_file.to_yaml())

    _auto_sync_hook(kor_path, llm_config_obj)
    console.print(f"[bold green]Saved: {kor_path}[/bold green]")


def _summary_directory(
    directory: str,
    length_short: bool,
    length_long: bool,
    max_chars: Optional[int],
    llm_config_path: Optional[str],
    workers: Optional[int],
    watch: bool,
) -> None:
    """Generate summaries for all supported files in a directory."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        console.print(f"[red]Error: Not a directory: {directory}[/red]")
        sys.exit(1)

    llm_config_obj = (
        LLMConfig.load(llm_config_path) if llm_config_path else LLMConfig.load()
    )
    if not llm_config_obj.enabled or not llm_config_obj.api_key:
        console.print(
            "[red]Error: LLM is not configured. Please enable LLM in config.yaml "
            "with a valid API key.[/red]"
        )
        sys.exit(1)

    workers = workers or llm_config_obj.workers
    length = _resolve_length(length_short, length_long)

    emitter = create_emitter(watch=watch)

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
        console.print(f"[yellow]No supported files found in {directory}[/yellow]")
        sys.exit(0)

    console.print(f"[blue]Found {len(files)} files to process[/blue]")
    emitter.started(directory, len(files))

    successful = 0
    failed = 0

    def process_file(file_path: Path):
        try:
            text_content, _, _ = extract_text(str(file_path))

            result = generate_summary(
                content=text_content,
                length=length,
                llm_config=llm_config_obj,
                max_chars=max_chars,
            )

            file_ext = file_path.suffix.lstrip(".").lower()
            filekor_dir = file_path.parent / ".filekor"
            kor_path = filekor_dir / f"{file_path.stem}.{file_ext}.kor"

            if kor_path.exists():
                sidecar = Sidecar.load(str(kor_path))
            else:
                sidecar = Sidecar.create(str(file_path), metadata=None, content=None)
                filekor_dir.mkdir(parents=True, exist_ok=True)

            if sidecar.summary is None:
                sidecar.summary = FileSummary()

            if result.short:
                sidecar.summary.short = result.short
            if result.long:
                sidecar.summary.long = result.long

            kor_path.write_text(sidecar.to_yaml())

            return (file_path, True, result, None)
        except Exception as e:
            return (file_path, False, None, str(e))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_file, f): f for f in files}

        for future in as_completed(futures):
            file_path, success, result, error = future.result()
            if success:
                successful += 1
                file_ext = file_path.suffix.lstrip(".").lower()
                kor_path = (
                    file_path.parent / ".filekor" / f"{file_path.stem}.{file_ext}.kor"
                )
                _auto_sync_hook(kor_path, llm_config_obj)
                short_preview = (result.short[:60] + "...") if result.short else "none"
                emitter.completed(str(file_path), str(kor_path))
                console.print(f"[green]OK[/green] {file_path.name}: {short_preview}")
            else:
                failed += 1
                emitter.error(str(file_path), error)
                console.print(f"[red]FAIL[/red] {file_path.name}: {error}")

    emitter.finished(len(files), successful, failed)
    console.print(
        f"\n[bold]Completed:[/bold] {successful}/{len(files)} successful, {failed} failed"
    )
    sys.exit(0 if failed == 0 else 1)


def _auto_sync_hook(kor_path: Path, llm_config: LLMConfig) -> None:
    """Auto-sync sidecar to database if enabled."""
    if not llm_config.auto_sync:
        return

    try:
        from filekor.db import sync_file

        sync_file(str(kor_path))
    except Exception:
        pass
