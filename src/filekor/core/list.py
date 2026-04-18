"""List module for querying .kor files."""

from pathlib import Path
from typing import List, Dict, Any, Optional


def list_kor_files(
    directory: str,
    extension: Optional[str] = None,
    include_merged: bool = False,
    recursive: bool = True,
) -> List[Dict[str, Any]]:
    """List all .kor files in a directory.

    Args:
        directory: Path to directory containing .kor files.
        extension: Filter by file extension (e.g., pdf, md, txt).
        include_merged: Include individual entries from merged.kor files.
        recursive: Search subdirectories.

    Returns:
        List of dicts with keys: sha256, name, path, type

    Example:
        >>> from filekor.list import list_kor_files
        >>> results = list_kor_files("./docs", extension="pdf")
    """
    from filekor.core.status import get_directory_status
    from filekor.merge import load_merged_kor

    dir_path = Path(directory)
    results = []

    if include_merged:
        filekor_dir = dir_path / ".filekor"
        if filekor_dir.is_dir():
            merged_files = list(filekor_dir.glob("merged*.kor"))
            for merged_file in merged_files:
                try:
                    sidecar_list = load_merged_kor(str(merged_file))
                    for sc in sidecar_list:
                        results.append({
                            "sha256": sc.file.hash_sha256,
                            "name": sc.file.name,
                            "path": str(merged_file),
                            "type": "merged",
                        })
                except Exception:
                    pass

    status = get_directory_status(str(dir_path), recursive=recursive)

    for file_status in status.file_statuses:
        if not file_status.exists or not file_status.sidecar:
            continue

        file_ext = file_status.sidecar.file.extension
        if extension and file_ext.lower() != extension.lower():
            continue

        results.append({
            "sha256": file_status.sidecar.file.hash_sha256,
            "name": file_status.sidecar.file.name,
            "path": str(file_status.kor_path),
            "type": "individual",
        })

    return results


def list_as_text(
    directory: str,
    extension: Optional[str] = None,
    include_merged: bool = False,
    recursive: bool = True,
) -> str:
    """List .kor files as formatted text.

    Returns:
        Formatted string with one entry per line.
    """
    results = list_kor_files(directory, extension, include_merged, recursive)

    lines = []
    for r in results:
        short_sha = r["sha256"][:16] + "..."
        type_marker = f"({r['type']})" if r["type"] == "merged" else ""
        lines.append(f"{short_sha} {r['name']} {type_marker}")

    return "\n".join(lines)


def list_as_json(
    directory: str,
    extension: Optional[str] = None,
    include_merged: bool = False,
    recursive: bool = True,
) -> str:
    """List .kor files as JSON.

    Returns:
        JSON string.
    """
    import json
    results = list_kor_files(directory, extension, include_merged, recursive)
    return json.dumps(results, indent=2)


def list_as_csv(
    directory: str,
    extension: Optional[str] = None,
    include_merged: bool = False,
    recursive: bool = True,
) -> str:
    """List .kor files as CSV.

    Returns:
        CSV string with header.
    """
    results = list_kor_files(directory, extension, include_merged, recursive)

    lines = ["sha256,name,path,type"]
    for r in results:
        lines.append(f"{r['sha256']},{r['name']},{r['path']},{r['type']}")

    return "\n".join(lines)


def list_sha_only(
    directory: str,
    extension: Optional[str] = None,
    include_merged: bool = False,
    recursive: bool = True,
) -> str:
    """List only SHA256 hashes, one per line.

    Returns:
        String with one SHA256 per line.
    """
    results = list_kor_files(directory, extension, include_merged, recursive)
    return "\n".join(r["sha256"] for r in results)