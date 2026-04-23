"""Sidecar model for metadata storage."""

import hashlib
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel
from rich.console import Console


console = Console()


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
        metadata: Optional[FileMetadata] = None,
        content: Optional[Content] = None,
        verbose: bool = False,
    ) -> "Sidecar":
        """Create a new Sidecar instance (WITHOUT labels).

        Args:
            file_path: Path to the source file.
            metadata: Optional FileMetadata object with extracted metadata.
            content: Optional Content object with text extraction info.
            verbose: Show detailed output.

        Returns:
            A new Sidecar instance with computed file info and current timestamp.

        Note:
            Labels are NOT auto-generated. Use 'filekor labels' command to add labels.
        """

        path = Path(file_path).resolve()

        file_info = FileInfo(
            path=str(path),
            name=path.name,
            extension=path.suffix.lstrip("."),
            size_bytes=path.stat().st_size,
            modified_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc),
            hash_sha256=cls._compute_hash(path),
        )

        if metadata and content and content.page_count is not None:
            metadata.pages = content.page_count

        # No labels auto-generated - labels added via 'filekor labels' command
        if verbose:
            console.print(
                "[yellow]Labels:[/yellow] not generated (use 'filekor labels' to add)"
            )

        return cls(
            file=file_info,
            metadata=metadata,
            content=content,
            labels=None,
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

    @classmethod
    def from_dict(cls, data: dict) -> "Sidecar":
        """Reconstruct a Sidecar from a parsed dict.

        Args:
            data: Dictionary with sidecar data (as produced by yaml.safe_load).

        Returns:
            Reconstructed Sidecar instance.
        """
        file_data = data.get("file", {})
        metadata_data = data.get("metadata")
        content_data = data.get("content")
        labels_data = data.get("labels")
        summary_data = data.get("summary")

        # Normalize file path to absolute
        if "path" in file_data:
            file_data["path"] = str(Path(file_data["path"]).resolve())

        file_info = FileInfo(**file_data)

        extracted_meta = None
        if metadata_data:
            extracted_meta = FileMetadata(**metadata_data)

        content_obj = None
        if content_data:
            content_obj = Content(**content_data)

        labels_obj = None
        if labels_data:
            labels_obj = FileLabels(**labels_data)

        summary_obj = None
        if summary_data:
            summary_obj = FileSummary(**summary_data)

        return cls(
            version=data.get("version", "1.0"),
            file=file_info,
            metadata=extracted_meta,
            content=content_obj,
            summary=summary_obj,
            labels=labels_obj,
            parser_status=data.get("parser_status", "OK"),
            generated_at=data.get("generated_at"),
        )

    @classmethod
    def load(cls, path: str) -> "Sidecar":
        """Load a .kor sidecar file from disk.

        Args:
            path: Path to the .kor file.

        Returns:
            Loaded Sidecar instance.

        Raises:
            FileNotFoundError: If .kor file does not exist.
            ValueError: If .kor file is invalid YAML.
        """
        import yaml

        kor_path = Path(path)
        if not kor_path.exists():
            raise FileNotFoundError(f"Sidecar file not found: {path}")

        try:
            data = yaml.safe_load(kor_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid sidecar file: {e}")

        return cls.from_dict(data)

    def update_labels(self, labels: List[str]) -> None:
        """Update labels in this sidecar (in-place).

        Args:
            labels: New list of labels.
        """
        self.labels = FileLabels(
            suggested=labels,
            source="llm",
        )
