"""Base utilities for CLI commands."""

from pathlib import Path
from typing import Optional

from rich.console import Console


console = Console()

# Text extraction try-imports (optional dependencies)
try:
    from pypdf import PdfReader

    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


def extract_text(path: str) -> tuple[str, int, int]:
    """Extract text content from a file.

    Args:
        path: Path to the file.

    Returns:
        Tuple of (text_content, word_count, page_count).

    Raises:
        ValueError: If file type is not supported.
    """
    file_path = Path(path)
    ext = file_path.suffix.lstrip(".").lower()

    if ext == "txt":
        content = file_path.read_text(encoding="utf-8")
        words = len(content.split())
        return content, words, 1

    elif ext == "md":
        content = file_path.read_text(encoding="utf-8")
        words = len(content.split())
        pages = max(1, len(content) // 3000)
        return content, words, pages

    elif ext == "pdf":
        if not HAS_PYPDF:
            raise ValueError("pypdf not installed. Install: pip install pypdf")
        reader = PdfReader(path)
        pages = len(reader.pages)
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text())
        content = "\n".join(text_parts)
        words = len(content.split())
        return content, words, pages

    else:
        raise ValueError(f"Unsupported file type: .{ext}")