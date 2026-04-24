"""Tests for cli/extract.py — extract command."""

import json
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
                    result = runner.invoke(extract, [str(tmp_path), "--dir", "--verbose"])

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


class TestExtractDirectoryFormats:
    """Tests for output formats in directory mode."""

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_format_separated(self, tmp_path):
        """Separated format includes clear file headers with SHA256 when verbose."""
        (tmp_path / "doc.pdf").write_text("pdf content")

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.return_value = ("pdf content", 10, 1)
            with patch("filekor.cli.extract.calculate_sha256") as mock_sha:
                mock_sha.return_value = "a3f2b8c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1"
                result = runner.invoke(
                    extract, [str(tmp_path), "--dir", "--format", "separated", "--verbose"]
                )

        assert result.exit_code == 0
        assert ">>> FILE: doc.pdf" in result.output
        assert "sha256:" in result.output
        assert "<<< END: doc.pdf" in result.output
        assert "pdf content" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_format_json(self, tmp_path):
        """JSON format outputs NDJSON (one JSON object per line)."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.side_effect = [
                ("a", 1, 1),
                ("b", 1, 1),
            ]
            with patch("filekor.cli.extract.calculate_sha256") as mock_sha:
                mock_sha.side_effect = [
                    "sha256hash1111111111",
                    "sha256hash2222222222",
                ]
                result = runner.invoke(
                    extract, [str(tmp_path), "--dir", "--format", "json"]
                )

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2

        obj1 = json.loads(lines[0])
        obj2 = json.loads(lines[1])
        assert obj1["file"] == "a.txt"
        assert obj1["content"] == "a"
        assert obj1["success"] is True
        assert obj1["words"] == 1
        assert "sha256" in obj1
        assert obj2["file"] == "b.txt"

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_format_json_error(self, tmp_path):
        """JSON format handles errors gracefully."""
        (tmp_path / "fail.txt").write_text("x")

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.side_effect = Exception("read error")
            result = runner.invoke(
                extract, [str(tmp_path), "--dir", "--format", "json"]
            )

        assert result.exit_code == 0
        line = result.output.strip()
        obj = json.loads(line)
        assert obj["success"] is False
        assert "read error" in obj["error"]
        assert obj["file"] == "fail.txt"

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_format_with_output_ignores_format(self, tmp_path):
        """When -o is specified, files are saved with --format extension."""
        (tmp_path / "a.txt").write_text("aaa")
        output_dir = tmp_path / "out"

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.return_value = ("extracted", 1, 1)
            with patch("filekor.cli.extract.calculate_sha256") as mock_sha:
                mock_sha.return_value = "sha256hash0000000000"
                result = runner.invoke(
                    extract,
                    [str(tmp_path), "--dir", "-o", str(output_dir), "--format", "json"],
                )

        assert result.exit_code == 0
        assert (output_dir / "a.json").exists()
        content = (output_dir / "a.json").read_text(encoding="utf-8")
        assert '"file": "a.txt"' in content
        assert '"success": true' in content
        assert "{" not in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_format_separated_default(self, tmp_path):
        """Default format (no --format flag) uses separated with headers but no progress logs."""
        (tmp_path / "doc.txt").write_text("content")

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.return_value = ("content", 1, 1)
            with patch("filekor.cli.extract.calculate_sha256") as mock_sha:
                mock_sha.return_value = "sha256hash0000000000"
                result = runner.invoke(extract, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert ">>> FILE: doc.txt" in result.output
        assert "<<< END: doc.txt" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_json_no_progress_message(self, tmp_path):
        """JSON format does not show progress messages."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.side_effect = [
                ("a", 1, 1),
                ("b", 1, 1),
            ]
            with patch("filekor.cli.extract.calculate_sha256") as mock_sha:
                mock_sha.side_effect = [
                    "sha256hash1111111111",
                    "sha256hash2222222222",
                ]
                result = runner.invoke(
                    extract, [str(tmp_path), "--dir", "--format", "json"]
                )

        assert result.exit_code == 0
        assert "Found" not in result.output
        assert "Completed" not in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_separated_with_subdirectory(self, tmp_path):
        """Separated format shows relative paths with subdirectories when verbose."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "doc.txt").write_text("content")

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.return_value = ("content", 1, 1)
            with patch("filekor.cli.extract.calculate_sha256") as mock_sha:
                mock_sha.return_value = "sha256hash0000000000"
                result = runner.invoke(
                    extract, [str(tmp_path), "--dir", "--format", "separated", "--verbose"]
                )

        assert result.exit_code == 0
        assert ">>> FILE:" in result.output
        assert "subdir" in result.output
        assert "doc.txt" in result.output
        assert "<<< END:" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_subdirectory_structure_preserved(self, tmp_path):
        """Output with -o preserves subdirectory structure."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "doc.txt").write_text("content")
        output_dir = tmp_path / "out"

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.return_value = ("content", 1, 1)
            result = runner.invoke(
                extract, [str(tmp_path), "--dir", "-o", str(output_dir)]
            )

        assert result.exit_code == 0
        assert (output_dir / "subdir" / "doc.txt").exists()
        assert (output_dir / "subdir" / "doc.txt").read_text(encoding="utf-8") == "content"

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_extract_directory_json_format_output(self, tmp_path):
        """Output with --format json saves .json files."""
        (tmp_path / "a.txt").write_text("aaa")
        output_dir = tmp_path / "out"

        runner = CliRunner()
        with patch("filekor.cli.extract.extract_text") as mock_extract:
            mock_extract.return_value = ("content", 1, 1)
            with patch("filekor.cli.extract.calculate_sha256") as mock_sha:
                mock_sha.return_value = "sha256hash0000000000"
                result = runner.invoke(
                    extract, [str(tmp_path), "--dir", "-o", str(output_dir), "--format", "json"]
                )

        assert result.exit_code == 0
        assert (output_dir / "a.json").exists()
        content = (output_dir / "a.json").read_text(encoding="utf-8")
        assert '"file": "a.txt"' in content
        assert '"success": true' in content