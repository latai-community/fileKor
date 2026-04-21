"""Tests for cli/delete.py — delete command."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from filekor.cli.delete import delete


class TestDeleteByPath:
    @patch("filekor.core.hasher.calculate_sha256")
    @patch("filekor.cli.delete.delete_by_sha")
    def test_delete_by_path(self, mock_delete_by_sha, mock_sha, tmp_path):
        """Delete by --path calculates SHA and deletes."""
        mock_sha.return_value = "abc123"
        mock_delete_by_sha.return_value = (1, 1)

        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")

        runner = CliRunner()
        with patch("click.confirm", return_value=True):
            result = runner.invoke(delete, [str(tmp_path), "--path", str(test_file)])

        assert result.exit_code == 0
        mock_sha.assert_called_once_with(str(test_file))
        mock_delete_by_sha.assert_called_once()
        assert "Deleted:" in result.output

    @patch("filekor.cli.delete.get_deletion_preview")
    def test_delete_dry_run(self, mock_preview, tmp_path):
        """--dry-run shows preview without deleting."""
        mock_preview.return_value = (
            ["abc123"],
            [("doc.txt", str(tmp_path / ".filekor" / "doc.txt.kor"))],
        )

        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")

        runner = CliRunner()
        result = runner.invoke(delete, [str(tmp_path), "--sha", "abc123", "--dry-run"])

        assert result.exit_code == 0
        assert "Dry Run" in result.output
        assert "abc123" in result.output
        assert "doc.txt" in result.output

    @patch("filekor.core.hasher.calculate_sha256")
    @patch("filekor.cli.delete.delete_by_sha")
    def test_delete_force_skips_confirm(self, mock_delete_by_sha, mock_sha, tmp_path):
        """--force skips the confirmation prompt."""
        mock_sha.return_value = "abc123"
        mock_delete_by_sha.return_value = (1, 1)

        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")

        runner = CliRunner()
        with patch("click.confirm") as mock_confirm:
            result = runner.invoke(
                delete, [str(tmp_path), "--path", str(test_file), "--force"]
            )

        assert result.exit_code == 0
        mock_confirm.assert_not_called()

    @patch("filekor.cli.delete.delete_by_sha")
    def test_delete_db_only(self, mock_delete_by_sha, tmp_path):
        """--db sets scope to 'db' and only deletes DB records."""
        mock_delete_by_sha.return_value = (1, 0)

        runner = CliRunner()
        with patch("click.confirm", return_value=True):
            result = runner.invoke(delete, [str(tmp_path), "--sha", "abc123", "--db"])

        assert result.exit_code == 0
        call_kwargs = mock_delete_by_sha.call_args.kwargs
        assert call_kwargs.get("scope") == "db"

    def test_delete_no_identifier(self, tmp_path):
        """Missing --sha, --path, or --input exits with code 1."""
        runner = CliRunner()
        result = runner.invoke(delete, [str(tmp_path)])

        assert result.exit_code == 1
        assert "Must specify --sha, --path, or --input" in result.output

    def test_delete_path_not_found(self, tmp_path):
        """--path with nonexistent file exits with code 2 (Click validation)."""
        runner = CliRunner()
        result = runner.invoke(
            delete, [str(tmp_path), "--path", str(tmp_path / "ghost.txt")]
        )

        assert result.exit_code == 2
        assert "does not exist" in result.output or "File not found" in result.output

    @patch("filekor.cli.delete.delete_by_sha")
    def test_delete_confirm_cancel(self, mock_delete_by_sha, tmp_path):
        """Canceling the confirmation prompt exits with code 0."""
        mock_delete_by_sha.return_value = (1, 1)

        runner = CliRunner()
        with patch("click.confirm", return_value=False):
            result = runner.invoke(delete, [str(tmp_path), "--sha", "abc123"])

        assert result.exit_code == 0
        assert "Cancelled" in result.output

    @patch("filekor.cli.delete.delete_by_sha")
    def test_delete_verbose(self, mock_delete_by_sha, tmp_path):
        """--verbose passes verbose=True to delete_by_sha."""
        mock_delete_by_sha.return_value = (1, 0)

        runner = CliRunner()
        with patch("click.confirm", return_value=True):
            result = runner.invoke(
                delete, [str(tmp_path), "--sha", "abc123", "--verbose"]
            )

        assert result.exit_code == 0
        call_kwargs = mock_delete_by_sha.call_args.kwargs
        assert call_kwargs.get("verbose") is True
