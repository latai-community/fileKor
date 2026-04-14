"""Sidecar model for metadata storage."""
from datetime import datetime, timezone
from typing import Dict, Optional

from pydantic import BaseModel


class Sidecar(BaseModel):
    """Sidecar model for storing extracted metadata.

    Attributes:
        file: Path to the source file.
        extracted_at: ISO timestamp when metadata was extracted.
        metadata: Dictionary of extracted metadata tags.
    """

    file: str
    extracted_at: datetime
    metadata: Dict[str, str]

    def to_json(self) -> str:
        """Serialize sidecar to JSON string.

        Returns:
            JSON string representation of the sidecar.
        """
        return self.model_dump_json(indent=2)

    @classmethod
    def create(cls, file_path: str, metadata: Dict[str, str]) -> "Sidecar":
        """Create a new Sidecar instance.

        Args:
            file_path: Path to the source file.
            metadata: Extracted metadata dictionary.

        Returns:
            A new Sidecar instance with current timestamp.
        """
        return cls(
            file=file_path,
            extracted_at=datetime.now(timezone.utc),
            metadata=metadata,
        )