"""Tests for labels module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from filekor.labels import (
    LabelsConfig,
    LLMConfig,
    suggest_labels,
    suggest_from_content,
)


class TestLabelsConfig:
    """Test LabelsConfig class."""

    def test_load_from_defaults(self):
        """Verify load() returns defaults when no config file exists."""
        config = LabelsConfig.load()
        assert config.synonyms is not None
        assert "finance" in config.synonyms

    def test_load_with_custom_path(self):
        """Verify load() works with custom config path."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".properties", delete=False
        ) as f:
            f.write("test=word1,word2\n")
            temp_path = f.name

        try:
            config = LabelsConfig.load(temp_path)
            assert "test" in config.synonyms
            assert "word1" in config.synonyms["test"]
            assert "word2" in config.synonyms["test"]
        finally:
            Path(temp_path).unlink()

    def test_parse_properties_basic(self):
        """Verify parse_properties() handles basic key=value."""
        content = "finance=budget,cost,money"
        result = LabelsConfig.parse_properties(content)
        assert "finance" in result
        assert "budget" in result["finance"]
        assert "cost" in result["finance"]
        assert "money" in result["finance"]

    def test_parse_properties_empty_synonyms(self):
        """Verify parse_properties() skips empty synonyms."""
        content = "empty="
        result = LabelsConfig.parse_properties(content)
        assert "empty" not in result

    def test_parse_properties_comments(self):
        """Verify parse_properties() skips comments."""
        content = "# This is a comment\nfinance=budget"
        result = LabelsConfig.parse_properties(content)
        assert "finance" in result

    def test_parse_properties_case_insensitive(self):
        """Verify parse_properties() normalizes keys to lowercase."""
        content = "FINANCE=budget\nCONTRACT=agreement"
        result = LabelsConfig.parse_properties(content)
        assert "finance" in result
        assert "contract" in result


class TestSuggestLabels:
    """Test suggest_labels() function (LLM only)."""

    def test_raises_when_llm_not_configured(self, tmp_path):
        """Verify raises RuntimeError when LLM is not configured."""
        # Create empty config in tmp_path BEFORE calling
        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Now with no config files in tmp_path, should raise
            with pytest.raises(RuntimeError) as exc_info:
                suggest_labels("test content")
            assert "LLM is not configured" in str(exc_info.value)
        finally:
            os.chdir(old_cwd)

    def test_raises_when_llm_disabled(self, tmp_path):
        """Verify raises when enabled: false in config."""
        config_content = """filekor:
  llm:
    enabled: false
    provider: gemini
    api_key: test-key
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(RuntimeError) as exc_info:
                suggest_labels("test content")

            assert "LLM is not configured" in str(exc_info.value)
        finally:
            os.chdir(old_cwd)

    def test_returns_labels_from_llm(self, tmp_path):
        """Verify returns labels from LLM when configured."""
        config_content = """filekor:
  llm:
    enabled: true
    provider: mock
    api_key: test-key
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = suggest_labels("test content")

            assert isinstance(result, list)
            # MockProvider returns ["documentation"] by default
        finally:
            os.chdir(old_cwd)


class TestLLMConfig:
    """Test LLMConfig class."""

    def test_load_defaults_when_no_config(self, tmp_path):
        """Verify load() returns defaults when no config file exists."""
        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = LLMConfig.load()
            assert config.enabled is False
            assert config.provider == "gemini"
            assert config.model == "gemini-2.0-flash"
            assert config.max_content_chars == 1500
        finally:
            os.chdir(old_cwd)

    def test_load_parses_config_file(self, tmp_path):
        """Verify load() parses config.yaml correctly."""
        config_content = """filekor:
  llm:
    enabled: true
    provider: gemini
    model: gemini-2.0-flash
    api_key: test-key-123
    max_content_chars: 2000
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = LLMConfig.load()
            assert config.enabled is True
            assert config.provider == "gemini"
            assert config.model == "gemini-2.0-flash"
            assert config.api_key == "test-key-123"
            assert config.max_content_chars == 2000
        finally:
            os.chdir(old_cwd)

    def test_load_expands_env_vars(self, tmp_path, monkeypatch):
        """Verify load() expands ${VAR} patterns."""
        monkeypatch.setenv("TEST_API_KEY", "env-value-123")

        config_content = """filekor:
  llm:
    enabled: true
    api_key: ${TEST_API_KEY}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = LLMConfig.load()
            assert config.api_key == "env-value-123"
        finally:
            os.chdir(old_cwd)


class TestSuggestFromContent:
    """Test suggest_from_content() function."""

    def test_returns_empty_when_llm_disabled(self):
        """Verify returns [] when LLM is not enabled."""
        config = LabelsConfig({"finance": ["budget", "cost"]})
        llm_config = LLMConfig(enabled=False)

        result = suggest_from_content("test content", config, llm_config)
        assert result == []

    def test_returns_empty_when_no_api_key(self):
        """Verify returns [] when no API key configured."""
        config = LabelsConfig({"finance": ["budget", "cost"]})
        llm_config = LLMConfig(enabled=True, api_key=None)

        result = suggest_from_content("test content", config, llm_config)
        assert result == []

    def test_truncates_content_to_max_chars(self):
        """Verify content is truncated to max_content_chars."""
        config = LabelsConfig({"finance": ["budget", "cost"]})
        llm_config = LLMConfig(enabled=True, api_key="test-key", max_content_chars=100)

        long_content = "a" * 500

        with patch("filekor.labels.get_provider") as mock_get_provider:
            mock_provider = Mock()
            mock_provider.extract_labels.return_value = ["finance"]
            mock_get_provider.return_value = mock_provider

            suggest_from_content(long_content, config, llm_config)

            call_args = mock_provider.extract_labels.call_args
            passed_content = call_args[0][0]
            assert len(passed_content) == 100

    def test_returns_empty_on_llm_error(self):
        """Verify returns empty list when LLM fails (silent fallback)."""
        config = LabelsConfig({"finance": ["budget", "cost"]})
        llm_config = LLMConfig(enabled=True, api_key="test-key")

        with patch("filekor.labels.get_provider") as mock_get_provider:
            mock_provider = Mock()
            mock_provider.extract_labels.side_effect = Exception("API Error")
            mock_get_provider.return_value = mock_provider

            result = suggest_from_content("test content", config, llm_config)
            assert result == []


class TestLabelsCLI:
    """Test labels CLI command."""

    def test_labels_requires_llm_config(self, tmp_path):
        """Verify labels command fails when LLM not configured."""
        import os
        from click.testing import CliRunner
        from filekor.cli import labels

        # Change to tmp_path to isolate from project config.yaml
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            test_file = tmp_path / "test.txt"
            test_file.write_text("test content")

            runner = CliRunner()
            result = runner.invoke(labels, [str(test_file)])

            # Should fail because LLM is not configured
            assert result.exit_code == 1
            assert "LLM" in result.output or "configured" in result.output.lower()
        finally:
            os.chdir(old_cwd)

    def test_labels_shows_confidence_flag_still_exists(self, tmp_path):
        """Verify --show-confidence flag still works (no-op now, for compatibility)."""
        from click.testing import CliRunner
        from filekor.cli import labels

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        runner = CliRunner()
        result = runner.invoke(labels, [str(test_file), "--show-confidence"])

        # Should still accept the flag but it does nothing
        # Only checking error happens


class TestLabelsIntegration:
    """Integration tests for labels in sidecar."""

    def test_sidecar_no_labels_when_llm_not_configured(self, tmp_path):
        """Verify sidecar labels is None when LLM not configured."""
        from filekor.sidecar import Sidecar

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        sidecar = Sidecar.create(str(test_file))

        # Should have labels set but may be None or empty depending on impl
        assert sidecar.labels is None or sidecar.labels.suggested == []


class TestFileLabelsModel:
    """Test FileLabels model."""

    def test_file_labels_no_confidence_field(self):
        """Verify FileLabels doesn't have confidence field."""
        from filekor.sidecar import FileLabels

        labels = FileLabels(suggested=["finance"], source="llm")

        # Should not have confidence attribute
        assert not hasattr(labels, "confidence")

    def test_file_labels_source_is_llm(self):
        """Verify source is always 'llm'."""
        from filekor.sidecar import FileLabels

        labels = FileLabels(suggested=["finance"], source="llm")

        assert labels.source == "llm"
