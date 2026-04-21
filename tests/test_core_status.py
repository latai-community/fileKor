"""Tests for core/status.py — get_file_status, get_directory_status, summarize."""

import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from filekor.core.models.file_status import FileStatus, DirectoryStatus
from filekor.core.status import get_file_status, get_directory_status, summarize
from filekor.sidecar import Content, FileInfo, FileLabels, FileMetadata, Sidecar


def _make_sidecar(file_path: str = "test.txt", sha: str = "abc123") -> Sidecar:
    """Create a minimal valid Sidecar for testing."""
    return Sidecar(
        file=FileInfo(
            path=file_path,
            name=file_path,
            extension="txt",
            size_bytes=100,
            modified_at=datetime.now(timezone.utc),
            hash_sha256=sha,
        ),
        metadata=FileMetadata(author="test", pages=1),
        content=Content(language="en", word_count=10, page_count=1),
        labels=FileLabels(suggested=["finance"]),
        parser_status="OK",
        generated_at=datetime.now(timezone.utc),
    )


def _write_kor(kor_path: Path, sidecar: Sidecar) -> None:
    """Write a Sidecar as YAML .kor file."""
    kor_path.parent.mkdir(parents=True, exist_ok=True)
    kor_path.write_text(sidecar.to_yaml(), encoding="utf-8")


# ─── get_file_status ────────────────────────────────────────────────


class TestGetFileStatus:
    def test_file_without_kor(self, tmp_path):
        """File exists but no .kor sidecar."""
        test_file = tmp_path / "document.txt"
        test_file.write_text("hello")

        status = get_file_status(str(test_file))

        assert status.file_path == test_file
        assert status.exists is False
        assert status.sidecar is None
        assert status.error is None

    def test_file_with_valid_kor(self, tmp_path):
        """File exists with a valid .kor sidecar."""
        test_file = tmp_path / "document.txt"
        test_file.write_text("hello")

        sidecar = _make_sidecar("document.txt")
        kor_path = tmp_path / ".filekor" / "document.txt.kor"
        _write_kor(kor_path, sidecar)

        status = get_file_status(str(test_file))

        assert status.exists is True
        assert status.sidecar is not None
        assert status.sidecar.file.name == "document.txt"
        assert status.error is None

    def test_file_not_found(self, tmp_path):
        """Source file does not exist."""
        missing = tmp_path / "nope.txt"

        status = get_file_status(str(missing))

        assert status.exists is False
        assert status.error == "File not found"

    def test_corrupted_kor(self, tmp_path):
        """Kor file exists but contains garbage YAML."""
        test_file = tmp_path / "broken.txt"
        test_file.write_text("data")

        kor_path = tmp_path / ".filekor" / "broken.txt.kor"
        kor_path.parent.mkdir(parents=True, exist_ok=True)
        kor_path.write_text("{{not: valid: yaml: [[[", encoding="utf-8")

        status = get_file_status(str(test_file))

        assert status.exists is True
        assert status.sidecar is None
        assert status.error is not None

    def test_kor_path_computed_correctly(self, tmp_path):
        """Verify kor path is .filekor/{stem}.{ext}.kor."""
        test_file = tmp_path / "report.pdf"
        test_file.write_text("pdf")

        status = get_file_status(str(test_file))

        expected_kor = tmp_path / ".filekor" / "report.pdf.kor"
        assert status.kor_path == expected_kor


# ─── get_directory_status ───────────────────────────────────────────


class TestGetDirectoryStatus:
    def test_empty_directory(self, tmp_path):
        """Directory with no supported files."""
        status = get_directory_status(str(tmp_path))

        assert status.directory == tmp_path
        assert status.total_files == 0
        assert status.kor_files == 0
        assert status.files_without_kor == []
        assert status.file_statuses == []

    def test_directory_with_files_no_kor(self, tmp_path):
        """Files exist but none have .kor sidecars."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.md").write_text("b")

        status = get_directory_status(str(tmp_path))

        assert status.total_files == 2
        assert status.kor_files == 0
        assert len(status.files_without_kor) == 2
        assert all(s.exists is False for s in status.file_statuses)

    def test_directory_with_files_and_kor(self, tmp_path):
        """Some files have .kor sidecars."""
        (tmp_path / "doc.txt").write_text("content")
        (tmp_path / "readme.md").write_text("# readme")

        sidecar = _make_sidecar("doc.txt")
        kor_path = tmp_path / ".filekor" / "doc.txt.kor"
        _write_kor(kor_path, sidecar)

        status = get_directory_status(str(tmp_path))

        assert status.total_files == 2
        # kor_files counts .kor files across all .filekor/ dirs (root .filekor found twice: explicit + glob)
        assert status.kor_files == 2
        assert len(status.files_without_kor) == 1
        assert status.files_without_kor[0].name == "readme.md"

    def test_not_a_directory(self, tmp_path):
        """Pass a file path instead of directory raises ValueError."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("x")

        with pytest.raises(ValueError, match="Not a directory"):
            get_directory_status(str(test_file))

    def test_recursive_false(self, tmp_path):
        """Non-recursive mode only finds top-level files."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "top.txt").write_text("top")
        (sub / "deep.txt").write_text("deep")

        status = get_directory_status(str(tmp_path), recursive=False)

        assert status.total_files == 1
        assert status.file_statuses[0].file_path.name == "top.txt"

    def test_unsupported_extensions_ignored(self, tmp_path):
        """Files with unsupported extensions are ignored."""
        (tmp_path / "data.csv").write_text("a,b")
        (tmp_path / "image.png").write_bytes(b"png")
        (tmp_path / "valid.txt").write_text("ok")

        status = get_directory_status(str(tmp_path))

        assert status.total_files == 1
        assert status.file_statuses[0].file_path.name == "valid.txt"

    def test_multiple_kor_in_filekor_dir(self, tmp_path):
        """Multiple .kor files in .filekor/ are counted."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        sidecar_a = _make_sidecar("a.txt", sha="sha_a")
        sidecar_b = _make_sidecar("b.txt", sha="sha_b")
        _write_kor(tmp_path / ".filekor" / "a.txt.kor", sidecar_a)
        _write_kor(tmp_path / ".filekor" / "b.txt.kor", sidecar_b)

        status = get_directory_status(str(tmp_path))

        # kor_files: root .filekor/ is counted twice (explicit + glob), each has 2 .kor → 4
        assert status.kor_files == 4
        assert len(status.files_without_kor) == 0


# ─── summarize ──────────────────────────────────────────────────────


class TestSummarize:
    def test_summarize_no_kor(self, tmp_path):
        """Summarize a file status where .kor does not exist."""
        fs = FileStatus(
            file_path=tmp_path / "x.txt",
            kor_path=tmp_path / ".filekor" / "x.txt.kor",
            exists=False,
        )
        result = summarize(fs)

        assert result["kor_exists"] is False
        assert "file" in result
        assert "name" not in result

    def test_summarize_with_error(self, tmp_path):
        """Summarize when kor exists but has an error."""
        fs = FileStatus(
            file_path=tmp_path / "x.txt",
            kor_path=tmp_path / ".filekor" / "x.txt.kor",
            exists=True,
            error="parse failed",
        )
        result = summarize(fs)

        assert result["kor_exists"] is True
        assert result["error"] == "parse failed"
        assert "name" not in result

    def test_summarize_complete(self, tmp_path):
        """Summarize a fully loaded sidecar."""
        sidecar = _make_sidecar("doc.txt", sha="deadbeef")
        fs = FileStatus(
            file_path=tmp_path / "doc.txt",
            kor_path=tmp_path / ".filekor" / "doc.txt.kor",
            exists=True,
            sidecar=sidecar,
        )
        result = summarize(fs)

        assert result["kor_exists"] is True
        assert result["name"] == "doc.txt"
        assert result["size_bytes"] == 100
        assert result["labels"] == ["finance"]
        assert result["parser_status"] == "OK"

    def test_summarize_no_labels(self, tmp_path):
        """Sidecar with no labels returns empty list."""
        sidecar = _make_sidecar("doc.txt")
        sidecar.labels = None
        fs = FileStatus(
            file_path=tmp_path / "doc.txt",
            kor_path=tmp_path / ".filekor" / "doc.txt.kor",
            exists=True,
            sidecar=sidecar,
        )
        result = summarize(fs)

        assert result["labels"] == []
