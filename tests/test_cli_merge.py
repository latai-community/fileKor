"""Tests for cli/merge.py — merge command."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from filekor.cli.merge import merge


class TestMergeCommand:
    def test_merge_success(self, tmp_path):
        """Successful merge shows merged file count."""
        runner = CliRunner()
        with patch("filekor.cli.merge.merge_kor_files") as mock_merge:
            mock_merge.return_value = [MagicMock(), MagicMock()]
            result = runner.invoke(merge, [str(tmp_path)])

        assert result.exit_code == 0
        assert "Merged:" in result.output
        assert "2 files ->" in result.output
        assert "Completed:" in result.output

    def test_merge_output_flag(self, tmp_path):
        """--output is passed to merge_kor_files and shown in output."""
        runner = CliRunner()
        custom_output = tmp_path / "output.kor"
        with patch("filekor.cli.merge.merge_kor_files") as mock_merge:
            mock_merge.return_value = [MagicMock()]
            result = runner.invoke(
                merge, [str(tmp_path), "--output", str(custom_output)]
            )

        assert result.exit_code == 0
        assert "output.kor" in result.output
        call_kwargs = mock_merge.call_args.kwargs
        assert call_kwargs.get("output_path") == str(custom_output)

    def test_merge_no_erase(self, tmp_path):
        """--no-erase passes delete_sources=False."""
        runner = CliRunner()
        with patch("filekor.cli.merge.merge_kor_files") as mock_merge:
            mock_merge.return_value = [MagicMock()]
            result = runner.invoke(merge, [str(tmp_path), "--no-erase"])

        assert result.exit_code == 0
        call_kwargs = mock_merge.call_args.kwargs
        assert call_kwargs.get("delete_sources") is False

    def test_merge_no_kor_files(self, tmp_path):
        """No .kor files found exits with code 0 and warning."""
        runner = CliRunner()
        with patch("filekor.cli.merge.merge_kor_files") as mock_merge:
            mock_merge.return_value = []
            result = runner.invoke(merge, [str(tmp_path)])

        assert result.exit_code == 0
        assert "No .kor files found to merge" in result.output

    def test_merge_file_not_found(self, tmp_path):
        """FileNotFoundError from merge_kor_files exits with code 1."""
        runner = CliRunner()
        with patch("filekor.cli.merge.merge_kor_files") as mock_merge:
            mock_merge.side_effect = FileNotFoundError(".filekor directory not found")
            result = runner.invoke(merge, [str(tmp_path)])

        assert result.exit_code == 1
        assert "Error:" in result.output
