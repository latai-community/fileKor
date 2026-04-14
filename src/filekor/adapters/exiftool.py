"""PyExifTool adapter implementation."""
import os
import subprocess
from typing import Dict

from filekor.adapters.base import MetadataAdapter


class PyExifToolAdapter(MetadataAdapter):
    """Adapter using exiftool for metadata extraction.

    Requires exiftool to be installed on the system.
    """

    PDF_TAGS = [
        "Title",
        "Author",
        "Subject",
        "Keywords",
        "Creator",
        "Producer",
        "CreateDate",
        "ModifyDate",
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

    def extract_metadata(self, path: str) -> Dict[str, str]:
        """Extract metadata from a file using exiftool.

        Args:
            path: Path to the file to extract metadata from.

        Returns:
            Dictionary of available metadata tags.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        metadata: Dict[str, str] = {}
        for tag in self.PDF_TAGS:
            try:
                result = subprocess.run(
                    ["exiftool", f"-{tag}", "-s", "-s", "-s", path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    metadata[tag] = result.stdout.strip()
            except subprocess.TimeoutExpired:
                # Skip tags that timeout
                continue

        return metadata