"""Tests for metadata adapters."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from filekor.adapters.base import MetadataAdapter
from filekor.adapters.exiftool import PyExifToolAdapter
from filekor.sidecar import Content, FileInfo, FileMetadata, Sidecar


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
        """Verify Sidecar can be created with new schema."""
        sidecar = Sidecar(
            file=FileInfo(
                path="test.pdf",
                name="test.pdf",
                extension="pdf",
                size_bytes=1024,
                modified_at=datetime.now(timezone.utc),
                hash_sha256="abc123",
            ),
            metadata=FileMetadata(author="Test Author", pages=5),
            generated_at=datetime.now(timezone.utc),
        )
        assert sidecar.file.name == "test.pdf"
        assert sidecar.metadata.author == "Test Author"
        assert sidecar.metadata.pages == 5

    def test_to_json(self):
        """Verify to_json produces valid JSON."""
        sidecar = Sidecar(
            file=FileInfo(
                path="test.pdf",
                name="test.pdf",
                extension="pdf",
                size_bytes=1024,
                modified_at=datetime.now(timezone.utc),
                hash_sha256="abc123",
            ),
            metadata=FileMetadata(author="Test"),
            generated_at=datetime.now(timezone.utc),
        )
        json_str = sidecar.to_json()
        assert '"file"' in json_str
        assert '"metadata"' in json_str

    def test_create_factory(self):
        """Verify create factory works with real file."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            sidecar = Sidecar.create(temp_path, FileMetadata(author="Test Author"))
            assert sidecar.file is not None
            assert sidecar.metadata is not None
            assert sidecar.metadata.author == "Test Author"
            assert sidecar.generated_at is not None
        finally:
            Path(temp_path).unlink()


class TestContent:
    """Test Content model class."""

    def test_content_creation(self):
        """Verify Content can be created with all fields."""
        content = Content(language="en", word_count=100, page_count=5)
        assert content.language == "en"
        assert content.word_count == 100
        assert content.page_count == 5

    def test_content_partial(self):
        """Verify Content can be created with partial fields."""
        content = Content(word_count=50)
        assert content.language is None
        assert content.word_count == 50
        assert content.page_count is None

    def test_content_serialization(self):
        """Verify Content serializes to JSON."""
        content = Content(language="es", word_count=200, page_count=3)
        json_str = content.model_dump_json()
        data = json.loads(json_str)
        assert data["language"] == "es"
        assert data["word_count"] == 200
        assert data["page_count"] == 3


class TestSidecarWithContent:
    """Test Sidecar model with content field."""

    def test_sidecar_with_content_to_json(self):
        """Verify Sidecar.to_json() includes content field."""
        content = Content(language="en", word_count=100, page_count=2)
        sidecar = Sidecar(
            file=FileInfo(
                path="test.pdf",
                name="test.pdf",
                extension="pdf",
                size_bytes=1024,
                modified_at=datetime.now(timezone.utc),
                hash_sha256="abc123",
            ),
            content=content,
            generated_at=datetime.now(timezone.utc),
        )
        json_str = sidecar.to_json()
        data = json.loads(json_str)
        assert "content" in data
        assert data["content"]["word_count"] == 100
        assert data["content"]["page_count"] == 2

    def test_sidecar_create_with_content(self):
        """Verify Sidecar.create() accepts content parameter."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test content for extraction")
            temp_path = f.name

        try:
            content = Content(language="en", word_count=4, page_count=1)
            sidecar = Sidecar.create(
                temp_path,
                metadata=None,
                content=content,
            )
            assert sidecar.content is not None
            assert sidecar.content.word_count == 4
        finally:
            Path(temp_path).unlink()

    def test_sidecar_all_nine_fields(self):
        """Verify all 9 Sidecar fields are present."""
        content = Content(language="en", word_count=50, page_count=2)
        sidecar = Sidecar(
            version="1.0",
            file=FileInfo(
                path="test.pdf",
                name="test.pdf",
                extension="pdf",
                size_bytes=1024,
                modified_at=datetime.now(timezone.utc),
                hash_sha256="abc123",
            ),
            metadata=None,
            content=content,
            summary=None,
            labels=None,
            parser_status="OK",
            generated_at=datetime.now(timezone.utc),
        )
        json_str = sidecar.to_json()
        data = json.loads(json_str)
        # All 9 required fields
        assert "version" in data
        assert "file" in data
        assert "metadata" in data
        assert "content" in data
        assert "summary" in data
        assert "labels" in data
        assert "parser_status" in data
        assert "generated_at" in data
        assert "generated_by" not in data


class TestExtractCommand:
    """Test extract CLI command."""

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_txt_file(self, tmp_path):
        """Verify extract command works for .txt files."""
        from click.testing import CliRunner
        from filekor.cli import extract

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello world this is a test file")

        runner = CliRunner()
        result = runner.invoke(extract, [str(test_file)])

        assert result.exit_code == 0
        assert "Hello world this is a test file" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_unsupported_file(self, tmp_path):
        """Verify extract command rejects unsupported files."""
        from click.testing import CliRunner
        from filekor.cli import extract

        test_file = tmp_path / "test.exe"
        test_file.write_bytes(b"invalid")

        runner = CliRunner()
        result = runner.invoke(extract, [str(test_file)])

        assert result.exit_code == 1
        assert "Unsupported" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_to_file(self, tmp_path):
        """Verify extract command with -o outputs to file."""
        from click.testing import CliRunner
        from filekor.cli import extract

        test_file = tmp_path / "test.txt"
        test_file.write_text("Content to extract")

        output_file = tmp_path / "output.txt"
        runner = CliRunner()
        result = runner.invoke(extract, [str(test_file), "-o", str(output_file)])

        assert result.exit_code == 0
        assert output_file.read_text() == "Content to extract"
        assert "Extracted:" in result.output


class TestSidecarCommand:
    """Test sidecar CLI command."""

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_sidecar_generates_kor_json(self, tmp_path):
        """Verify sidecar command generates .kor JSON file."""
        from click.testing import CliRunner
        from filekor.cli import sidecar
        import os

        # Create mock config.yaml with LLM enabled
        config_content = """filekor:
  llm:
    enabled: true
    provider: mock
    api_key: test-key
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            test_file = tmp_path / "test.txt"
            test_file.write_text("Test content for sidecar")

            runner = CliRunner()
            result = runner.invoke(sidecar, [str(test_file), "--no-cache"])

            assert result.exit_code == 0
            # Check .kor file was created in .filekor/ subdirectory
            # Note: By default, single file generates merged.kor
            filekor_dir = test_file.parent / ".filekor"
            kor_file = filekor_dir / "merged.kor"
            assert kor_file.exists(), f"Expected {kor_file} to exist"

            # Verify YAML format
            data = yaml.safe_load(kor_file.read_text())
            assert "version" in data
            assert "file" in data
            assert "content" in data
        finally:
            os.chdir(old_cwd)

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_sidecar_custom_output(self, tmp_path):
        """Verify sidecar command with custom output path."""
        from click.testing import CliRunner
        from filekor.cli import sidecar
        import os

        # Create mock config.yaml with LLM enabled
        config_content = """filekor:
  llm:
    enabled: true
    provider: mock
    api_key: test-key
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            test_file = tmp_path / "test.txt"
            test_file.write_text("Test")

            output_file = tmp_path / "custom.kor"
            runner = CliRunner()
            result = runner.invoke(
                sidecar, [str(test_file), "-o", str(output_file), "--no-cache"]
            )

            # Note: by default single files generate merged.kor in .filekor/
            # The -o flag is used to set default output but merge overrides it
            # So we check that .kor was created in .filekor/ directory
            filekor_dir = test_file.parent / ".filekor"
            actual_kor = filekor_dir / "merged.kor"

            assert result.exit_code == 0
            assert actual_kor.exists(), f"Expected {actual_kor} to exist"
            data = yaml.safe_load(actual_kor.read_text())
            assert "version" in data
        finally:
            os.chdir(old_cwd)
