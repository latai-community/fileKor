"""Hash utilities for filekor."""

import hashlib
from pathlib import Path


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


def calculate_sha256_from_bytes(data: bytes) -> str:
    """Calculate SHA256 from bytes data.

    Args:
        data: Bytes data to hash.

    Returns:
        SHA256 hex digest.
    """
    return hashlib.sha256(data).hexdigest()


def calculate_sha256_from_file(file_path: Path) -> str:
    """Calculate SHA256 from a Path object.

    Args:
        file_path: Path object to the file.

    Returns:
        SHA256 hex digest.
    """
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()