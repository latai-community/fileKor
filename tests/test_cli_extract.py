"""Tests for cli/extract.py — extract command."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from filekor.cli.extract import extract


class TestExtractFile:
    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_file_success(self, tmp_path):
        """Extract text from a single supported file."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("hello world")

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.return_value = ("hello world", 2, 1)
            result = runner.invoke(extract, [str(test_file)])

        assert result.exit_code == 0
        assert "hello world" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_file_with_output(self, tmp_path):
        """Extract text to an output file via -o."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")
        output_file = tmp_path / "out.txt"

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.return_value = ("extracted content", 2, 1)
            result = runner.invoke(extract, [str(test_file), "-o", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
        assert output_file.read_text(encoding="utf-8") == "extracted content"
        assert f"Extracted: {output_file}" in result.output

    def test_extract_unsupported_file_type(self, tmp_path):
        """Unsupported extension exits with code 1."""
        test_file = tmp_path / "data.xyz"
        test_file.write_text("data")

        runner = CliRunner()
        result = runner.invoke(extract, [str(test_file)])

        assert result.exit_code == 1
        assert "Unsupported file type: .xyz" in result.output

    def test_extract_file_not_found(self, tmp_path):
        """Nonexistent file exits with code 2 (Click validation)."""
        runner = CliRunner()
        result = runner.invoke(extract, [str(tmp_path / "ghost.txt")])

        assert result.exit_code == 2
        assert "File not found" in result.output or "does not exist" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_file_read_error(self, tmp_path):
        """Error during text extraction exits with code 1."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")

        runner = CliRunner()
        with patch(
            "filekor.cli.extract.extract_text", side_effect=Exception("read failed")
        ):
            result = runner.invoke(extract, [str(test_file)])

        assert result.exit_code == 1
        assert "read failed" in result.output


class TestExtractDirectory:
    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_success(self, tmp_path):
        """Extract text from all supported files in a directory."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.return_value = ("text", 1, 1)
            with patch("filekor.core.labels.LLMConfig.load") as mock_llm:
                mock_llm.return_value = MagicMock(workers=2)
                with patch("filekor.core.labels.LabelsConfig.load") as mock_labels:
                    mock_labels.return_value = MagicMock()
                    result = runner.invoke(extract, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert "Found 2 files to process" in result.output
        assert "Completed: 2/2 files" in result.output

    def test_extract_directory_not_a_directory(self, tmp_path):
        """Passing a file with --dir exits with code 1."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("x")

        runner = CliRunner()
        result = runner.invoke(extract, [str(test_file), "--dir"])

        assert result.exit_code == 1
        assert "Not a directory" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_no_supported_files(self, tmp_path):
        """Directory with no supported files exits with code 0."""
        (tmp_path / "data.csv").write_text("a,b")

        runner = CliRunner()
        result = runner.invoke(extract, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert "No supported files found" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_with_output(self, tmp_path):
        """Extract directory with -o writes .txt files to output dir."""
        (tmp_path / "a.txt").write_text("aaa")
        output_dir = tmp_path / "out"

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.return_value = ("extracted", 1, 1)
            with patch("filekor.core.labels.LLMConfig.load") as mock_llm:
                mock_llm.return_value = MagicMock(workers=2)
                with patch("filekor.core.labels.LabelsConfig.load") as mock_labels:
                    mock_labels.return_value = MagicMock()
                    result = runner.invoke(
                        extract, [str(tmp_path), "--dir", "-o", str(output_dir)]
                    )

        assert result.exit_code == 0
        assert (output_dir / "a.txt").exists()
        assert (output_dir / "a.txt").read_text(encoding="utf-8") == "extracted"
