"""Labels command for filekor CLI."""

import sys
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import click

from filekor.cli.base import console, extract_text
from filekor.constants import FILEKOR_DIR, KOR_EXTENSION
from filekor.core.labels import LabelsConfig, LLMConfig, suggest_labels
from filekor.core.processor import SUPPORTED_EXTENSIONS
from filekor.sidecar import Sidecar
from filekor.core.events import create_emitter


@click.command()
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
    file_path = Path(path)
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        sys.exit(2)

    file_ext = file_path.suffix.lstrip(".").lower()
    filekor_dir = file_path.parent / FILEKOR_DIR
    kor_path = filekor_dir / f"{file_path.stem}.{file_ext}{KOR_EXTENSION}"
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

    labels_config = None
    if config:
        labels_config = LabelsConfig.load(config)
    else:
        labels_config = LabelsConfig.load()

    text_content = None
    try:
        text_content, _, _ = extract_text(path)
    except Exception:
        console.print("[red]Error: Could not read file content.[/red]")
        sys.exit(1)

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

    for label in suggestions:
        console.print(f"[green]{label}[/green]")

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

    sidecar_file.update_labels(suggestions)

    kor_path.write_text(sidecar_file.to_yaml())

    _auto_sync_hook(kor_path, llm_config_obj)
    console.print(f"[bold green]Saved: {kor_path}[/bold green]")


def _auto_sync_hook(kor_path: Path, llm_config: LLMConfig) -> None:
    """Auto-sync sidecar to database if enabled."""
    if not llm_config.auto_sync:
        return

    try:
        from filekor.db import sync_file

        sync_file(str(kor_path))
    except Exception:
        pass


def _labels_directory(
    directory: str,
    config: Optional[str],
    llm_config_path: Optional[str],
    workers: Optional[int],
    watch: bool,
) -> None:
    """Suggest labels for all supported files in a directory."""
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

    labels_config = LabelsConfig.load(config) if config else LabelsConfig.load()
    workers = workers or llm_config_obj.workers

    emitter = create_emitter(watch=watch)

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
    emitter.started(directory, len(files))

    successful = 0
    failed = 0

    def process_file(file_path: Path):
        try:
            text_content, _, _ = extract_text(str(file_path))

            suggestions = suggest_labels(
                content=text_content,
                config=labels_config,
                llm_config=llm_config_obj,
            )

            file_ext = file_path.suffix.lstrip(".").lower()
            filekor_dir = file_path.parent / FILEKOR_DIR
            kor_path = filekor_dir / f"{file_path.stem}.{file_ext}{KOR_EXTENSION}"

            if kor_path.exists():
                sidecar = Sidecar.load(str(kor_path))
            else:
                sidecar = Sidecar.create(str(file_path), metadata=None, content=None)
                filekor_dir.mkdir(parents=True, exist_ok=True)

            sidecar.update_labels(suggestions)

            kor_path.write_text(sidecar.to_yaml())
            _auto_sync_hook(kor_path, llm_config_obj)

            return (file_path, True, suggestions, None)
        except Exception as e:
            return (file_path, False, None, str(e))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_file, f): f for f in files}

        for future in as_completed(futures):
            file_path, success, labels, error = future.result()
            if success:
                successful += 1
                file_ext = file_path.suffix.lstrip(".").lower()
                kor_path = (
                    file_path.parent
                    / FILEKOR_DIR
                    / f"{file_path.stem}.{file_ext}{KOR_EXTENSION}"
                )
                emitter.completed(str(file_path), str(kor_path), labels)
                console.print(
                    f"[green]OK[/green] {file_path.name}: {', '.join(labels) if labels else 'no labels'}"
                )
            else:
                failed += 1
                emitter.error(str(file_path), error)
                console.print(f"[red]FAIL[/red] {file_path.name}: {error}")

    emitter.finished(len(files), successful, failed)
    console.print(
        f"\n[bold]Completed:[/bold] {successful}/{len(files)} successful, {failed} failed"
    )
    sys.exit(0 if failed == 0 else 1)
