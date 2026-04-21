"""Tests for core/delete.py — delete_by_sha, delete_by_path, delete_by_input, get_deletion_preview."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from filekor.core.models.file_status import FileStatus, DirectoryStatus
from filekor.core.delete import (
    delete_by_sha,
    delete_by_path,
    delete_by_input,
    get_deletion_preview,
)
from filekor.sidecar import FileInfo, FileLabels, Sidecar


def _make_sidecar(name: str = "doc.txt", sha: str = "abc123") -> Sidecar:
    return Sidecar(
        file=FileInfo(
            path=name,
            name=name,
            extension="txt",
            size_bytes=100,
            modified_at=datetime.now(timezone.utc),
            hash_sha256=sha,
        ),
        labels=FileLabels(suggested=["test"]),
        parser_status="OK",
        generated_at=datetime.now(timezone.utc),
    )


def _make_file_status(tmp_path, name: str, sha: str, exists: bool = True) -> FileStatus:
    file_path = tmp_path / name
    file_path.write_text("data")
    kor_path = tmp_path / ".filekor" / f"{name}.kor"
    sidecar = _make_sidecar(name=name, sha=sha) if exists else None
    return FileStatus(
        file_path=file_path,
        kor_path=kor_path,
        exists=exists,
        sidecar=sidecar,
    )


# ─── delete_by_sha ──────────────────────────────────────────────────


class TestDeleteBySha:
    @patch("filekor.core.status.get_directory_status")
    @patch("filekor.db.delete_file_by_hash")
    def test_scope_db_only(self, mock_db_delete, mock_status, tmp_path):
        """scope='db' only deletes DB records."""
        mock_db_delete.return_value = 1

        db_count, file_count = delete_by_sha("sha123", str(tmp_path), scope="db")

        assert db_count == 1
        assert file_count == 0
        mock_db_delete.assert_called_once_with("sha123")
        mock_status.assert_not_called()

    @patch("filekor.core.status.get_directory_status")
    @patch("filekor.db.delete_file_by_hash")
    def test_scope_file_only(self, mock_db_delete, mock_status, tmp_path):
        """scope='file' only deletes .kor files."""
        kor_path = tmp_path / ".filekor" / "doc.txt.kor"
        kor_path.parent.mkdir(parents=True, exist_ok=True)
        kor_path.write_text("dummy")

        fs = _make_file_status(tmp_path, "doc.txt", sha="sha123")
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=1,
            kor_files=1,
            files_without_kor=[],
            file_statuses=[fs],
        )

        with patch.object(Path, "unlink") as mock_unlink:
            db_count, file_count = delete_by_sha("sha123", str(tmp_path), scope="file")

        assert db_count == 0
        assert file_count == 1
        mock_db_delete.assert_not_called()
        mock_unlink.assert_called_once()

    @patch("filekor.core.status.get_directory_status")
    @patch("filekor.db.delete_file_by_hash")
    def test_scope_all(self, mock_db_delete, mock_status, tmp_path):
        """scope='all' deletes both DB and files."""
        mock_db_delete.return_value = 1

        fs = _make_file_status(tmp_path, "doc.txt", sha="sha123")
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=1,
            kor_files=1,
            files_without_kor=[],
            file_statuses=[fs],
        )

        with patch.object(Path, "unlink") as mock_unlink:
            db_count, file_count = delete_by_sha("sha123", str(tmp_path), scope="all")

        assert db_count == 1
        assert file_count == 1

    @patch("filekor.core.status.get_directory_status")
    def test_no_matching_files(self, mock_status, tmp_path):
        """No files match the SHA — nothing deleted."""
        fs = _make_file_status(tmp_path, "other.txt", sha="different_sha")
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=1,
            kor_files=1,
            files_without_kor=[],
            file_statuses=[fs],
        )

        db_count, file_count = delete_by_sha("sha123", str(tmp_path), scope="file")

        assert db_count == 0
        assert file_count == 0

    @patch("filekor.core.status.get_directory_status")
    def test_file_without_sidecar_skipped(self, mock_status, tmp_path):
        """FileStatus with sidecar=None is skipped."""
        fs = _make_file_status(tmp_path, "no_kor.txt", sha="sha123", exists=False)
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=1,
            kor_files=0,
            files_without_kor=[tmp_path / "no_kor.txt"],
            file_statuses=[fs],
        )

        db_count, file_count = delete_by_sha("sha123", str(tmp_path), scope="file")

        assert file_count == 0

    @patch("filekor.db.delete_file_by_hash")
    def test_db_exception_handled(self, mock_db_delete, tmp_path):
        """DB delete exception returns 0, doesn't crash."""
        mock_db_delete.side_effect = Exception("DB error")

        db_count, file_count = delete_by_sha("sha123", str(tmp_path), scope="db")

        assert db_count == 0

    @patch("filekor.core.status.get_directory_status")
    def test_verbose_prints(self, mock_status, tmp_path):
        """verbose=True prints output."""
        fs = _make_file_status(tmp_path, "doc.txt", sha="sha123")
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=1,
            kor_files=1,
            files_without_kor=[],
            file_statuses=[fs],
        )

        with patch.object(Path, "unlink"):
            with patch("builtins.print") as mock_print:
                delete_by_sha("sha123", str(tmp_path), scope="file", verbose=True)

        mock_print.assert_called()


# ─── delete_by_path ─────────────────────────────────────────────────


class TestDeleteByPath:
    @patch("filekor.core.hasher.calculate_sha256")
    @patch("filekor.core.status.get_directory_status")
    @patch("filekor.db.delete_file_by_hash")
    def test_delegates_to_delete_by_sha(
        self, mock_db_del, mock_status, mock_sha, tmp_path
    ):
        """delete_by_path calculates SHA and delegates."""
        mock_sha.return_value = "computed_sha"
        mock_db_del.return_value = 1

        fs = _make_file_status(tmp_path, "doc.txt", sha="computed_sha")
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=1,
            kor_files=1,
            files_without_kor=[],
            file_statuses=[fs],
        )

        with patch.object(Path, "unlink"):
            db_count, file_count = delete_by_path(
                str(tmp_path / "doc.txt"), str(tmp_path)
            )

        mock_sha.assert_called_once_with(str(tmp_path / "doc.txt"))
        assert db_count == 1
        assert file_count == 1


# ─── delete_by_input ────────────────────────────────────────────────


class TestDeleteByInput:
    @patch("filekor.core.status.get_directory_status")
    @patch("filekor.db.delete_file_by_hash")
    def test_batch_from_file(self, mock_db_del, mock_status, tmp_path):
        """Reads SHA hashes from input file and deletes each."""
        mock_db_del.return_value = 1

        input_file = tmp_path / "hashes.txt"
        input_file.write_text("sha_a\nsha_b\n")

        fs = _make_file_status(tmp_path, "doc.txt", sha="sha_a")
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=1,
            kor_files=1,
            files_without_kor=[],
            file_statuses=[fs],
        )

        with patch.object(Path, "unlink"):
            db_count, file_count = delete_by_input(str(input_file), str(tmp_path))

        assert db_count == 2  # 2 hashes processed
        assert file_count == 1  # only sha_a matched

    @patch("filekor.db.delete_file_by_hash")
    def test_skips_comments_and_empty_lines(self, mock_db_del, tmp_path):
        """Lines starting with # and empty lines are skipped."""
        mock_db_del.return_value = 0

        input_file = tmp_path / "hashes.txt"
        input_file.write_text("# comment\n\nsha_only\n  \n")

        db_count, file_count = delete_by_input(
            str(input_file), str(tmp_path), scope="db"
        )

        # Only "sha_only" should be processed (1 call)
        assert mock_db_del.call_count == 1

    def test_file_not_found_raises(self, tmp_path):
        """Input file doesn't exist raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Input file not found"):
            delete_by_input(str(tmp_path / "nonexistent.txt"))

    @patch("filekor.db.delete_file_by_hash")
    def test_empty_file(self, mock_db_del, tmp_path):
        """Empty input file processes 0 hashes."""
        input_file = tmp_path / "empty.txt"
        input_file.write_text("")

        db_count, file_count = delete_by_input(
            str(input_file), str(tmp_path), scope="db"
        )

        assert db_count == 0
        mock_db_del.assert_not_called()


# ─── get_deletion_preview ───────────────────────────────────────────


class TestGetDeletionPreview:
    @patch("filekor.db.get_file_by_hash")
    def test_preview_db_record(self, mock_get_by_hash, tmp_path):
        """Hash exists in DB — included in preview."""
        mock_get_by_hash.return_value = {"hash_sha256": "sha123"}

        db_hashes, files = get_deletion_preview("sha123", str(tmp_path))

        assert "sha123" in db_hashes

    @patch("filekor.db.get_file_by_hash")
    def test_preview_no_db_record(self, mock_get_by_hash, tmp_path):
        """Hash not in DB — empty db_hashes."""
        mock_get_by_hash.return_value = None

        db_hashes, files = get_deletion_preview("sha123", str(tmp_path))

        assert db_hashes == []

    @patch("filekor.core.status.get_directory_status")
    @patch("filekor.db.get_file_by_hash")
    def test_preview_matching_files(self, mock_get_by_hash, mock_status, tmp_path):
        """Files matching SHA are included in preview."""
        mock_get_by_hash.return_value = None

        fs = _make_file_status(tmp_path, "doc.txt", sha="sha123")
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=1,
            kor_files=1,
            files_without_kor=[],
            file_statuses=[fs],
        )

        db_hashes, files = get_deletion_preview("sha123", str(tmp_path))

        assert len(files) == 1
        assert files[0][0] == "doc.txt"  # name
        assert ".filekor" in files[0][1]  # kor path

    @patch("filekor.core.status.get_directory_status")
    @patch("filekor.db.get_file_by_hash")
    def test_preview_nothing_matches(self, mock_get_by_hash, mock_status, tmp_path):
        """No DB record and no files match — empty preview."""
        mock_get_by_hash.return_value = None
        mock_status.return_value = DirectoryStatus(
            directory=tmp_path,
            total_files=0,
            kor_files=0,
            files_without_kor=[],
            file_statuses=[],
        )

        db_hashes, files = get_deletion_preview("sha_unknown", str(tmp_path))

        assert db_hashes == []
        assert files == []

    @patch("filekor.db.get_file_by_hash")
    def test_preview_db_exception_handled(self, mock_get_by_hash, tmp_path):
        """DB exception is caught, preview continues."""
        mock_get_by_hash.side_effect = Exception("DB down")

        db_hashes, files = get_deletion_preview("sha123", str(tmp_path))

        assert db_hashes == []
