"""Tests for cli/sync.py — sync command."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from filekor.cli.sync import sync


def _make_kor_file(path: Path, content: str = "dummy") -> None:
    """Create a minimal .kor file for sync tests."""
    path.write_text(content, encoding="utf-8")


class TestSyncFile:
    @patch("filekor.cli.sync.sync_file")
    def test_sync_file_success(self, mock_sync_file, tmp_path):
        """Sync a single .kor file."""
        kor_file = tmp_path / "doc.kor"
        kor_file.write_text("dummy", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(sync, [str(kor_file)])

        assert result.exit_code == 0
        mock_sync_file.assert_called_once_with(str(kor_file))
        assert "Synced:" in result.output

    def test_sync_file_not_kor(self, tmp_path):
        """Syncing a non-.kor file exits with code 1."""
        txt_file = tmp_path / "doc.txt"
        txt_file.write_text("data")

        runner = CliRunner()
        result = runner.invoke(sync, [str(txt_file)])

        assert result.exit_code == 1
        assert "File must have .kor extension" in result.output

    def test_sync_file_not_found(self, tmp_path):
        """Nonexistent file exits with code 2 (Click validation)."""
        runner = CliRunner()
        result = runner.invoke(sync, [str(tmp_path / "ghost.kor")])

        assert result.exit_code == 2
        assert "does not exist" in result.output or "File not found" in result.output

    @patch("filekor.cli.sync.sync_file")
    def test_sync_file_error(self, mock_sync_file, tmp_path):
        """Error during sync exits with code 1."""
        mock_sync_file.side_effect = Exception("db error")

        kor_file = tmp_path / "doc.kor"
        kor_file.write_text("dummy", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(sync, [str(kor_file)])

        assert result.exit_code == 1
        assert "db error" in result.output


class TestSyncDirectory:
    @patch("filekor.cli.sync.sync_file")
    def test_sync_directory_success(self, mock_sync_file, tmp_path):
        """Sync all .kor files in a directory."""
        (tmp_path / "a.kor").write_text("dummy", encoding="utf-8")
        (tmp_path / "b.kor").write_text("dummy", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(sync, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert "Found 2 .kor files to sync" in result.output
        assert mock_sync_file.call_count == 2

    @patch("filekor.cli.sync.sync_file")
    def test_sync_directory_auto_detect(self, mock_sync_file, tmp_path):
        """Passing a directory without --dir also works."""
        (tmp_path / "a.kor").write_text("dummy", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(sync, [str(tmp_path)])

        assert result.exit_code == 0
        assert "Found 1 .kor files to sync" in result.output
        mock_sync_file.assert_called_once()

    @patch("filekor.cli.sync.sync_file")
    def test_sync_directory_verbose(self, mock_sync_file, tmp_path):
        """--verbose shows each synced file."""
        (tmp_path / "a.kor").write_text("dummy", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(sync, [str(tmp_path), "--dir", "--verbose"])

        assert result.exit_code == 0
        assert "Synced:" in result.output
        assert "a.kor" in result.output

    def test_sync_directory_no_kor_files(self, tmp_path):
        """Directory with no .kor files exits with code 0."""
        (tmp_path / "a.txt").write_text("not a kor")

        runner = CliRunner()
        result = runner.invoke(sync, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert "No .kor files found" in result.output

    @patch("filekor.cli.sync.sync_file")
    def test_sync_directory_some_failures(self, mock_sync_file, tmp_path):
        """Some files fail, exit code is 1."""
        (tmp_path / "good.kor").write_text("dummy", encoding="utf-8")
        (tmp_path / "bad.kor").write_text("dummy", encoding="utf-8")

        def side_effect(path):
            if "bad" in path:
                raise Exception("parse error")
            return 1

        mock_sync_file.side_effect = side_effect

        runner = CliRunner()
        result = runner.invoke(sync, [str(tmp_path), "--dir"])

        assert result.exit_code == 1
        assert "Completed: 1/2 synced, 1 failed" in result.output
        assert "parse error" in result.output
