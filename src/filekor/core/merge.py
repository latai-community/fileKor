"""Merge module for combining .kor files."""

from pathlib import Path
from typing import List, Optional

from filekor.constants import FILEKOR_DIR, KOR_EXTENSION, MERGED_KOR_FILENAME
from filekor.sidecar import Sidecar


def merge_kor_files(
    directory: str,
    output_path: Optional[str] = None,
    delete_sources: bool = True,
) -> List[Sidecar]:
    """Merge multiple .kor files into a single aggregated file.

    Args:
        directory: Path containing .kor files to merge.
        output_path: Optional output path for merged .kor file.
        delete_sources: Whether to delete original .kor files after merge.

    Returns:
        List of Sidecar objects that were merged.

    Example:
        >>> from filekor.merge import merge_kor_files
        >>> sidecars = merge_kor_files("./docs", delete_sources=False)
    """
    dir_path = Path(directory)
    filekor_dir = dir_path / FILEKOR_DIR

    if not filekor_dir.is_dir():
        raise FileNotFoundError(f"{FILEKOR_DIR} directory not found: {filekor_dir}")

    kor_files = list(filekor_dir.glob(f"*{KOR_EXTENSION}"))
    if not kor_files:
        return []

    merged_sidecars = []
    for kor_file in kor_files:
        try:
            sidecar = Sidecar.load(str(kor_file))
            merged_sidecars.append(sidecar)
        except Exception:
            continue

    if not merged_sidecars:
        return []

    merged_yaml = ""
    for sidecar in merged_sidecars:
        merged_yaml += "---\n" + sidecar.to_yaml() + "\n"

    out_path = Path(output_path) if output_path else filekor_dir / MERGED_KOR_FILENAME
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(merged_yaml)

    if delete_sources:
        for kor_file in kor_files:
            try:
                kor_file.unlink()
            except Exception:
                continue

    return merged_sidecars


def load_merged_kor(path: str) -> List[Sidecar]:
    """Load a merged .kor file (list format).

    Args:
        path: Path to the merged .kor file.

    Returns:
        List of Sidecar objects.

    Example:
        >>> from filekor.merge import load_merged_kor
        >>> sidecars = load_merged_kor("./docs/.filekor/merged.kor")
    """
    kor_path = Path(path)
    if not kor_path.exists():
        raise FileNotFoundError(f"Merged {KOR_EXTENSION} file not found: {path}")

    import yaml

    content = kor_path.read_text()
    sidecars = []
    for data in yaml.safe_load_all(content):
        if data:
            sidecar = Sidecar.model_validate(data)
            sidecars.append(sidecar)

    return sidecars
