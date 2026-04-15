"""Sidecar model for metadata storage."""

import hashlib
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel

from filekor.labels import suggest_labels, LabelsConfig, LLMConfig


class FileInfo(BaseModel):
    """File information fields."""

    path: str
    name: str
    extension: str
    size_bytes: int
    modified_at: datetime
    hash_sha256: str


class FileMetadata(BaseModel):
    """Optional file metadata."""

    author: Optional[str] = None
    created: Optional[datetime] = None
    pages: Optional[int] = None


class Content(BaseModel):
    """Content information with language, word count, and page count."""

    language: Optional[str] = None
    word_count: Optional[int] = None
    page_count: Optional[int] = None


class FileContent(BaseModel):
    """Optional content information (legacy compatibility)."""

    language: Optional[str] = None
    word_count: Optional[int] = None


class FileSummary(BaseModel):
    """Optional summary information."""

    short: Optional[str] = None
    long: Optional[str] = None


class FileLabels(BaseModel):
    """Optional labels with source information.

    Attributes:
        suggested: List of suggested label names.
        source: Source of labels (always "llm").
    """

    suggested: List[str] = []
    source: Literal["llm"] = "llm"


class Sidecar(BaseModel):
    """Sidecar model for storing extracted metadata.

    Attributes:
        version: Schema version (default "1.0").
        file: File information (path, name, extension, size_bytes, modified_at, hash_sha256).
        metadata: Optional extracted metadata (author, created, pages).
        content: Optional content info (language, word_count).
        summary: Optional summary (short, long).
        labels: Optional labels (suggested, source).
        parser_status: Parser status (OK, DEGRADED, BROKEN).
        generated_at: ISO timestamp when metadata was generated.
    """

    version: str = "1.0"
    file: FileInfo
    metadata: Optional[FileMetadata] = None
    content: Optional[Content] = None
    summary: Optional[FileSummary] = None
    labels: Optional[FileLabels] = None
    parser_status: str = "OK"
    generated_at: datetime

    def to_json(self) -> str:
        """Serialize sidecar to JSON string.

        Returns:
            JSON string representation of the sidecar.
        """
        return self.model_dump_json(indent=2)

    def to_yaml(self) -> str:
        """Serialize sidecar to YAML string.

        Returns:
            YAML string representation of the sidecar.
        """
        # Define field order to match spec
        field_order = [
            "version",
            "file",
            "metadata",
            "content",
            "summary",
            "labels",
            "parser_status",
            "generated_at",
        ]

        file_order = [
            "path",
            "name",
            "extension",
            "size_bytes",
            "modified_at",
            "hash_sha256",
        ]
        content_order = ["language", "word_count", "page_count"]

        data = self.model_dump(mode="json")

        def ordered_dict(data_dict, key_order):
            """Convert dict to ordered dict for consistent YAML output."""
            result = {}
            for key in key_order:
                if key in data_dict:
                    result[key] = data_dict[key]
            # Add any remaining keys not in order
            for key in data_dict:
                if key not in result:
                    result[key] = data_dict[key]
            return result

        ordered_data = {}
        for key in field_order:
            if key in data:
                if key == "file" and data["file"]:
                    ordered_data[key] = ordered_dict(data["file"], file_order)
                elif key == "content" and data["content"]:
                    ordered_data[key] = ordered_dict(data["content"], content_order)
                else:
                    ordered_data[key] = data[key]

        return yaml.dump(
            ordered_data, indent=2, default_flow_style=False, sort_keys=False
        )

    @classmethod
    def create(
        cls,
        file_path: str,
        metadata: Optional[Dict] = None,
        content: Optional[Content] = None,
        labels_config: Optional[LabelsConfig] = None,
        text_content: Optional[str] = None,
    ) -> "Sidecar":
        """Create a new Sidecar instance.

        Args:
            file_path: Path to the source file.
            metadata: Extracted metadata dictionary.
            content: Optional Content object with text extraction info.
            labels_config: Optional LabelsConfig for auto-labeling.
            text_content: Optional extracted text content for LLM-based labeling.

        Returns:
            A new Sidecar instance with computed file info and current timestamp.

        Raises:
            RuntimeError: If LLM is not configured and labels_config is provided.
        """
        path = Path(file_path)

        file_info = FileInfo(
            path=str(path),
            name=path.name,
            extension=path.suffix.lstrip("."),
            size_bytes=path.stat().st_size,
            modified_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc),
            hash_sha256=cls._compute_hash(path),
        )

        extracted_meta = None
        if metadata:
            author = metadata.get("author")
            created = metadata.get("created")
            pages = metadata.get("pages")

            if author or created or pages:
                extracted_meta = FileMetadata(
                    author=author,
                    created=created,
                    pages=pages,
                )

        # Auto-populate labels if config is provided
        labels = None
        if labels_config and text_content:
            # Use LLM only for label extraction
            suggested_labels = suggest_labels(
                content=text_content,
                config=labels_config,
            )
            if suggested_labels:
                labels = FileLabels(
                    suggested=suggested_labels,
                    source="llm",
                )

        return cls(
            file=file_info,
            metadata=extracted_meta,
            content=content,
            labels=labels,
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _compute_hash(file_path: Path) -> str:
        """Compute SHA256 hash of file.

        Args:
            file_path: Path to the file.

        Returns:
            SHA256 hash as hexadecimal string.
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
