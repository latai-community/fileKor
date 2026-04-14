"""Tests for metadata adapters."""
import pytest
from unittest.mock import Mock, patch

from filekor.adapters.base import MetadataAdapter
from filekor.adapters.exiftool import PyExifToolAdapter
from filekor.sidecar import Sidecar


class TestMetadataAdapter:
    """Test MetadataAdapter interface."""

    def test_adapter_is_abstract(self):
        """Verify MetadataAdapter is abstract."""

        class MockAdapter(MetadataAdapter):
            def is_available(self) -> bool:
                return True

            def extract_metadata(self, path: str) -> dict:
                return {}

        adapter = MockAdapter()
        assert adapter.is_available() is True
        assert adapter.extract_metadata("test.pdf") == {}


class TestPyExifToolAdapter:
    """Test PyExifToolAdapter."""

    def test_adapter_instantiates(self):
        """Verify adapter can be instantiated."""
        adapter = PyExifToolAdapter()
        assert adapter is not None

    @patch("subprocess.run")
    def test_is_available_true_when_exiftool_found(self, mock_run):
        """Test is_available returns True when exiftool is found."""
        mock_run.return_value = Mock(returncode=0, stdout="12.0", stderr="")
        adapter = PyExifToolAdapter()
        assert adapter.is_available() is True

    @patch("subprocess.run")
    def test_is_available_false_when_exiftool_not_found(self, mock_run):
        """Test is_available returns False when exiftool not found."""
        mock_run.side_effect = FileNotFoundError()
        adapter = PyExifToolAdapter()
        assert adapter.is_available() is False


class TestSidecar:
    """Test Sidecar model."""

    def test_sidecar_creation(self):
        """Verify Sidecar can be created."""
        sidecar = Sidecar(
            file="test.pdf",
            extracted_at="2026-04-14T12:00:00Z",
            metadata={"Title": "Test", "Author": "Test Author"},
        )
        assert sidecar.file == "test.pdf"
        assert sidecar.metadata["Title"] == "Test"

    def test_to_json(self):
        """Verify to_json produces valid JSON."""
        sidecar = Sidecar(
            file="test.pdf",
            extracted_at="2026-04-14T12:00:00Z",
            metadata={"Title": "Test"},
        )
        json_str = sidecar.to_json()
        assert '"file": "test.pdf"' in json_str
        assert '"metadata"' in json_str

    def test_create_factory(self):
        """Verify create factory works."""
        sidecar = Sidecar.create("test.pdf", {"Title": "Test"})
        assert sidecar.file == "test.pdf"
        assert sidecar.metadata == {"Title": "Test"}
        assert sidecar.extracted_at is not None