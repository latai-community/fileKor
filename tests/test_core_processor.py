"""Tests for filekor.core.processor module."""

from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from filekor.core.processor import DirectoryProcessor, process_directory
from filekor.core.models.process_result import ProcessResult
from filekor.sidecar import FileMetadata


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_config_loads():
    """Patch LLMConfig.load and LabelsConfig.load globally for all tests."""
    mock_llm = MagicMock()
    mock_llm.enabled = False
    mock_llm.api_key = None
    mock_llm.workers = 4

    mock_labels = MagicMock()
    mock_labels.synonyms = {}

    with (
        patch("filekor.core.processor.LLMConfig.load", return_value=mock_llm),
        patch("filekor.core.processor.LabelsConfig.load", return_value=mock_labels),
    ):
        yield


@pytest.fixture
def mock_adapter():
    """Return a mocked PyExifToolAdapter instance."""
    adapter = MagicMock()
    adapter.is_available.return_value = False
    adapter.extract_metadata.return_value = None
    return adapter


@pytest.fixture
def processor(mock_adapter):
    """Return a DirectoryProcessor with a mocked adapter."""
    with patch("filekor.core.processor.PyExifToolAdapter", return_value=mock_adapter):
        proc = DirectoryProcessor()
    return proc


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    """Create a sample .txt file in tmp_path."""
    file_path = tmp_path / "document.txt"
    file_path.write_text("hello world", encoding="utf-8")
    return file_path


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a sample .pdf file in tmp_path."""
    file_path = tmp_path / "report.pdf"
    file_path.write_text("fake pdf content", encoding="utf-8")
    return file_path


# ---------------------------------------------------------------------------
# DirectoryProcessor.__init__
# ---------------------------------------------------------------------------


class TestDirectoryProcessorInit:
    def test_defaults(self, mock_adapter):
        with patch(
            "filekor.core.processor.PyExifToolAdapter", return_value=mock_adapter
        ):
            proc = DirectoryProcessor()

        assert proc.workers == 4
        assert proc.output_dir is None
        assert proc.llm_config is not None
        assert proc.labels_config is not None
        assert proc.adapter is mock_adapter

    def test_custom_configs(self, mock_adapter):
        custom_llm = MagicMock(enabled=True, api_key="key", workers=8)
        custom_labels = MagicMock(synonyms={"foo": ["bar"]})

        with patch(
            "filekor.core.processor.PyExifToolAdapter", return_value=mock_adapter
        ):
            proc = DirectoryProcessor(
                workers=8,
                output_dir=Path("/out"),
                llm_config=custom_llm,
                labels_config=custom_labels,
            )

        assert proc.workers == 8
        assert proc.output_dir == Path("/out")
        assert proc.llm_config is custom_llm
        assert proc.labels_config is custom_labels


# ---------------------------------------------------------------------------
# get_output_path
# ---------------------------------------------------------------------------


class TestGetOutputPath:
    def test_without_output_dir(self, processor: DirectoryProcessor, sample_txt: Path):
        out = processor.get_output_path(sample_txt)
        expected = sample_txt.parent / ".filekor" / "document.txt.kor"
        assert out == expected
        assert out.parent.exists()

    def test_with_output_dir(
        self, processor: DirectoryProcessor, sample_txt: Path, tmp_path: Path
    ):
        out_dir = tmp_path / "kor_output"
        processor.output_dir = out_dir

        out = processor.get_output_path(sample_txt)
        expected = out_dir / "document.txt.kor"
        assert out == expected
        assert out.parent.exists()


# ---------------------------------------------------------------------------
# process_file
# ---------------------------------------------------------------------------


class TestProcessFile:
    def test_success_without_metadata_and_without_labels(
        self, processor: DirectoryProcessor, sample_txt: Path
    ):
        with patch("filekor.cli.extract_text", return_value=("hello", 2, None)):
            result = processor.process_file(sample_txt)

        assert isinstance(result, ProcessResult)
        assert result.success is True
        assert result.file_path == sample_txt
        assert result.output_path is not None
        assert result.output_path.exists()
        assert result.labels is None
        assert result.error is None

    def test_success_with_metadata(
        self, processor: DirectoryProcessor, sample_txt: Path, mock_adapter
    ):
        mock_adapter.is_available.return_value = True
        mock_adapter.extract_metadata.return_value = FileMetadata(author="Alice")

        with patch("filekor.cli.extract_text", return_value=("hello", 2, None)):
            result = processor.process_file(sample_txt)

        assert result.success is True
        mock_adapter.extract_metadata.assert_called_once_with(str(sample_txt))

    def test_success_with_labels(self, mock_adapter, sample_txt: Path):
        llm = MagicMock(enabled=True, api_key="fake-key", workers=4)
        labels_cfg = MagicMock()

        with patch(
            "filekor.core.processor.PyExifToolAdapter", return_value=mock_adapter
        ):
            proc = DirectoryProcessor(llm_config=llm, labels_config=labels_cfg, add_labels=True)

        with (
            patch("filekor.cli.extract_text", return_value=("hello", 2, None)),
            patch(
                "filekor.core.processor.suggest_labels",
                return_value=["finance", "legal"],
            ),
        ):
            result = proc.process_file(sample_txt)

        assert result.success is True
        assert result.labels == ["finance", "legal"]

    def test_success_no_text_extraction(
        self, processor: DirectoryProcessor, sample_txt: Path
    ):
        with patch("filekor.cli.extract_text", side_effect=Exception("boom")):
            result = processor.process_file(sample_txt)

        assert result.success is True
        assert result.output_path is not None

    def test_error_during_processing(
        self, processor: DirectoryProcessor, sample_txt: Path
    ):
        # Force an error inside get_output_path by passing an invalid object
        processor.output_dir = None
        with patch("filekor.cli.extract_text", side_effect=Exception("boom")):
            # Even if extract_text fails, Sidecar.create + get_output_path should succeed.
            # To trigger a real error, patch Sidecar.create to raise.
            with patch(
                "filekor.core.processor.Sidecar.create",
                side_effect=RuntimeError("fail"),
            ):
                result = processor.process_file(sample_txt)

        assert result.success is False
        assert "fail" in result.error

    def test_adapter_extract_metadata_exception_is_ignored(
        self, processor: DirectoryProcessor, sample_txt: Path, mock_adapter
    ):
        mock_adapter.is_available.return_value = True
        mock_adapter.extract_metadata.side_effect = Exception("exif err")

        with patch("filekor.cli.extract_text", return_value=("hello", 2, None)):
            result = processor.process_file(sample_txt)

        assert result.success is True


# ---------------------------------------------------------------------------
# process_directory (method)
# ---------------------------------------------------------------------------


class TestProcessDirectoryMethod:
    def test_with_files(self, processor: DirectoryProcessor, tmp_path: Path):
        # Create two supported files
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.pdf").write_text("b")

        with patch("filekor.cli.extract_text", return_value=("x", 1, None)):
            results = processor.process_directory(tmp_path)

        assert len(results) == 2
        assert all(r.success for r in results)

    def test_empty_directory(self, processor: DirectoryProcessor, tmp_path: Path):
        results = processor.process_directory(tmp_path)
        assert results == []

    def test_recursive_true(self, processor: DirectoryProcessor, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.md").write_text("md")
        (tmp_path / "root.txt").write_text("txt")

        with patch("filekor.cli.extract_text", return_value=("x", 1, None)):
            results = processor.process_directory(tmp_path, recursive=True)

        assert len(results) == 2

    def test_recursive_false(self, processor: DirectoryProcessor, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.md").write_text("md")
        (tmp_path / "root.txt").write_text("txt")

        with patch("filekor.cli.extract_text", return_value=("x", 1, None)):
            results = processor.process_directory(tmp_path, recursive=False)

        assert len(results) == 1
        assert results[0].file_path.name == "root.txt"

    def test_callback_invoked(self, processor: DirectoryProcessor, tmp_path: Path):
        (tmp_path / "file.txt").write_text("data")
        called_with: List[ProcessResult] = []

        def cb(result: ProcessResult) -> None:
            called_with.append(result)

        with patch("filekor.cli.extract_text", return_value=("x", 1, None)):
            processor.process_directory(tmp_path, callback=cb)

        assert len(called_with) == 1
        assert called_with[0].success is True

    def test_skips_filekor_directory(
        self, processor: DirectoryProcessor, tmp_path: Path
    ):
        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir()
        (filekor_dir / "dummy.txt").write_text("should be ignored")
        (tmp_path / "real.txt").write_text("process me")

        with patch("filekor.cli.extract_text", return_value=("x", 1, None)):
            results = processor.process_directory(tmp_path)

        assert len(results) == 1
        assert results[0].file_path.name == "real.txt"


# ---------------------------------------------------------------------------
# process_directory (convenience function)
# ---------------------------------------------------------------------------


class TestProcessDirectoryFunction:
    def test_uses_workers_from_llm_config(self, tmp_path: Path):
        llm = MagicMock(enabled=False, api_key=None, workers=2)

        (tmp_path / "doc.txt").write_text("hello")

        with (
            patch("filekor.core.processor.LLMConfig.load", return_value=llm),
            patch("filekor.core.processor.PyExifToolAdapter") as mock_adapter_cls,
            patch("filekor.cli.extract_text", return_value=("x", 1, None)),
        ):
            mock_adapter_cls.return_value.is_available.return_value = False
            results = process_directory(str(tmp_path))

        assert len(results) == 1
        assert results[0].success is True

    def test_custom_output_dir(self, tmp_path: Path):
        out_dir = tmp_path / "output"
        llm = MagicMock(enabled=False, api_key=None, workers=4)

        (tmp_path / "doc.txt").write_text("hello")

        with (
            patch("filekor.core.processor.LLMConfig.load", return_value=llm),
            patch("filekor.core.processor.PyExifToolAdapter") as mock_adapter_cls,
            patch("filekor.cli.extract_text", return_value=("x", 1, None)),
        ):
            mock_adapter_cls.return_value.is_available.return_value = False
            results = process_directory(
                str(tmp_path),
                output_dir=str(out_dir),
                llm_config=llm,
            )

        assert len(results) == 1
        assert results[0].output_path.parent == out_dir

    def test_passes_callback(self, tmp_path: Path):
        llm = MagicMock(enabled=False, api_key=None, workers=4)
        called = []

        (tmp_path / "doc.txt").write_text("hello")

        def cb(r: ProcessResult) -> None:
            called.append(r)

        with (
            patch("filekor.core.processor.LLMConfig.load", return_value=llm),
            patch("filekor.core.processor.PyExifToolAdapter") as mock_adapter_cls,
            patch("filekor.cli.extract_text", return_value=("x", 1, None)),
        ):
            mock_adapter_cls.return_value.is_available.return_value = False
            process_directory(str(tmp_path), llm_config=llm, callback=cb)

        assert len(called) == 1
