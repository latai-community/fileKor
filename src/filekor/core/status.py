"""Status module for core - view .kor file information."""

from pathlib import Path
from typing import Dict

from filekor.constants import FILEKOR_DIR, KOR_EXTENSION
from filekor.core.models.file_status import FileStatus, DirectoryStatus


def get_file_status(file_path: str) -> FileStatus:
    """Get status for a single file.

    Args:
        file_path: Path to the file.

    Returns:
        FileStatus instance.
    """
    from filekor.sidecar import Sidecar

    path = Path(file_path)

    # Check new location: .filekor/{filename}.{ext}.kor
    ext = path.suffix.lstrip(".").lower()
    filekor_dir = path.parent / FILEKOR_DIR
    kor_path = filekor_dir / f"{path.stem}.{ext}{KOR_EXTENSION}"

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


def get_directory_status(
    directory: str, recursive: bool = True, max_depth: int = -1
) -> DirectoryStatus:
    """Get status for all files in a directory.

    Args:
        directory: Path to the directory.
        recursive: Whether to check subdirectories.
        max_depth: Maximum depth to search (-1 for unlimited).

    Returns:
        DirectoryStatus instance.
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

    # Get status for each file
    file_statuses = []
    for file_path in supported_files:
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
