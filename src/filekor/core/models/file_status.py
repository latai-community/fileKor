"""File status models for core module."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Import delayed to avoid circular imports
# from filekor.sidecar import Sidecar  # Added by consumer


@dataclass
class FileStatus:
    """Status information for a file.

    Attributes:
        file_path: Path to the source file.
        kor_path: Path to the .kor sidecar file.
        exists: Whether the .kor file exists in filesystem.
        in_db: Whether the file is indexed in database.
        sidecar: Loaded Sidecar instance (optional).
        error: Error message if loading failed (optional).
    """

    file_path: Path
    kor_path: Path
    exists: bool
    in_db: bool = False
    sidecar: Optional["Sidecar"] = None
    error: Optional[str] = None


@dataclass
class DirectoryStatus:
    """Status information for a directory.

    Attributes:
        directory: Path to the directory.
        total_files: Total number of supported files found.
        kor_files: Total number of .kor files found in filesystem.
        files_without_kor: List of files that don't have .kor files.
        file_statuses: List of FileStatus for each file.
        indexed_in_db: Total number of files indexed in database.
    """

    directory: Path
    total_files: int
    kor_files: int
    files_without_kor: list[Path]
    file_statuses: list[FileStatus]
    indexed_in_db: int = 0