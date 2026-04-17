"""PyExifTool adapter implementation."""

import os
import subprocess
from datetime import datetime
from typing import Optional

from filekor.adapters.base import MetadataAdapter
from filekor.sidecar import FileMetadata


class PyExifToolAdapter(MetadataAdapter):
    """Adapter using exiftool for metadata extraction.

    Requires exiftool to be installed on the system.
    """

    PDF_TAGS = [
        "Author",
        "Creator",
        "CreateDate",
        "ModifyDate",
        "Producer",
        "Title",
        "Subject",
        "Keywords",
    ]

    def is_available(self) -> bool:
        """Check if exiftool is available on the system.

        Returns:
            True if exiftool is installed and accessible, False otherwise.
        """
        try:
            result = subprocess.run(
                ["exiftool", "-ver"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _extract_tag(self, path: str, tag: str) -> Optional[str]:
        """Extract a single tag from a file.

        Args:
            path: Path to the file.
            tag: Tag name to extract.

        Returns:
            Tag value or None if not found/timeout.
        """
        try:
            result = subprocess.run(
                ["exiftool", f"-{tag}", "-s", "-s", "-s", path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except subprocess.TimeoutExpired:
            pass
        return None

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse exiftool datetime format to datetime object.

        Args:
            date_str: Date string from exiftool (format: YYYY:MM:DD HH:MM:SS±HH:MM)

        Returns:
            Parsed datetime or None if parsing fails.
        """
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace(":", "-", 2))
        except ValueError:
            return None

    def extract_metadata(self, path: str) -> Optional[FileMetadata]:
        """Extract metadata from a PDF file using exiftool.

        Args:
            path: Path to the file to extract metadata from.

        Returns:
            FileMetadata object with extracted fields, or None if extraction failed.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        author = self._extract_tag(path, "Author") or self._extract_tag(path, "Creator")
        created_str = self._extract_tag(path, "CreateDate")
        created = self._parse_datetime(created_str)

        return FileMetadata(
            author=author,
            created=created,
            pages=None,
        )
