"""Database command group for filekor CLI."""

import sqlite3
import sys
from pathlib import Path
from typing import Optional

import click
from rich.table import Table

from filekor.cli.base import console
from filekor.constants import (
    CONFIG_DB_KEY,
    CONFIG_FILENAME,
    CONFIG_ROOT_KEY,
    FILEKOR_DIR,
)
from filekor.core.config import FilekorConfig


@click.group("db", invoke_without_command=True)
@click.pass_context
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default=None,
    help="Custom config.yaml file path",
)
def db(ctx: click.Context, config: str) -> None:
    """Database commands. Run without subcommand for summary."""
    filekor_config = FilekorConfig.load(config) if config else FilekorConfig.load()
    ctx.ensure_object(dict)
    ctx.obj["config"] = filekor_config

    if ctx.invoked_subcommand is None:
        _show_summary(filekor_config)


def _show_summary(config: FilekorConfig) -> None:
    """Show database summary info."""
    db_path = config.db_path

    table = Table(title="Database")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Path", str(db_path))
    table.add_row(
        "Configured",
        "[green]yes[/green]" if _has_db_config() else "[yellow]no (default)[/yellow]",
    )

    if not db_path.exists():
        table.add_row("Exists", "[yellow]no[/yellow]")
        console.print(table)
        sys.exit(0)

    table.add_row("Exists", "[green]yes[/green]")
    size = db_path.stat().st_size
    table.add_row("Size", _format_size(size))

    try:
        conn = _connect(db_path)

        schema_version = _query_scalar(
            conn, "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        table.add_row("Schema", f"v{schema_version}" if schema_version else "unknown")

        file_count = _query_scalar(conn, "SELECT COUNT(*) FROM files") or 0
        label_count = _query_scalar(conn, "SELECT COUNT(*) FROM labels") or 0
        table.add_row("Files", str(file_count))
        table.add_row("Labels", str(label_count))

        conn.close()
    except Exception as e:
        table.add_row("Error", f"[red]{e}[/red]")

    console.print(table)


@db.command("files")
@click.pass_context
def db_files(ctx: click.Context) -> None:
    """List all indexed files."""
    config: FilekorConfig = ctx.obj["config"]
    db_path = config.db_path

    if not db_path.exists():
        console.print("[red]Database does not exist.[/red]")
        sys.exit(1)

    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            "SELECT hash_sha256, extension, file_path FROM files ORDER BY file_path"
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        console.print("[yellow]No files indexed.[/yellow]")
        sys.exit(0)

    table = Table(title="Files")
    table.add_column("SHA256", style="cyan", no_wrap=True)
    table.add_column("EXT", style="white")
    table.add_column("PATH", style="white")

    for row in rows:
        sha = row["hash_sha256"]
        short_sha = sha[:16] + "..." if sha else "—"
        ext = row["extension"] or "—"
        path = row["file_path"] or "—"
        table.add_row(short_sha, ext, path)

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(rows)} files")


@db.command("labels")
@click.pass_context
def db_labels(ctx: click.Context) -> None:
    """List all labels with file counts."""
    config: FilekorConfig = ctx.obj["config"]
    db_path = config.db_path

    if not db_path.exists():
        console.print("[red]Database does not exist.[/red]")
        sys.exit(1)

    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT l.label, COUNT(DISTINCT l.file_id) as file_count
            FROM labels l
            GROUP BY l.label
            ORDER BY file_count DESC, l.label ASC
            """
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        console.print("[yellow]No labels indexed.[/yellow]")
        sys.exit(0)

    table = Table(title="Labels")
    table.add_column("LABEL", style="cyan")
    table.add_column("FILES", style="white", justify="right")

    for row in rows:
        table.add_row(row["label"], str(row["file_count"]))

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(rows)} unique labels")


@db.command("search")
@click.argument("query")
@click.pass_context
def db_search(ctx: click.Context, query: str) -> None:
    """Search files by full-text query (FTS5)."""
    config: FilekorConfig = ctx.obj["config"]
    db_path = config.db_path

    if not db_path.exists():
        console.print("[red]Database does not exist.[/red]")
        sys.exit(1)

    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT f.hash_sha256, f.name, f.file_path
            FROM files_fts
            JOIN files f ON f.id = files_fts.rowid
            WHERE files_fts MATCH ?
            ORDER BY rank
            LIMIT 50
            """,
            (query,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        console.print(f"[yellow]No results for '{query}'.[/yellow]")
        sys.exit(0)

    table = Table(title=f"Search: {query}")
    table.add_column("SHA256", style="cyan", no_wrap=True)
    table.add_column("NAME", style="white")
    table.add_column("PATH", style="white")

    for row in rows:
        sha = row["hash_sha256"]
        short_sha = sha[:16] + "..." if sha else "—"
        table.add_row(short_sha, row["name"], row["file_path"])

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(rows)} results")


@db.command("show")
@click.argument("sha256_prefix")
@click.pass_context
def db_show(ctx: click.Context, sha256_prefix: str) -> None:
    """Show details for a file by SHA256 hash (prefix ok)."""
    config: FilekorConfig = ctx.obj["config"]
    db_path = config.db_path

    if not db_path.exists():
        console.print("[red]Database does not exist.[/red]")
        sys.exit(1)

    conn = _connect(db_path)
    try:
        # Match by prefix
        cursor = conn.execute(
            "SELECT * FROM files WHERE hash_sha256 LIKE ?",
            (sha256_prefix + "%",),
        )
        row = cursor.fetchone()

        if not row:
            console.print(
                f"[red]No file found with hash prefix '{sha256_prefix}'.[/red]"
            )
            sys.exit(1)

        file_id = row["id"]

        # Get labels
        cursor = conn.execute(
            "SELECT label FROM labels WHERE file_id = ? ORDER BY label",
            (file_id,),
        )
        labels = [r["label"] for r in cursor.fetchall()]
    finally:
        conn.close()

    table = Table(title=f"File: {row['name']}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Name", row["name"])
    table.add_row("Path", row["file_path"])
    table.add_row("Extension", row["extension"] or "—")
    table.add_row("Size", _format_size(row["size_bytes"] or 0))
    table.add_row("SHA256", row["hash_sha256"] or "—")
    table.add_row("Modified", row["modified_at"] or "—")
    table.add_row("Kor Path", row["kor_path"] or "—")

    if labels:
        table.add_row("Labels", ", ".join(labels))
    else:
        table.add_row("Labels", "—")

    keys = row.keys()
    summary_short = row["summary_short"] if "summary_short" in keys else None
    summary_long = row["summary_long"] if "summary_long" in keys else None

    table.add_row("Summary (short)", summary_short or "—")
    table.add_row("Summary (long)", summary_long or "—")

    console.print(table)


def _connect(db_path: Path) -> sqlite3.Connection:
    """Connect to SQLite database with Row factory."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _query_scalar(conn: sqlite3.Connection, sql: str) -> Optional[int]:
    """Execute a scalar query and return first value."""
    try:
        cursor = conn.execute(sql)
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _has_db_config() -> bool:
    """Check if config.yaml has a db.path setting."""
    import yaml

    search_paths = [
        Path(CONFIG_FILENAME),
        Path(FILEKOR_DIR) / CONFIG_FILENAME,
        Path.home() / FILEKOR_DIR / CONFIG_FILENAME,
    ]

    for search_path in search_paths:
        if search_path.exists():
            try:
                data = yaml.safe_load(search_path.read_text(encoding="utf-8"))
                if data and CONFIG_ROOT_KEY in data:
                    db = data[CONFIG_ROOT_KEY].get(CONFIG_DB_KEY, {})
                    if "path" in db:
                        return True
            except Exception:
                pass

    return False


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
