"""Tests for cli/list.py — list command."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from filekor.cli.list import list


class TestListCommand:
    def test_list_text_format(self, tmp_path):
        """Default text format output."""
        runner = CliRunner()
        with patch("filekor.cli.list.list_kor_files") as mock_list:
            mock_list.return_value = [
                {
                    "sha256": "abc123def456",
                    "name": "doc.txt",
                    "path": str(tmp_path / ".filekor" / "doc.txt.kor"),
                    "type": "individual",
                }
            ]
            with patch("filekor.cli.list.list_as_text") as mock_text:
                mock_text.return_value = "abc123def456... doc.txt"
                result = runner.invoke(list, [str(tmp_path)])

        assert result.exit_code == 0
        assert "abc123def456... doc.txt" in result.output
        assert "Total: 1 files" in result.output

    def test_list_json_format(self, tmp_path):
        """JSON format output."""
        runner = CliRunner()
        with patch("filekor.cli.list.list_kor_files") as mock_list:
            mock_list.return_value = [
                {
                    "sha256": "abc123def456",
                    "name": "doc.txt",
                    "path": str(tmp_path / ".filekor" / "doc.txt.kor"),
                    "type": "individual",
                }
            ]
            with patch("filekor.cli.list.list_as_json") as mock_json:
                mock_json.return_value = '[{"sha256": "abc123def456"}]'
                result = runner.invoke(list, [str(tmp_path), "--format", "json"])

        assert result.exit_code == 0
        assert '"sha256": "abc123def456"' in result.output

    def test_list_csv_format(self, tmp_path):
        """CSV format output."""
        runner = CliRunner()
        with patch("filekor.cli.list.list_kor_files") as mock_list:
            mock_list.return_value = [
                {
                    "sha256": "abc123def456",
                    "name": "doc.txt",
                    "path": str(tmp_path / ".filekor" / "doc.txt.kor"),
                    "type": "individual",
                }
            ]
            with patch("filekor.cli.list.list_as_csv") as mock_csv:
                mock_csv.return_value = (
                    "sha256,name,path,type\nabc123def456,doc.txt,path,individual"
                )
                result = runner.invoke(list, [str(tmp_path), "--format", "csv"])

        assert result.exit_code == 0
        assert "sha256,name,path,type" in result.output

    def test_list_sha_format(self, tmp_path):
        """SHA-only format output."""
        runner = CliRunner()
        with patch("filekor.cli.list.list_kor_files") as mock_list:
            mock_list.return_value = [
                {
                    "sha256": "abc123def456",
                    "name": "doc.txt",
                    "path": str(tmp_path / ".filekor" / "doc.txt.kor"),
                    "type": "individual",
                }
            ]
            with patch("filekor.cli.list.list_sha_only") as mock_sha:
                mock_sha.return_value = "abc123def456"
                result = runner.invoke(list, [str(tmp_path), "--format", "sha"])

        assert result.exit_code == 0
        assert "abc123def456" in result.output

    def test_list_ext_filter(self, tmp_path):
        """--ext filter is passed to list_kor_files."""
        runner = CliRunner()
        with patch("filekor.cli.list.list_kor_files") as mock_list:
            mock_list.return_value = []
            with patch("filekor.cli.list.list_as_text") as mock_text:
                mock_text.return_value = ""
                result = runner.invoke(list, [str(tmp_path), "--ext", "pdf"])

        assert result.exit_code == 0
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs.get("extension") == "pdf"

    def test_list_no_merged(self, tmp_path):
        """--no-merged excludes merged entries."""
        runner = CliRunner()
        with patch("filekor.cli.list.list_kor_files") as mock_list:
            mock_list.return_value = []
            with patch("filekor.cli.list.list_as_text") as mock_text:
                mock_text.return_value = ""
                result = runner.invoke(list, [str(tmp_path), "--no-merged"])

        assert result.exit_code == 0
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs.get("include_merged") is False

    def test_list_empty_directory(self, tmp_path):
        """Empty directory shows zero results."""
        runner = CliRunner()
        with patch("filekor.cli.list.list_kor_files") as mock_list:
            mock_list.return_value = []
            with patch("filekor.cli.list.list_as_text") as mock_text:
                mock_text.return_value = ""
                result = runner.invoke(list, [str(tmp_path)])

        assert result.exit_code == 0
        assert "Total: 0 files" in result.output
