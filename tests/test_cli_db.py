"""Tests for cli/db.py - database commands."""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from filekor.cli.db import db, _format_size, _has_db_config, _query_scalar


def _create_test_db(db_path: Path) -> None:
    """Create a test SQLite database with schema and sample data."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Schema version
    conn.execute("CREATE TABLE schema_version (version INTEGER)")
    conn.execute("INSERT INTO schema_version (version) VALUES (1)")

    # Files table
    conn.execute(
        """
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            hash_sha256 TEXT,
            name TEXT,
            extension TEXT,
            file_path TEXT,
            size_bytes INTEGER,
            modified_at TEXT,
            kor_path TEXT,
            summary_short TEXT,
            summary_long TEXT
        )
        """
    )

    # Labels table
    conn.execute(
        """
        CREATE TABLE labels (
            file_id INTEGER,
            label TEXT
        )
        """
    )

    # FTS5 virtual table
    conn.execute(
        "CREATE VIRTUAL TABLE files_fts USING fts5(name, content='', content_rowid='id')"
    )

    # Insert test data
    conn.execute(
        """
        INSERT INTO files (id, hash_sha256, name, extension, file_path, size_bytes, modified_at, kor_path, summary_short, summary_long)
        VALUES (1, 'abc123def456', 'test.pdf', 'pdf', '/docs/test.pdf', 2048, '2024-01-01', '/docs/.filekor/test.pdf.kor', 'Short summary', 'Long summary')
        """
    )
    conn.execute(
        """
        INSERT INTO files (id, hash_sha256, name, extension, file_path, size_bytes, modified_at, kor_path, summary_short, summary_long)
        VALUES (2, 'xyz789abc012', 'report.md', 'md', '/docs/report.md', 512, '2024-02-01', '/docs/.filekor/report.md.kor', NULL, NULL)
        """
    )

    # Insert labels
    conn.execute("INSERT INTO labels (file_id, label) VALUES (1, 'finance')")
    conn.execute("INSERT INTO labels (file_id, label) VALUES (1, 'contract')")
    conn.execute("INSERT INTO labels (file_id, label) VALUES (2, 'documentation')")

    # Insert FTS5 data
    conn.execute("INSERT INTO files_fts (rowid, name) VALUES (1, 'test.pdf')")
    conn.execute("INSERT INTO files_fts (rowid, name) VALUES (2, 'report.md')")

    conn.commit()
    conn.close()


@pytest.fixture
def test_db(tmp_path):
    """Create a test database file with sample data."""
    db_path = tmp_path / "test.db"
    _create_test_db(db_path)
    return db_path


# ─── db summary (no subcommand) ─────────────────────────────────────


class TestDbSummary:
    def test_db_summary_no_database(self, tmp_path):
        """Summary when database does not exist."""
        db_path = tmp_path / "nonexistent.db"
        config_mock = MagicMock(db_path=db_path)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, [])

        assert result.exit_code == 0
        assert "Database" in result.output
        assert "no (default)" in result.output or "yes" in result.output
        assert "no" in result.output  # Exists: no

    def test_db_summary_with_database(self, test_db):
        """Summary when database exists."""
        config_mock = MagicMock(db_path=test_db)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, [])

        assert result.exit_code == 0
        assert "Database" in result.output
        assert "yes" in result.output  # Exists: yes
        assert "2" in result.output  # Files count
        assert "3" in result.output  # Labels count
        assert "v1" in result.output  # Schema version

    def test_db_summary_custom_config(self, tmp_path):
        """--config flag loads custom config."""
        config_mock = MagicMock(db_path=tmp_path / "custom.db")
        custom_cfg = tmp_path / "custom.yaml"
        custom_cfg.write_text("filekor:\n  db:\n    path: /tmp/custom.db\n")

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["--config", str(custom_cfg)])

        assert result.exit_code == 0
        # FilekorConfig.load should have been called with custom path

    def test_db_summary_database_error(self, test_db):
        """Summary handles database read errors gracefully."""
        config_mock = MagicMock(db_path=test_db)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            with patch("sqlite3.connect", side_effect=Exception("db error")):
                result = runner.invoke(db, [])

        assert result.exit_code == 0
        assert "db error" in result.output


# ─── db files ───────────────────────────────────────────────────────


class TestDbFiles:
    def test_db_files_success(self, test_db):
        """List all indexed files."""
        config_mock = MagicMock(db_path=test_db)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["files"])

        assert result.exit_code == 0
        assert "test.pdf" in result.output
        assert "report.md" in result.output
        assert "Total:" in result.output
        assert "2" in result.output

    def test_db_files_no_database(self, tmp_path):
        """Error when database does not exist."""
        db_path = tmp_path / "nonexistent.db"
        config_mock = MagicMock(db_path=db_path)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["files"])

        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_db_files_empty(self, tmp_path):
        """Message when no files indexed."""
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE files (id INTEGER, hash_sha256 TEXT, extension TEXT, file_path TEXT)"
        )
        conn.execute("CREATE TABLE labels (file_id INTEGER, label TEXT)")
        conn.execute("CREATE TABLE schema_version (version INTEGER)")
        conn.commit()
        conn.close()

        config_mock = MagicMock(db_path=db_path)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["files"])

        assert result.exit_code == 0
        assert "No files indexed" in result.output


# ─── db labels ──────────────────────────────────────────────────────


class TestDbLabels:
    def test_db_labels_success(self, test_db):
        """List all labels with file counts."""
        config_mock = MagicMock(db_path=test_db)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["labels"])

        assert result.exit_code == 0
        assert "finance" in result.output
        assert "contract" in result.output
        assert "documentation" in result.output
        assert "Total:" in result.output
        assert "3" in result.output

    def test_db_labels_no_database(self, tmp_path):
        """Error when database does not exist."""
        db_path = tmp_path / "nonexistent.db"
        config_mock = MagicMock(db_path=db_path)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["labels"])

        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_db_labels_empty(self, tmp_path):
        """Message when no labels indexed."""
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE files (id INTEGER)")
        conn.execute("CREATE TABLE labels (file_id INTEGER, label TEXT)")
        conn.execute("CREATE TABLE schema_version (version INTEGER)")
        conn.commit()
        conn.close()

        config_mock = MagicMock(db_path=db_path)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["labels"])

        assert result.exit_code == 0
        assert "No labels indexed" in result.output


# ─── db search ──────────────────────────────────────────────────────


class TestDbSearch:
    def test_db_search_success(self, test_db):
        """Search files by FTS5 query."""
        config_mock = MagicMock(db_path=test_db)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["search", "test"])

        assert result.exit_code == 0
        assert "test.pdf" in result.output
        assert "Total:" in result.output

    def test_db_search_no_results(self, test_db):
        """Message when no search results."""
        config_mock = MagicMock(db_path=test_db)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["search", "nonexistent"])

        assert result.exit_code == 0
        assert "No results" in result.output

    def test_db_search_no_database(self, tmp_path):
        """Error when database does not exist."""
        db_path = tmp_path / "nonexistent.db"
        config_mock = MagicMock(db_path=db_path)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["search", "test"])

        assert result.exit_code == 1
        assert "does not exist" in result.output


# ─── db show ────────────────────────────────────────────────────────


class TestDbShow:
    def test_db_show_success(self, test_db):
        """Show file details by SHA256 prefix."""
        config_mock = MagicMock(db_path=test_db)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["show", "abc123"])

        assert result.exit_code == 0
        assert "test.pdf" in result.output
        assert "finance" in result.output
        assert "contract" in result.output
        assert "Short summary" in result.output
        assert "Long summary" in result.output

    def test_db_show_not_found(self, test_db):
        """Error when hash prefix not found."""
        config_mock = MagicMock(db_path=test_db)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["show", "zzz"])

        assert result.exit_code == 1
        assert "No file found" in result.output

    def test_db_show_no_database(self, tmp_path):
        """Error when database does not exist."""
        db_path = tmp_path / "nonexistent.db"
        config_mock = MagicMock(db_path=db_path)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["show", "abc"])

        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_db_show_no_labels(self, tmp_path):
        """Show file without labels displays dash."""
        db_path = tmp_path / "nolabels.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE files (id INTEGER PRIMARY KEY, hash_sha256 TEXT, name TEXT, extension TEXT, file_path TEXT, size_bytes INTEGER, modified_at TEXT, kor_path TEXT, summary_short TEXT, summary_long TEXT)"
        )
        conn.execute("CREATE TABLE labels (file_id INTEGER, label TEXT)")
        conn.execute("CREATE TABLE schema_version (version INTEGER)")
        conn.execute(
            "INSERT INTO files VALUES (1, 'nolabel001', 'clean.txt', 'txt', '/clean.txt', 100, '2024-01-01', '/clean.kor', NULL, NULL)"
        )
        # No labels inserted for this file
        conn.commit()
        conn.close()

        config_mock = MagicMock(db_path=db_path)

        runner = CliRunner()
        with patch("filekor.cli.db.FilekorConfig.load", return_value=config_mock):
            result = runner.invoke(db, ["show", "nolabel"])

        assert result.exit_code == 0
        assert "clean.txt" in result.output
        assert "Labels" in result.output


# ─── helper functions ───────────────────────────────────────────────


class TestHelperFunctions:
    def test_format_size_bytes(self):
        assert _format_size(512) == "512 B"

    def test_format_size_kb(self):
        assert _format_size(1536) == "1.5 KB"

    def test_format_size_mb(self):
        assert _format_size(2 * 1024 * 1024) == "2.0 MB"

    def test_query_scalar_success(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (42)")
        conn.commit()

        result = _query_scalar(conn, "SELECT id FROM t")
        assert result == 42
        conn.close()

    def test_query_scalar_empty(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()

        result = _query_scalar(conn, "SELECT id FROM t")
        assert result is None
        conn.close()

    def test_query_scalar_error(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        result = _query_scalar(conn, "SELECT id FROM nonexistent")
        assert result is None
        conn.close()

    def test_has_db_config_false(self, tmp_path):
        """No config file means no db config."""
        with patch.object(Path, "exists", return_value=False):
            assert _has_db_config() is False
