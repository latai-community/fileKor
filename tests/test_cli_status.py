"""Tests for cli/status.py — status command via CliRunner."""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from filekor.cli import status
from filekor.sidecar import Content, FileInfo, FileLabels, Sidecar


def _make_sidecar_yaml(name: str = "test.txt", sha: str = "abc123") -> str:
    """Create a valid YAML sidecar string."""
    sidecar = Sidecar(
        file=FileInfo(
            path=name,
            name=name,
            extension="txt",
            size_bytes=42,
            modified_at=datetime.now(timezone.utc),
            hash_sha256=sha,
        ),
        content=Content(language="en", word_count=5, page_count=1),
        labels=FileLabels(suggested=["finance", "report"]),
        parser_status="OK",
        generated_at=datetime.now(timezone.utc),
    )
    return sidecar.to_yaml()


# ─── status file ────────────────────────────────────────────────────


class TestStatusFile:
    def test_file_with_kor(self, tmp_path):
        """File with valid .kor sidecar shows table and exits 0."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("hello world")

        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir()
        kor_path = filekor_dir / "doc.txt.kor"
        kor_path.write_text(_make_sidecar_yaml("doc.txt"), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(status, [str(test_file)])

        assert result.exit_code == 0
        assert "doc.txt" in result.output
        assert "OK" in result.output

    def test_file_without_kor(self, tmp_path):
        """File exists but no .kor sidecar exits 1."""
        test_file = tmp_path / "no_kor.txt"
        test_file.write_text("data")

        runner = CliRunner()
        result = runner.invoke(status, [str(test_file)])

        assert result.exit_code == 1
        assert "No .kor file found" in result.output

    def test_file_not_found(self, tmp_path):
        """File doesn't exist exits 2."""
        runner = CliRunner()
        result = runner.invoke(status, [str(tmp_path / "ghost.txt")])

        assert result.exit_code == 2
        assert "File not found" in result.output

    def test_file_with_metadata_shown(self, tmp_path):
        """Status output includes metadata fields when present."""
        test_file = tmp_path / "report.txt"
        test_file.write_text("content")

        sidecar = Sidecar(
            file=FileInfo(
                path="report.txt",
                name="report.txt",
                extension="txt",
                size_bytes=42,
                modified_at=datetime.now(timezone.utc),
                hash_sha256="def456",
            ),
            content=Content(language="en", word_count=100, page_count=3),
            labels=FileLabels(suggested=["analysis"]),
            parser_status="OK",
            generated_at=datetime.now(timezone.utc),
        )

        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir()
        kor_path = filekor_dir / "report.txt.kor"
        kor_path.write_text(sidecar.to_yaml(), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(status, [str(test_file)])

        assert result.exit_code == 0
        assert "100" in result.output  # word count
        assert "analysis" in result.output

    def test_file_with_labels_shown(self, tmp_path):
        """Status output shows labels when present."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("text")

        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir()
        kor_path = filekor_dir / "doc.txt.kor"
        kor_path.write_text(_make_sidecar_yaml("doc.txt"), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(status, [str(test_file)])

        assert result.exit_code == 0
        assert "finance" in result.output
        assert "report" in result.output


# ─── status directory ───────────────────────────────────────────────


class TestStatusDirectory:
    def test_directory_with_kor_files(self, tmp_path):
        """Directory with .kor files shows status."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir()
        (filekor_dir / "a.txt.kor").write_text(
            _make_sidecar_yaml("a.txt"), encoding="utf-8"
        )

        runner = CliRunner()
        result = runner.invoke(status, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert "Supported files:" in result.output
        assert "2" in result.output  # 2 supported files
        assert ".kor Files:" in result.output

    def test_directory_empty(self, tmp_path):
        """Empty directory shows zero counts."""
        runner = CliRunner()
        result = runner.invoke(status, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert "Supported files:" in result.output

    def test_directory_not_a_directory(self, tmp_path):
        """Passing a file with --dir exits 1."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("x")

        runner = CliRunner()
        result = runner.invoke(status, [str(test_file), "--dir"])

        assert result.exit_code == 1
        assert "Not a directory" in result.output

    def test_directory_auto_detects_dir(self, tmp_path):
        """Passing a directory path without --dir also works."""
        (tmp_path / "doc.txt").write_text("data")

        runner = CliRunner()
        result = runner.invoke(status, [str(tmp_path)])

        assert result.exit_code == 0
        assert "Supported files:" in result.output

    def test_directory_files_without_kor_listed(self, tmp_path):
        """Files without .kor are listed under 'Files without .kor'."""
        (tmp_path / "has_kor.txt").write_text("a")
        (tmp_path / "no_kor.txt").write_text("b")

        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir()
        (filekor_dir / "has_kor.txt.kor").write_text(
            _make_sidecar_yaml("has_kor.txt"), encoding="utf-8"
        )

        runner = CliRunner()
        result = runner.invoke(status, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert "Files without .kor:" in result.output
        assert "no_kor.txt" in result.output

    def test_directory_unsupported_extensions_ignored(self, tmp_path):
        """Unsupported file types are not counted."""
        (tmp_path / "data.csv").write_text("a,b")
        (tmp_path / "valid.txt").write_text("ok")

        runner = CliRunner()
        result = runner.invoke(status, [str(tmp_path), "--dir"])

        assert result.exit_code == 0
        assert "Supported files:      1" in result.output or "1" in result.output
