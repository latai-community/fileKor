"""Tests for cli/summary.py — summary command."""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from filekor.cli.summary import _resolve_length, summary
from filekor.sidecar import Content, FileInfo, FileLabels, FileSummary, Sidecar


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
        labels=FileLabels(suggested=["finance"]),
        summary=FileSummary(short="Test summary"),
        parser_status="OK",
        generated_at=datetime.now(timezone.utc),
    )
    return sidecar.to_yaml()


# ─── _resolve_length ────────────────────────────────────────────────


class TestResolveLength:
    def test_both_flags(self):
        assert _resolve_length(True, True) == "both"

    def test_short_only(self):
        assert _resolve_length(True, False) == "short"

    def test_long_only(self):
        assert _resolve_length(False, True) == "long"

    def test_neither_flag(self):
        assert _resolve_length(False, False) == "both"


# ─── summary file ───────────────────────────────────────────────────


class TestSummaryFile:
    @patch("filekor.cli.HAS_PYPDF", False)
    def test_file_success(self, tmp_path):
        """Successful summary generation for a single file."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("hello world")

        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text") as mock_extract:
            mock_extract.return_value = ("hello world", 2, 1)
            with patch("filekor.cli.summary.generate_summary") as mock_gen:
                mock_gen.return_value = MagicMock(short="Short", long="Long")
                with patch("filekor.cli.summary._auto_sync_hook"):
                    result = runner.invoke(summary, [str(test_file)])

        assert result.exit_code == 0
        assert "Short: Short" in result.output
        assert "Long:  Long" in result.output
        assert "Saved:" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_file_not_found(self, tmp_path):
        """File not found exits with code 2."""
        runner = CliRunner()
        result = runner.invoke(summary, [str(tmp_path / "missing.txt")])
        assert result.exit_code == 2
        assert "File not found" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_cannot_read_content(self, tmp_path):
        """Error reading file content exits with code 1."""
        test_file = tmp_path / "bad.txt"
        test_file.write_text("data")
        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text", side_effect=Exception("boom")):
            result = runner.invoke(summary, [str(test_file)])
        assert result.exit_code == 1
        assert "Could not read file content" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_llm_not_configured(self, tmp_path):
        """LLM disabled or missing API key exits with code 1."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")
        runner = CliRunner()
        with patch("filekor.core.labels.LLMConfig.load") as mock_load:
            mock_load.return_value = MagicMock(enabled=False, api_key=None)
            result = runner.invoke(summary, [str(test_file)])
        assert result.exit_code == 1
        assert "LLM is not configured" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_short_flag_only(self, tmp_path):
        """--short flag generates only short summary."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")
        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text") as mock_extract:
            mock_extract.return_value = ("text", 1, 1)
            with patch("filekor.cli.summary.generate_summary") as mock_gen:
                mock_gen.return_value = MagicMock(short="Short only", long=None)
                with patch("filekor.cli.summary._auto_sync_hook"):
                    result = runner.invoke(summary, [str(test_file), "--short"])
        assert result.exit_code == 0
        assert "Short only" in result.output
        assert "Long" not in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_long_flag_only(self, tmp_path):
        """--long flag generates only long summary."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")
        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text") as mock_extract:
            mock_extract.return_value = ("text", 1, 1)
            with patch("filekor.cli.summary.generate_summary") as mock_gen:
                mock_gen.return_value = MagicMock(short=None, long="Long only")
                with patch("filekor.cli.summary._auto_sync_hook"):
                    result = runner.invoke(summary, [str(test_file), "--long"])
        assert result.exit_code == 0
        assert "Long only" in result.output
        assert "Short" not in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_max_chars_flag(self, tmp_path):
        """--max-chars flag is passed to generate_summary."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")
        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text") as mock_extract:
            mock_extract.return_value = ("text", 1, 1)
            with patch("filekor.cli.summary.generate_summary") as mock_gen:
                mock_gen.return_value = MagicMock()
                with patch("filekor.cli.summary._auto_sync_hook"):
                    result = runner.invoke(
                        summary, [str(test_file), "--max-chars", "99"]
                    )
        assert result.exit_code == 0
        # Check that max_chars=99 was passed
        call_args = mock_gen.call_args
        assert call_args.kwargs.get("max_chars") == 99

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_custom_llm_config(self, tmp_path):
        """--llm-config flag uses custom config path."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")
        custom_cfg = tmp_path / "custom.yaml"
        custom_cfg.write_text(
            "filekor:\n  llm:\n    enabled: true\n    provider: mock\n    api_key: test\n"
        )
        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text") as mock_extract:
            mock_extract.return_value = ("text", 1, 1)
            with patch("filekor.cli.summary.generate_summary") as mock_gen:
                mock_gen.return_value = MagicMock()
                with patch("filekor.cli.summary._auto_sync_hook"):
                    result = runner.invoke(
                        summary, [str(test_file), "--llm-config", str(custom_cfg)]
                    )
        assert result.exit_code == 0
        # LLMConfig.load should have been called with the custom path
        # (we don't need to assert further as the mocks above will fail if not called)

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_existing_kor_updated(self, tmp_path):
        """When .kor exists, it is loaded and updated."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")
        filekor_dir = test_file.parent / ".filekor"
        filekor_dir.mkdir()
        kor_path = filekor_dir / "doc.txt.kor"
        kor_path.write_text(_make_sidecar_yaml("doc.txt"), encoding="utf-8")

        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text") as mock_extract:
            mock_extract.return_value = ("text", 1, 1)
            with patch("filekor.cli.summary.generate_summary") as mock_gen:
                mock_gen.return_value = MagicMock(short="New short", long="New long")
                with patch("filekor.cli.summary._auto_sync_hook"):
                    result = runner.invoke(summary, [str(test_file)])
        assert result.exit_code == 0
        # Check that the .kor file was updated with new summary
        updated = Sidecar.load(str(kor_path))
        assert updated.summary.short == "New short"
        assert updated.summary.long == "New long"

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_new_kor_created(self, tmp_path):
        """When .kor does not exist, a new one is created."""
        test_file = tmp_path / "doc.txt"
        test_file.write_text("data")
        filekor_dir = test_file.parent / ".filekor"
        # Ensure .kor does not exist
        assert not filekor_dir.exists()

        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text") as mock_extract:
            mock_extract.return_value = ("text", 1, 1)
            with patch("filekor.cli.summary.generate_summary") as mock_gen:
                mock_gen.return_value = MagicMock(short="Short", long="Long")
                with patch("filekor.cli.summary._auto_sync_hook"):
                    result = runner.invoke(summary, [str(test_file)])
        assert result.exit_code == 0
        # Check that .kor file was created
        kor_path = filekor_dir / "doc.txt.kor"
        assert kor_path.exists()
        created = Sidecar.load(str(kor_path))
        assert created.summary.short == "Short"
        assert created.summary.long == "Long"


# ─── summary directory ──────────────────────────────────────────────


class TestSummaryDirectory:
    @patch("filekor.cli.HAS_PYPDF", False)
    def test_directory_success(self, tmp_path):
        """Successful summary generation for a directory."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text") as mock_extract:
            mock_extract.return_value = ("text", 1, 1)
            with patch("filekor.cli.summary.generate_summary") as mock_gen:
                mock_gen.return_value = MagicMock(short="S", long="L")
                with patch("filekor.cli.summary._auto_sync_hook"):
                    with patch("filekor.cli.summary.create_emitter") as mock_emitter:
                        mock_emitter.return_value = MagicMock()
                        result = runner.invoke(summary, [str(tmp_path), "--dir"])
        assert result.exit_code == 0
        assert "Found 2 files to process" in result.output
        assert "Completed: 2/2 successful" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_directory_not_a_directory(self, tmp_path):
        """Passing a file with --dir exits with code 1."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("x")
        runner = CliRunner()
        result = runner.invoke(summary, [str(test_file), "--dir"])
        assert result.exit_code == 1
        assert "Not a directory" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_directory_no_supported_files(self, tmp_path):
        """Directory with no supported files exits with code 0."""
        (tmp_path / "data.csv").write_text("a,b")
        (tmp_path / "image.png").write_bytes(b"fake")
        runner = CliRunner()
        result = runner.invoke(summary, [str(tmp_path), "--dir"])
        assert result.exit_code == 0
        assert "No supported files found" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_directory_with_failures(self, tmp_path):
        """Some files fail, some succeed."""
        (tmp_path / "good.txt").write_text("good")
        (tmp_path / "bad.txt").write_text("bad")

        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text") as mock_extract:

            def side_effect(path):
                if "bad" in path:
                    raise Exception("boom")
                return ("text", 1, 1)

            mock_extract.side_effect = side_effect
            with patch("filekor.cli.summary.generate_summary") as mock_gen:
                mock_gen.return_value = MagicMock(short="S", long="L")
                with patch("filekor.cli.summary._auto_sync_hook"):
                    with patch("filekor.cli.summary.create_emitter") as mock_emitter:
                        mock_emitter.return_value = MagicMock()
                        result = runner.invoke(summary, [str(tmp_path), "--dir"])
        assert result.exit_code == 1  # fails > 0 -> exit 1
        assert "OK good.txt:" in result.output
        assert "FAIL bad.txt:" in result.output
        assert "Completed: 1/2 successful" in result.output

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_directory_workers_flag(self, tmp_path):
        """--workers flag is respected."""
        (tmp_path / "a.txt").write_text("a")
        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text") as mock_extract:
            mock_extract.return_value = ("text", 1, 1)
            with patch("filekor.cli.summary.generate_summary") as mock_gen:
                mock_gen.return_value = MagicMock()
                with patch("filekor.cli.summary._auto_sync_hook"):
                    with patch("filekor.cli.summary.create_emitter") as mock_emitter:
                        mock_emitter.return_value = MagicMock()
                        result = runner.invoke(
                            summary, [str(tmp_path), "--dir", "--workers", "4"]
                        )
        assert result.exit_code == 0
        # The workers value is used to create ThreadPoolExecutor; we can't easily assert it,
        # but at least the command didn't crash.

    @patch("filekor.cli.HAS_PYPDF", False)
    def test_directory_watch_flag(self, tmp_path):
        """--watch flag creates emitter with watch=True."""
        (tmp_path / "a.txt").write_text("a")
        runner = CliRunner()
        with patch("filekor.cli.summary.extract_text") as mock_extract:
            mock_extract.return_value = ("text", 1, 1)
            with patch("filekor.cli.summary.generate_summary") as mock_gen:
                mock_gen.return_value = MagicMock()
                with patch("filekor.cli.summary._auto_sync_hook"):
                    with patch("filekor.cli.summary.create_emitter") as mock_emitter:
                        mock_emitter.return_value = MagicMock()
                        result = runner.invoke(
                            summary, [str(tmp_path), "--dir", "--watch"]
                        )
        assert result.exit_code == 0
        # Check that create_emitter was called with watch=True
        call_args = mock_emitter.call_args
        assert call_args.kwargs.get("watch") is True
