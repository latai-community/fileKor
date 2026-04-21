"""Tests for core/list.py — list_kor_files, list_as_text, list_as_json, list_as_csv, list_sha_only."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from filekor.core.models.file_status import FileStatus, DirectoryStatus
from filekor.core.list import (
    list_kor_files,
    list_as_text,
    list_as_json,
    list_as_csv,
    list_sha_only,
)
from filekor.sidecar import FileInfo, FileLabels, Sidecar


def _make_sidecar(
    name: str = "doc.txt", sha: str = "abc123", ext: str = "txt"
) -> Sidecar:
    """Create a minimal Sidecar for testing."""
    return Sidecar(
        file=FileInfo(
            path=name,
            name=name,
            extension=ext,
            size_bytes=100,
            modified_at=datetime.now(timezone.utc),
            hash_sha256=sha,
        ),
        labels=FileLabels(suggested=["finance"]),
        parser_status="OK",
        generated_at=datetime.now(timezone.utc),
    )


def _make_file_statuses(tmp_path, specs):
    """Build a list of FileStatus from specs: list of (name, ext, has_kor, sha)."""
    statuses = []
    for name, ext, has_kor, sha in specs:
        file_path = tmp_path / name
        file_path.write_text("data")
        kor_path = tmp_path / ".filekor" / f"{name}.kor"
        sidecar = _make_sidecar(name=name, sha=sha, ext=ext) if has_kor else None
        statuses.append(
            FileStatus(
                file_path=file_path,
                kor_path=kor_path,
                exists=has_kor,
                sidecar=sidecar,
            )
        )
    return statuses


# ─── list_kor_files ─────────────────────────────────────────────────


class TestListKorFiles:
    @patch("filekor.core.status.get_directory_status")
    def test_empty_directory(self, mock_status, tmp_path):
        """No files with .kor returns empty list."""
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=0,
            kor_files=0,
            files_without_kor=[],
            file_statuses=[],
        )
        result = list_kor_files(str(tmp_path))
        assert result == []

    @patch("filekor.core.status.get_directory_status")
    def test_with_individual_files(self, mock_status, tmp_path):
        """Files with .kor sidecars are listed."""
        statuses = _make_file_statuses(
            tmp_path,
            [
                ("doc.txt", "txt", True, "sha1"),
                ("readme.md", "md", True, "sha2"),
            ],
        )
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=2,
            kor_files=2,
            files_without_kor=[],
            file_statuses=statuses,
        )

        result = list_kor_files(str(tmp_path))

        assert len(result) == 2
        assert result[0]["sha256"] == "sha1"
        assert result[0]["type"] == "individual"
        assert result[1]["sha256"] == "sha2"

    @patch("filekor.core.status.get_directory_status")
    def test_skips_files_without_kor(self, mock_status, tmp_path):
        """Files without .kor sidecar are excluded."""
        statuses = _make_file_statuses(
            tmp_path,
            [
                ("has_kor.txt", "txt", True, "sha1"),
                ("no_kor.txt", "txt", False, "sha2"),
            ],
        )
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=2,
            kor_files=1,
            files_without_kor=[tmp_path / "no_kor.txt"],
            file_statuses=statuses,
        )

        result = list_kor_files(str(tmp_path))

        assert len(result) == 1
        assert result[0]["sha256"] == "sha1"

    @patch("filekor.core.status.get_directory_status")
    def test_filter_by_extension(self, mock_status, tmp_path):
        """Extension filter returns only matching files."""
        statuses = _make_file_statuses(
            tmp_path,
            [
                ("doc.pdf", "pdf", True, "sha_pdf"),
                ("doc.txt", "txt", True, "sha_txt"),
                ("readme.md", "md", True, "sha_md"),
            ],
        )
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=3,
            kor_files=3,
            files_without_kor=[],
            file_statuses=statuses,
        )

        result = list_kor_files(str(tmp_path), extension="pdf")

        assert len(result) == 1
        assert result[0]["name"] == "doc.pdf"

    @patch("filekor.core.status.get_directory_status")
    def test_extension_case_insensitive(self, mock_status, tmp_path):
        """Extension filter is case-insensitive."""
        statuses = _make_file_statuses(
            tmp_path,
            [
                ("Doc.PDF", "PDF", True, "sha1"),
            ],
        )
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=1,
            kor_files=1,
            files_without_kor=[],
            file_statuses=statuses,
        )

        result = list_kor_files(str(tmp_path), extension="pdf")
        assert len(result) == 1

    @patch("filekor.core.merge.load_merged_kor")
    @patch("filekor.core.status.get_directory_status")
    def test_include_merged(self, mock_status, mock_merged, tmp_path):
        """include_merged=True loads merged.kor files."""
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=0,
            kor_files=0,
            files_without_kor=[],
            file_statuses=[],
        )

        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir()
        (filekor_dir / "merged.kor").write_text("dummy")

        merged_sidecar = _make_sidecar("merged_doc.pdf", sha="merged_sha", ext="pdf")
        mock_merged.return_value = [merged_sidecar]

        result = list_kor_files(str(tmp_path), include_merged=True)

        assert len(result) == 1
        assert result[0]["sha256"] == "merged_sha"
        assert result[0]["type"] == "merged"

    @patch("filekor.core.merge.load_merged_kor")
    @patch("filekor.core.status.get_directory_status")
    def test_merged_exception_skipped(self, mock_status, mock_merged, tmp_path):
        """Exception loading merged.kor is silently skipped."""
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=0,
            kor_files=0,
            files_without_kor=[],
            file_statuses=[],
        )

        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir()
        (filekor_dir / "merged.kor").write_text("broken")

        mock_merged.side_effect = Exception("corrupt")

        result = list_kor_files(str(tmp_path), include_merged=True)
        assert result == []

    @patch("filekor.core.status.get_directory_status")
    def test_no_merged_without_flag(self, mock_status, tmp_path):
        """include_merged=False skips merged files even if present."""
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=0,
            kor_files=0,
            files_without_kor=[],
            file_statuses=[],
        )

        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir()
        (filekor_dir / "merged.kor").write_text("dummy")

        result = list_kor_files(str(tmp_path), include_merged=False)
        assert result == []


# ─── format functions ───────────────────────────────────────────────


class TestListFormats:
    @patch("filekor.core.list.list_kor_files")
    def test_list_as_text(self, mock_list):
        mock_list.return_value = [
            {"sha256": "a" * 64, "name": "doc.txt", "path": "/x", "type": "individual"},
            {"sha256": "b" * 64, "name": "merged.pdf", "path": "/y", "type": "merged"},
        ]
        output = list_as_text(".")
        lines = output.strip().split("\n")

        assert len(lines) == 2
        assert lines[0].startswith("a" * 16)
        assert "doc.txt" in lines[0]
        assert "(merged)" in lines[1]

    @patch("filekor.core.list.list_kor_files")
    def test_list_as_text_empty(self, mock_list):
        mock_list.return_value = []
        output = list_as_text(".")
        assert output == ""

    @patch("filekor.core.list.list_kor_files")
    def test_list_as_json(self, mock_list):
        import json

        mock_list.return_value = [
            {"sha256": "abc", "name": "f.txt", "path": "/p", "type": "individual"},
        ]
        output = list_as_json(".")
        data = json.loads(output)

        assert len(data) == 1
        assert data[0]["sha256"] == "abc"

    @patch("filekor.core.list.list_kor_files")
    def test_list_as_csv(self, mock_list):
        mock_list.return_value = [
            {"sha256": "sha1", "name": "doc.txt", "path": "/x", "type": "individual"},
        ]
        output = list_as_csv(".")
        lines = output.strip().split("\n")

        assert lines[0] == "sha256,name,path,type"
        assert "sha1,doc.txt,/x,individual" in lines[1]

    @patch("filekor.core.list.list_kor_files")
    def test_list_sha_only(self, mock_list):
        mock_list.return_value = [
            {"sha256": "sha_aaa", "name": "a.txt", "path": "/x", "type": "individual"},
            {"sha256": "sha_bbb", "name": "b.txt", "path": "/y", "type": "individual"},
        ]
        output = list_sha_only(".")
        lines = output.strip().split("\n")

        assert lines == ["sha_aaa", "sha_bbb"]

    @patch("filekor.core.list.list_kor_files")
    def test_list_sha_only_empty(self, mock_list):
        mock_list.return_value = []
        output = list_sha_only(".")
        assert output == ""
