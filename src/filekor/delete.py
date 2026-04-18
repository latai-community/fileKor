"""Delete module for removing .kor files and database records."""

import hashlib
from pathlib import Path
from typing import List, Literal, Optional

from filekor.db import delete_file_by_hash as db_delete_by_hash


def calculate_sha256(path: str) -> str:
    """Calculate SHA256 for a file.

    Args:
        path: Path to the file.

    Returns:
        SHA256 hex digest.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def delete_by_sha(
    sha256: str,
    scope: Literal["all", "db", "file"] = "all",
    verbose: bool = False,
) -> int:
    """Delete by SHA256 hash.

    Args:
        sha256: The SHA256 hash of the file.
        scope: Delete scope - "all", "db", or "file".
        verbose: Show detailed output.

    Returns:
        Number of records/files deleted.
    """
    deleted_count = 0

    if scope in ("all", "db"):
        try:
            count = db_delete_by_hash(sha256)
            deleted_count += count
            if verbose:
                print(f"DB deleted: {count} record(s)")
        except Exception as e:
            if verbose:
                print(f"DB error: {e}")

    if scope in ("all", "file"):
        from filekor.status import get_directory_status

        try:
            status = get_directory_status(".", recursive=True)
            for file_status in status.file_statuses:
                if (
                    file_status.sidecar
                    and file_status.sidecar.file.hash_sha256 == sha256
                ):
                    try:
                        file_status.kor_path.unlink()
                        deleted_count += 1
                        if verbose:
                            print(f"File deleted: {file_status.kor_path}")
                    except Exception as e:
                        if verbose:
                            print(f"File error: {e}")
        except Exception as e:
            if verbose:
                print(f"Search error: {e}")

    return deleted_count


def delete_by_path(
    path: str,
    scope: Literal["all", "db", "file"] = "all",
    verbose: bool = False,
) -> int:
    """Delete by file path (calculates SHA internally).

    Args:
        path: Path to the file.
        scope: Delete scope - "all", "db", or "file".
        verbose: Show detailed output.

    Returns:
        Number of records/files deleted.
    """
    file_hash = calculate_sha256(path)
    return delete_by_sha(file_hash, scope, verbose)


def delete_by_input(
    input_path: str,
    scope: Literal["all", "db", "file"] = "all",
    verbose: bool = False,
) -> int:
    """Delete multiple hashes from input file.

    Args:
        input_path: Path to file with SHA256 hashes (one per line).
        scope: Delete scope - "all", "db", or "file".
        verbose: Show detailed output.

    Returns:
        Total number of records/files deleted.
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    hashes = []
    for line in input_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            hashes.append(line)

    deleted_count = 0
    for sha in hashes:
        deleted_count += delete_by_sha(sha, scope, verbose)

    return deleted_count
