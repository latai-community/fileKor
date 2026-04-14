"""Base adapter interface for metadata extraction."""
from abc import ABC, abstractmethod
from typing import Dict


class MetadataAdapter(ABC):
    """Abstract base class for metadata adapters.

    All adapters must implement is_available() and extract_metadata().
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the adapter is available.

        Returns:
            True if the underlying tool is available, False otherwise.
        """
        pass

    @abstractmethod
    def extract_metadata(self, path: str) -> Dict[str, str]:
        """Extract metadata from a file.

        Args:
            path: Path to the file to extract metadata from.

        Returns:
            Dictionary of metadata key-value pairs.
        """
        pass