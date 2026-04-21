"""Tests for core/merge.py — merge_kor_files, load_merged_kor."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from filekor.core.merge import merge_kor_files, load_merged_kor
from filekor.sidecar import Content, FileInfo, FileLabels, Sidecar


def _make_sidecar(name: str = "doc.txt", sha: str = "abc123") -> Sidecar:
    """Create a minimal valid Sidecar."""
    return Sidecar(
        file=FileInfo(
            path=name,
            name=name,
            extension="txt",
            size_bytes=42,
            modified_at=datetime.now(timezone.utc),
            hash_sha256=sha,
        ),
        content=Content(language="en", word_count=5, page_count=1),
        labels=FileLabels(suggested=["test"]),
        parser_status="OK",
        generated_at=datetime.now(timezone.utc),
    )


def _write_sidecar(kor_path: Path, sidecar: Sidecar) -> None:
    """Write a Sidecar as YAML .kor file."""
    kor_path.parent.mkdir(parents=True, exist_ok=True)
    kor_path.write_text(sidecar.to_yaml(), encoding="utf-8")


# ─── merge_kor_files ────────────────────────────────────────────────


class TestMergeKorFiles:
    def test_no_filekor_directory_raises(self, tmp_path):
        """No .filekor/ directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match=".filekor directory not found"):
            merge_kor_files(str(tmp_path))

    def test_empty_filekor_returns_empty(self, tmp_path):
        """.filekor/ exists but has no .kor files — returns []."""
        (tmp_path / ".filekor").mkdir()

        result = merge_kor_files(str(tmp_path))

        assert result == []

    def test_merge_creates_merged_kor(self, tmp_path):
        """Merges multiple .kor files into merged.kor."""
        filekor_dir = tmp_path / ".filekor"
        _write_sidecar(filekor_dir / "a.txt.kor", _make_sidecar("a.txt", "sha_a"))
        _write_sidecar(filekor_dir / "b.txt.kor", _make_sidecar("b.txt", "sha_b"))

        result = merge_kor_files(str(tmp_path), delete_sources=False)

        assert len(result) == 2
        merged_path = filekor_dir / "merged.kor"
        assert merged_path.exists()

        # Verify multi-doc YAML
        content = merged_path.read_text()
        docs = list(yaml.safe_load_all(content))
        assert len(docs) == 2

    def test_delete_sources_removes_originals(self, tmp_path):
        """delete_sources=True removes original .kor files."""
        filekor_dir = tmp_path / ".filekor"
        kor_a = filekor_dir / "a.txt.kor"
        kor_b = filekor_dir / "b.txt.kor"
        _write_sidecar(kor_a, _make_sidecar("a.txt", "sha_a"))
        _write_sidecar(kor_b, _make_sidecar("b.txt", "sha_b"))

        merge_kor_files(str(tmp_path), delete_sources=True)

        assert not kor_a.exists()
        assert not kor_b.exists()
        assert (filekor_dir / "merged.kor").exists()

    def test_delete_sources_false_keeps_originals(self, tmp_path):
        """delete_sources=False keeps original .kor files."""
        filekor_dir = tmp_path / ".filekor"
        kor_a = filekor_dir / "a.txt.kor"
        _write_sidecar(kor_a, _make_sidecar("a.txt", "sha_a"))

        merge_kor_files(str(tmp_path), delete_sources=False)

        assert kor_a.exists()
        assert (filekor_dir / "merged.kor").exists()

    def test_custom_output_path(self, tmp_path):
        """output_path writes to a custom location."""
        filekor_dir = tmp_path / ".filekor"
        _write_sidecar(filekor_dir / "a.txt.kor", _make_sidecar("a.txt", "sha_a"))

        custom_out = tmp_path / "custom" / "merged.kor"
        result = merge_kor_files(
            str(tmp_path), output_path=str(custom_out), delete_sources=False
        )

        assert custom_out.exists()
        assert len(result) == 1

    def test_corrupted_kor_skipped(self, tmp_path):
        """Corrupted .kor file is silently skipped during merge."""
        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir(parents=True)
        (filekor_dir / "bad.kor").write_text("{{invalid: yaml: [[[")
        _write_sidecar(filekor_dir / "good.txt.kor", _make_sidecar("good.txt", "sha_g"))

        result = merge_kor_files(str(tmp_path), delete_sources=False)

        assert len(result) == 1
        assert result[0].file.name == "good.txt"

    def test_all_corrupted_returns_empty(self, tmp_path):
        """All .kor files corrupted — returns []."""
        filekor_dir = tmp_path / ".filekor"
        filekor_dir.mkdir(parents=True)
        (filekor_dir / "bad1.kor").write_text("{{not yaml")
        (filekor_dir / "bad2.kor").write_text("also bad: [[[")

        result = merge_kor_files(str(tmp_path), delete_sources=False)

        assert result == []

    def test_unlink_error_continues_merge(self, tmp_path):
        """PermissionError on unlink is caught, merge still completes."""
        filekor_dir = tmp_path / ".filekor"
        kor_a = filekor_dir / "a.txt.kor"
        kor_b = filekor_dir / "b.txt.kor"
        _write_sidecar(kor_a, _make_sidecar("a.txt", "sha_a"))
        _write_sidecar(kor_b, _make_sidecar("b.txt", "sha_b"))

        real_unlink = Path.unlink

        def stubborn_unlink(self):
            if self.name == "a.txt.kor":
                raise PermissionError("locked")
            real_unlink(self)

        with patch.object(Path, "unlink", stubborn_unlink):
            result = merge_kor_files(str(tmp_path), delete_sources=True)

        # Merge still returned both sidecars
        assert len(result) == 2
        # a.txt.kor still exists (unlink failed), b.txt.kor was deleted
        assert kor_a.exists()
        assert not kor_b.exists()
        # merged.kor was created
        assert (filekor_dir / "merged.kor").exists()


# ─── load_merged_kor ────────────────────────────────────────────────


class TestLoadMergedKor:
    def test_load_single_sidecar(self, tmp_path):
        """Load a merged.kor with a single document."""
        merged_path = tmp_path / "merged.kor"
        sidecar = _make_sidecar("doc.txt", "sha1")
        merged_path.write_text("---\n" + sidecar.to_yaml() + "\n", encoding="utf-8")

        result = load_merged_kor(str(merged_path))

        assert len(result) == 1
        assert result[0].file.name == "doc.txt"
        assert result[0].file.hash_sha256 == "sha1"

    def test_load_multiple_sidecars(self, tmp_path):
        """Load a merged.kor with multiple documents."""
        merged_path = tmp_path / "merged.kor"
        s1 = _make_sidecar("a.txt", "sha_a")
        s2 = _make_sidecar("b.txt", "sha_b")

        content = "---\n" + s1.to_yaml() + "\n---\n" + s2.to_yaml() + "\n"
        merged_path.write_text(content, encoding="utf-8")

        result = load_merged_kor(str(merged_path))

        assert len(result) == 2
        assert result[0].file.name == "a.txt"
        assert result[1].file.name == "b.txt"

    def test_file_not_found_raises(self, tmp_path):
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Merged .kor file not found"):
            load_merged_kor(str(tmp_path / "nope.kor"))

    def test_empty_document_skipped(self, tmp_path):
        """Empty YAML document between separators is skipped."""
        merged_path = tmp_path / "merged.kor"
        sidecar = _make_sidecar("doc.txt", "sha1")
        # YAML safe_load_all returns None for empty documents between ---
        content = (
            "---\n" + sidecar.to_yaml() + "\n---\n---\n" + sidecar.to_yaml() + "\n"
        )
        merged_path.write_text(content, encoding="utf-8")

        result = load_merged_kor(str(merged_path))

        # Empty doc between the two sidecars is skipped (None filtered out)
        assert len(result) == 2

    def test_roundtrip_merge_and_load(self, tmp_path):
        """Write with merge_kor_files, load with load_merged_kor."""
        filekor_dir = tmp_path / ".filekor"
        _write_sidecar(filekor_dir / "x.txt.kor", _make_sidecar("x.txt", "sha_x"))
        _write_sidecar(filekor_dir / "y.txt.kor", _make_sidecar("y.txt", "sha_y"))

        merged_sidecars = merge_kor_files(str(tmp_path), delete_sources=True)
        assert len(merged_sidecars) == 2

        loaded = load_merged_kor(str(filekor_dir / "merged.kor"))
        assert len(loaded) == 2
        names = {s.file.name for s in loaded}
        assert names == {"x.txt", "y.txt"}
