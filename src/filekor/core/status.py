"""Status module for core - view .kor file information."""

from pathlib import Path
from typing import Dict, Optional

from filekor.constants import FILEKOR_DIR, KOR_EXTENSION
from filekor.core.models.file_status import FileStatus, DirectoryStatus


def get_file_status(file_path: str) -> FileStatus:
    """Get status for a single file, prioritizing database.

    Args:
        file_path: Path to the file.

    Returns:
        FileStatus instance with in_db flag.
    """
    from filekor.sidecar import Sidecar
    import yaml

    path = Path(file_path)

    # Check expected .kor path for this file (individual)
    ext = path.suffix.lstrip(".").lower()
    filekor_dir = path.parent / FILEKOR_DIR
    kor_path = filekor_dir / f"{path.stem}.{ext}{KOR_EXTENSION}"

    if not path.exists():
        return FileStatus(
            file_path=path,
            kor_path=kor_path,
            exists=False,
            in_db=False,
            error="File not found",
        )

    # 1. Try to get from database first
    db_file = _get_file_from_db(file_path)
    if db_file:
        kor_path_db = db_file.get("kor_path", "")

        # Check if kor_path from DB exists in filesystem
        exists_in_fs = Path(kor_path_db).exists() if kor_path_db else False

        # If not exists as individual .kor, check in merged.kor
        if not exists_in_fs and kor_path_db:
            # Check if kor_path points to merged.kor or if merged.kor exists nearby
            kor_path_obj = Path(kor_path_db)
            merged_kor_path = kor_path_obj.parent / "merged.kor"

            # Try to find in merged.kor
            if merged_kor_path.exists():
                try:
                    content = merged_kor_path.read_text(encoding="utf-8")
                    # Search for this file in merged.kor by file_path
                    abs_path = str(path.resolve())
                    for doc in yaml.safe_load_all(content):
                        if doc and doc.get("file", {}).get("path") == abs_path:
                            exists_in_fs = True
                            break
                except Exception:
                    pass

        # Build Sidecar-like info from DB record
        sidecar = _build_sidecar_from_db(db_file)
        return FileStatus(
            file_path=path,
            kor_path=Path(kor_path_db) if kor_path_db else kor_path,
            exists=exists_in_fs,
            in_db=True,
            sidecar=sidecar,
        )

    # 2. Fallback: check filesystem for .kor file
    if kor_path.exists():
        try:
            sidecar = Sidecar.load(str(kor_path))
            return FileStatus(
                file_path=path,
                kor_path=kor_path,
                exists=True,
                in_db=False,
                sidecar=sidecar,
            )
        except Exception as e:
            return FileStatus(
                file_path=path,
                kor_path=kor_path,
                exists=True,
                in_db=False,
                error=str(e),
            )

    # 3. Neither in DB nor in filesystem
    return FileStatus(
        file_path=path,
        kor_path=kor_path,
        exists=False,
        in_db=False,
    )
    if kor_path.exists():
        try:
            sidecar = Sidecar.load(str(kor_path))
            return FileStatus(
                file_path=path,
                kor_path=kor_path,
                exists=True,
                in_db=False,
                sidecar=sidecar,
            )
        except Exception as e:
            return FileStatus(
                file_path=path,
                kor_path=kor_path,
                exists=True,
                in_db=False,
                error=str(e),
            )

    # 3. Neither in DB nor in filesystem
    return FileStatus(
        file_path=path,
        kor_path=kor_path,
        exists=False,
        in_db=False,
    )


def _get_file_from_db(file_path: str) -> Optional[Dict]:
    """Get file info from database by path.

    Args:
        file_path: Path to the source file.

    Returns:
        Dict with file info from DB, or None if not found.
    """
    try:
        import sqlite3
        from pathlib import Path

        # Get DB path from config
        from filekor.core.config import FilekorConfig

        config = FilekorConfig.load()
        db_path = config.db_path

        # Create direct connection without row_factory to avoid timestamp issues
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = None  # Disable automatic row conversion

        try:
            # Use absolute path
            abs_path = str(Path(file_path).resolve())

            cursor = conn.execute(
                "SELECT id, kor_path, file_path, name, extension, size_bytes, "
                "hash_sha256, summary_short, summary_long FROM files WHERE file_path = ?",
                (abs_path,)
            )
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None

            result = {
                "id": row[0],
                "kor_path": row[1],
                "file_path": row[2],
                "name": row[3],
                "extension": row[4],
                "size_bytes": row[5],
                "hash_sha256": row[6],
                "summary_short": row[7],
                "summary_long": row[8],
                "parser_status": "OK",
            }

            # Get labels
            labels_cursor = conn.execute(
                "SELECT label FROM labels WHERE file_id = ?", (result["id"],)
            )
            result["labels"] = [r[0] for r in labels_cursor.fetchall()]

            conn.close()
            return result
        except Exception:
            conn.close()
            raise
    except Exception:
        return None


def _build_sidecar_from_db(db_file: Dict) -> Optional["Sidecar"]:
    """Build a minimal Sidecar-like object from database record.

    This is used to provide labels and other metadata
    without needing to load the actual .kor file.

    Args:
        db_file: Dict with file info from DB.

    Returns:
        Minimal object with file info from DB.
    """
    from datetime import datetime
    from filekor.sidecar import Content, FileInfo, FileLabels, FileSummary, Sidecar

    file_data = db_file

    file_info = FileInfo(
        path=file_data.get("file_path", ""),
        name=file_data.get("name", ""),
        extension=file_data.get("extension", ""),
        size_bytes=file_data.get("size_bytes", 0),
        modified_at=file_data.get("modified_at", datetime.now()),
        hash_sha256=file_data.get("hash_sha256", ""),
    )

    # Build labels from DB (stored separately)
    labels_list = file_data.get("labels", [])
    file_labels = None
    if labels_list:
        file_labels = FileLabels(suggested=labels_list, source="llm")

    # Build summary from DB
    summary = None
    if file_data.get("summary_short") or file_data.get("summary_long"):
        summary = FileSummary(
            short=file_data.get("summary_short"),
            long=file_data.get("summary_long"),
        )

    content = Content(
        language=None,
        word_count=None,
        page_count=None,
    )

    return Sidecar(
        file=file_info,
        metadata=None,
        content=content,
        summary=summary,
        labels=file_labels,
        parser_status=file_data.get("parser_status", "OK"),
        generated_at=file_data.get("created_at", datetime.now()),
    )


def get_directory_status(
    directory: str, recursive: bool = True, max_depth: int = -1
) -> DirectoryStatus:
    """Get status for all files in a directory.

    Args:
        directory: Path to the directory.
        recursive: Whether to check subdirectories.
        max_depth: Maximum depth to search (-1 for unlimited).

    Returns:
        DirectoryStatus instance with indexed_in_db count.
    """
    from filekor.core.processor import SUPPORTED_EXTENSIONS

    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    def get_depth(path: Path) -> int:
        """Calculate depth relative to dir_path."""
        try:
            return len(path.relative_to(dir_path).parts)
        except ValueError:
            return 0

    # Find all supported files
    pattern = "**/*" if recursive else "*"
    supported_files = []
    for ext in SUPPORTED_EXTENSIONS:
        files = list(dir_path.glob(f"{pattern}.{ext}"))
        if max_depth > 0:
            files = [f for f in files if get_depth(f) <= max_depth]
        supported_files.extend(files)

    # Find all .kor files (in .filekor/ subdirectory)
    kor_files = []
    filekor_dirs = [dir_path / FILEKOR_DIR]
    if recursive:
        if max_depth > 0:
            filekor_dirs.extend(
                [
                    d
                    for d in dir_path.glob(f"**/{FILEKOR_DIR}")
                    if get_depth(d) <= max_depth
                ]
            )
        else:
            filekor_dirs.extend(dir_path.glob(f"**/{FILEKOR_DIR}"))

    for fk_dir in filekor_dirs:
        if fk_dir.exists() and fk_dir.is_dir():
            kor_files.extend(fk_dir.glob(f"*{KOR_EXTENSION}"))

    # Get status for each file (DB-first logic)
    file_statuses = []
    indexed_count = 0
    for file_path in supported_files:
        status = get_file_status(str(file_path))
        file_statuses.append(status)
        if status.in_db:
            indexed_count += 1

    # Files without .kor (neither in DB nor in filesystem)
    files_without_kor = [s.file_path for s in file_statuses if not s.exists and not s.in_db]

    return DirectoryStatus(
        directory=dir_path,
        total_files=len(supported_files),
        kor_files=len(kor_files),
        indexed_in_db=indexed_count,
        files_without_kor=files_without_kor,
        file_statuses=file_statuses,
    )


def file_status_to_dict(s: FileStatus) -> Dict:
    """Convert FileStatus to dictionary for programmatic use.

    Args:
        s: FileStatus instance.

    Returns:
        Dict with keys: file, kor_exists, and (if exists)
        name, size_bytes, labels, parser_status.
    """
    if not s.exists:
        return {
            "file": str(s.file_path),
            "kor_exists": False,
        }

    if s.error:
        return {
            "file": str(s.file_path),
            "kor_exists": True,
            "error": s.error,
        }

    sidecar = s.sidecar
    return {
        "file": str(s.file_path),
        "kor_exists": True,
        "name": sidecar.file.name,
        "size_bytes": sidecar.file.size_bytes,
        "labels": sidecar.labels.suggested if sidecar.labels else [],
        "parser_status": sidecar.parser_status,
    }
