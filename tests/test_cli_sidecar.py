"""Tests for cli/sidecar.py — sidecar command."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from filekor.cli.sidecar import sidecar
from filekor.core.models.process_result import ProcessResult
from filekor.sidecar import Content, FileInfo, FileLabels, Sidecar


def _make_sidecar(name: str = "test.txt", sha: str = "abc123") -> Sidecar:
    return Sidecar(
        file=FileInfo(
            path=name,
            name=name,
            extension="txt",
            size_bytes=42,
            modified_at=datetime.now(timezone.utc),
            hash_sha256=sha,
        ),
        content=Content(language="en", word_count=5, page_count=1),
        labels=FileLabels(suggested=["finance"]),
        parser_status="OK",
        generated_at=datetime.now(timezone.utc),
    )


# ─── sidecar file ───────────────────────────────────────────────────


class TestSidecarFile:
    @patch("filekor.cli.HAS_PYPDF", False)
    def test_sidecar_file_success(self, tmp_path):
        """Successful sidecar generation for a single file."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("hello world")

        runner = CliRunner()
        with patch("filekor.cli.sidecar.extract_text") as mock_extract:
            mock_extract.return_value = ("hello world", 2, 1)
            with patch("filekor.cli.sidecar._auto_sync_hook"):
                result = runner.invoke(sidecar, [str(test_file)])

        assert result.exit_code == 0
        assert "Created:" in result.output
        merged = tmp_path / ".filekor" / "merged.kor"
        assert merged.exists()

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_sidecar_file_no_cache(self, tmp_path):
        """--no-cache forces regeneration even if sidecar exists."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("hello world")
        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir()
        merged = filekor_dir / "merged.kor"
        merged.write_text("existing")

        runner = CliRunner()
        with patch("filekor.cli.sidecar.extract_text") as mock_extract:
            mock_extract.return_value = ("hello world", 2, 1)
            with patch("filekor.cli.sidecar._auto_sync_hook"):
                result = runner.invoke(sidecar, [str(test_file), "--no-cache"])

        assert result.exit_code == 0
        assert "Created:" in result.output
        assert "merged.kor" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_sidecar_file_merge_flag(self, tmp_path):
        """--merge generates merged.kor."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("hello world")

        runner = CliRunner()
        with patch("filekor.cli.sidecar.extract_text") as mock_extract:
            mock_extract.return_value = ("hello world", 2, 1)
            with patch("filekor.cli.sidecar._auto_sync_hook"):
                result = runner.invoke(sidecar, [str(test_file), "--merge"])

        assert result.exit_code == 0
        merged = tmp_path / ".filekor" / "merged.kor"
        assert merged.exists()

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_sidecar_file_no_merge_flag(self, tmp_path):
        """--no-merge generates individual .kor file."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("hello world")

        runner = CliRunner()
        with patch("filekor.cli.sidecar.extract_text") as mock_extract:
            mock_extract.return_value = ("hello world", 2, 1)
            with patch("filekor.cli.sidecar._auto_sync_hook"):
                result = runner.invoke(sidecar, [str(test_file), "--no-merge"])

        assert result.exit_code == 0
        kor = tmp_path / ".filekor" / "doc.txt.kor"
        assert kor.exists()
        assert "Created:" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_sidecar_file_verbose(self, tmp_path):
        """--verbose shows detailed output."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("hello world")

        runner = CliRunner()
        with patch("filekor.cli.sidecar.extract_text") as mock_extract:
            mock_extract.return_value = ("hello world", 2, 1)
            with patch("filekor.cli.sidecar._auto_sync_hook"):
                result = runner.invoke(sidecar, [str(test_file), "--verbose"])

        assert result.exit_code == 0
        assert (
            "Metadata:" in result.output
            or "Text:" in result.output
            or "Labels:" in result.output
        )

    def test_sidecar_file_unsupported_type(self, tmp_path):
        """Unsupported file type exits with code 1."""
        test_file = tmp_path / "data.csv"
        test_file.write_text("a,b")

        runner = CliRunner()
        result = runner.invoke(sidecar, [str(test_file)])

        assert result.exit_code == 1
        assert "Unsupported file type" in result.output

    def test_sidecar_file_not_found(self, tmp_path):
        """Missing file exits with code 2."""
        runner = CliRunner()
        result = runner.invoke(sidecar, [str(tmp_path / "missing.txt")])

        assert result.exit_code == 2
        assert "File not found" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_sidecar_file_llm_labels(self, tmp_path):
        """LLM configuration is shown in verbose mode when mocked."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("hello world")

        runner = CliRunner()
        with patch("filekor.cli.sidecar.extract_text") as mock_extract:
            mock_extract.return_value = ("hello world", 2, 1)
            with patch("filekor.core.labels.LLMConfig.load") as mock_llm:
                mock_llm.return_value = MagicMock(
                    enabled=True,
                    provider="mock",
                    model="mock-model",
                    api_key="test-key",
                    workers=4,
                    auto_sync=False,
                )
                with patch("filekor.cli.sidecar._auto_sync_hook"):
                    result = runner.invoke(sidecar, [str(test_file), "--verbose"])

        assert result.exit_code == 0
        assert "mock" in result.output


# ─── sidecar directory ──────────────────────────────────────────────


class TestSidecarDirectory:
    @patch("filekor.cli.HAS_PYPDF", False)
    def test_sidecar_directory_success(self, tmp_path):
        """Successful sidecar generation for a directory."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        runner = CliRunner()
        with patch("filekor.cli.sidecar.DirectoryProcessor") as mock_proc_cls:
            mock_proc = MagicMock()
            mock_proc_cls.return_value = mock_proc

            results = [
                ProcessResult(
                    file_path=tmp_path / "a.txt",
                    success=True,
                    output_path=tmp_path / ".filekor" / "a.txt.kor",
                    labels=None,
                ),
                ProcessResult(
                    file_path=tmp_path / "b.txt",
                    success=True,
                    output_path=tmp_path / ".filekor" / "b.txt.kor",
                    labels=None,
                ),
            ]

            def _side_effect(directory, callback=None):
                if callback:
                    for r in results:
                        callback(r)
                return results

            mock_proc.process_directory.side_effect = _side_effect
            with patch("filekor.cli.sidecar.create_emitter") as mock_emitter:
                mock_emitter.return_value = MagicMock()
                with patch("filekor.cli.sidecar._auto_sync_hook"):
                    result = runner.invoke(sidecar, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert "Found 2 files to process" in result.output
        assert "Completed: 2/2 successful" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_sidecar_directory_llm_labels(self, tmp_path):
        """Directory processing with mocked LLM labels."""
        (tmp_path / "a.txt").write_text("a")

        runner = CliRunner()
        with patch("filekor.cli.sidecar.DirectoryProcessor") as mock_proc_cls:
            mock_proc = MagicMock()
            mock_proc_cls.return_value = mock_proc
            mock_proc.process_directory.return_value = [
                ProcessResult(
                    file_path=tmp_path / "a.txt",
                    success=True,
                    output_path=tmp_path / ".filekor" / "a.txt.kor",
                    labels=["finance", "contract"],
                ),
            ]
            with patch("filekor.cli.sidecar.create_emitter") as mock_emitter:
                mock_emitter.return_value = MagicMock()
                with patch("filekor.cli.sidecar._auto_sync_hook"):
                    result = runner.invoke(sidecar, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert "Found 1 files to process" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_sidecar_directory_empty(self, tmp_path):
        """Directory with no supported files exits 0."""
        (tmp_path / "data.csv").write_text("a,b")
        (tmp_path / "image.png").write_bytes(b"fake")

        runner = CliRunner()
        result = runner.invoke(sidecar, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert "No supported files found" in result.output
