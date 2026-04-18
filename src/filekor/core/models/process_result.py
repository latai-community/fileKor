"""Process result models for core module."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

# Supported file extensions for processing
SUPPORTED_EXTENSIONS = {"pdf", "txt", "md"}


@dataclass
class ProcessResult:
    """Result of processing a single file.

    Attributes:
        file_path: Path to the original file.
        success: Whether the processing was successful.
        output_path: Path to the output .kor file (optional).
        error: Error message if processing failed (optional).
        labels: List of labels extracted (optional).
    """

    file_path: Path
    success: bool
    output_path: Optional[Path] = None
    error: Optional[str] = None
    labels: Optional[List[str]] = None