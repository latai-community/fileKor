"""Delete module for removing .kor files and database records."""

from pathlib import Path
from typing import List, Literal, Optional, Tuple


def delete_by_sha(
    sha256: str,
    directory: str = ".",
    scope: Literal["all", "db", "file"] = "all",
    recursive: bool = True,
    max_depth: int = -1,
    verbose: bool = False,
) -> Tuple[int, int]:
    """Delete by SHA256 hash in a specific directory.

    Args:
        sha256: The SHA256 hash of the file.
        directory: Directory to search for .kor files.
        scope: Delete scope - "all", "db", or "file".
        recursive: Search subdirectories.
        max_depth: Maximum depth to search (-1 for unlimited).
        verbose: Show detailed output.

    Returns:
        Tuple of (deleted_db_count, deleted_files_count).
    """
    deleted_db = 0
    deleted_files = 0

    if scope in ("all", "db"):
        from filekor.db import delete_file_by_hash as db_delete_by_hash
        try:
            count = db_delete_by_hash(sha256)
            deleted_db = count
            if verbose:
                print(f"DB deleted: {count} record(s)")
        except Exception as e:
            if verbose:
                print(f"DB error: {e}")

    if scope in ("all", "file"):
        from filekor.core.status import get_directory_status

        try:
            status = get_directory_status(directory, recursive=recursive, max_depth=max_depth)
            for file_status in status.file_statuses:
                if (
                    file_status.sidecar
                    and file_status.sidecar.file.hash_sha256 == sha256
                ):
                    try:
                        file_status.kor_path.unlink()
                        deleted_files += 1
                        if verbose:
                            print(f"File deleted: {file_status.kor_path}")
                    except Exception as e:
                        if verbose:
                            print(f"File error: {e}")
        except Exception as e:
            if verbose:
                print(f"Search error: {e}")

    return deleted_db, deleted_files


def delete_by_path(
    path: str,
    directory: str = ".",
    scope: Literal["all", "db", "file"] = "all",
    recursive: bool = True,
    max_depth: int = -1,
    verbose: bool = False,
) -> Tuple[int, int]:
    """Delete by file path (calculates SHA internally).

    Args:
        path: Path to the file.
        directory: Directory to search for .kor files.
        scope: Delete scope - "all", "db", or "file".
        recursive: Search subdirectories.
        max_depth: Maximum depth to search.
        verbose: Show detailed output.

    Returns:
        Tuple of (deleted_db_count, deleted_files_count).
    """
    from filekor.core.hasher import calculate_sha256
    file_hash = calculate_sha256(path)
    return delete_by_sha(
        file_hash,
        directory=directory,
        scope=scope,
        recursive=recursive,
        max_depth=max_depth,
        verbose=verbose,
    )


def delete_by_input(
    input_path: str,
    directory: str = ".",
    scope: Literal["all", "db", "file"] = "all",
    recursive: bool = True,
    max_depth: int = -1,
    verbose: bool = False,
) -> Tuple[int, int]:
    """Delete multiple hashes from input file.

    Args:
        input_path: Path to file with SHA256 hashes (one per line).
        directory: Directory to search for .kor files.
        scope: Delete scope - "all", "db", or "file".
        recursive: Search subdirectories.
        max_depth: Maximum depth to search.
        verbose: Show detailed output.

    Returns:
        Tuple of (total_deleted_db, total_deleted_files).
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    hashes = []
    for line in input_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            hashes.append(line)

    total_db = 0
    total_files = 0
    for sha in hashes:
        db_count, files_count = delete_by_sha(
            sha,
            directory=directory,
            scope=scope,
            recursive=recursive,
            max_depth=max_depth,
            verbose=verbose,
        )
        total_db += db_count
        total_files += files_count

    return total_db, total_files


def get_deletion_preview(
    sha256: str,
    directory: str = ".",
    recursive: bool = True,
    max_depth: int = -1,
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Get preview of what would be deleted (dry-run).

    Args:
        sha256: The SHA256 hash of the file.
        directory: Directory to search.
        recursive: Search subdirectories.
        max_depth: Maximum depth to search.

    Returns:
        Tuple of (db_hashes_to_delete, files_to_delete)
        where files_to_delete is list of (name, path).
    """
    db_hashes = []
    files_to_delete = []

    from filekor.db import get_file_by_hash
    try:
        record = get_file_by_hash(sha256)
        if record:
            db_hashes.append(sha256)
    except Exception:
        pass

    from filekor.core.status import get_directory_status
    try:
        status = get_directory_status(directory, recursive=recursive, max_depth=max_depth)
        for file_status in status.file_statuses:
            if (
                file_status.sidecar
                and file_status.sidecar.file.hash_sha256 == sha256
            ):
                files_to_delete.append((
                    file_status.sidecar.file.name,
                    str(file_status.kor_path)
                ))
    except Exception:
        pass

    return db_hashes, files_to_delete