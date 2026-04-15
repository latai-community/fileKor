"""Status module for lib API - view .kor file information."""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from filekor.sidecar import Sidecar


@dataclass
class FileStatus:
    """Status information for a file."""

    file_path: Path
    kor_path: Path
    exists: bool
    sidecar: Optional[Sidecar] = None
    error: Optional[str] = None


@dataclass
class DirectoryStatus:
    """Status information for a directory."""

    directory: Path
    total_files: int
    kor_files: int
    files_without_kor: List[Path]
    file_statuses: List[FileStatus]


def get_file_status(file_path: str) -> FileStatus:
    """Get status for a single file.

    Args:
        file_path: Path to the file.

    Returns:
        FileStatus instance.
    """
    path = Path(file_path)
    kor_path = path.with_suffix(".kor")

    if not path.exists():
        return FileStatus(
            file_path=path,
            kor_path=kor_path,
            exists=False,
            error="File not found",
        )

    if not kor_path.exists():
        return FileStatus(
            file_path=path,
            kor_path=kor_path,
            exists=False,
        )

    try:
        sidecar = Sidecar.load(str(kor_path))
        return FileStatus(
            file_path=path,
            kor_path=kor_path,
            exists=True,
            sidecar=sidecar,
        )
    except Exception as e:
        return FileStatus(
            file_path=path,
            kor_path=kor_path,
            exists=True,
            error=str(e),
        )


def get_directory_status(directory: str, recursive: bool = True) -> DirectoryStatus:
    """Get status for all files in a directory.

    Args:
        directory: Path to the directory.
        recursive: Whether to check subdirectories.

    Returns:
        DirectoryStatus instance.
    """
    from filekor.processor import SUPPORTED_EXTENSIONS

    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    # Find all supported files
    pattern = "**/*" if recursive else "*"
    supported_files = []
    for ext in SUPPORTED_EXTENSIONS:
        supported_files.extend(dir_path.glob(f"{pattern}.{ext}"))

    # Find all .kor files
    kor_files = list(dir_path.glob("*.kor"))
    if recursive:
        kor_files.extend(dir_path.glob("**/*.kor"))

    # Get status for each file
    file_statuses = []
    for file_path in supported_files:
        kor_path = file_path.with_suffix(".kor")
        status = get_file_status(str(file_path))
        file_statuses.append(status)

    # Files without .kor
    files_without_kor = [s.file_path for s in file_statuses if not s.exists]

    return DirectoryStatus(
        directory=dir_path,
        total_files=len(supported_files),
        kor_files=len(kor_files),
        files_without_kor=files_without_kor,
        file_statuses=file_statuses,
    )


def summarize(s: FileStatus) -> Dict:
    """Create a summary dict from FileStatus.

    Args:
        s: FileStatus instance.

    Returns:
        Dictionary with summary info.
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
