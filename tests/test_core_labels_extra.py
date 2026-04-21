"""Extra tests for core/labels.py — get_config, reload_config, suggest_from_content success path."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import filekor.core.labels as labels_module
from filekor.core.labels import (
    LabelsConfig,
    LLMConfig,
    get_config,
    reload_config,
    suggest_from_content,
)


# ─── get_config / reload_config ─────────────────────────────────────


class TestConfigSingleton:
    def setup_method(self):
        """Reset singleton before each test."""
        labels_module._config = None

    def teardown_method(self):
        """Reset singleton after each test."""
        labels_module._config = None

    def test_get_config_loads_lazily(self):
        """get_config() loads config on first call."""
        config = get_config()
        assert isinstance(config, LabelsConfig)
        assert "finance" in config.synonyms

    def test_get_config_returns_same_instance(self):
        """Second call returns the cached instance."""
        first = get_config()
        second = get_config()
        assert first is second

    def test_reload_config_returns_new_instance(self):
        """reload_config() forces a fresh load."""
        first = get_config()
        second = reload_config()
        assert isinstance(second, LabelsConfig)
        assert second is not first
        assert labels_module._config is second

    def test_reload_config_with_custom_path(self, tmp_path):
        """reload_config() accepts a custom path."""
        props = tmp_path / "custom.properties"
        props.write_text("custom_label=syn1,syn2\n", encoding="utf-8")

        config = reload_config(str(props))

        assert "custom_label" in config.synonyms
        assert "syn1" in config.synonyms["custom_label"]


# ─── suggest_from_content success path ──────────────────────────────


class TestSuggestFromContentSuccess:
    def test_success_with_mock_provider(self):
        """suggest_from_content returns labels when provider succeeds."""
        mock_provider = Mock()
        mock_provider.extract_labels.return_value = ["finance", "legal"]

        llm_config = LLMConfig(enabled=True, api_key="test", provider="mock")

        with patch("filekor.core.labels.get_provider", return_value=mock_provider):
            result = suggest_from_content(
                "Some financial legal content",
                llm_config=llm_config,
            )

        assert result == ["finance", "legal"]
        mock_provider.extract_labels.assert_called_once()

    def test_taxonomy_passed_to_provider(self):
        """Taxonomy from LabelsConfig is passed to extract_labels."""
        mock_provider = Mock()
        mock_provider.extract_labels.return_value = ["x"]

        config = LabelsConfig(synonyms={"tech": ["software", "hardware"]})
        llm_config = LLMConfig(enabled=True, api_key="test", provider="mock")

        with patch("filekor.core.labels.get_provider", return_value=mock_provider):
            suggest_from_content("content", config=config, llm_config=llm_config)

        call_args = mock_provider.extract_labels.call_args
        assert call_args[0][1] == {"tech": ["software", "hardware"]}

    def test_config_loaded_when_none(self):
        """config=None triggers get_config() call."""
        llm_config = LLMConfig(enabled=True, api_key="test", provider="mock")

        mock_provider = Mock()
        mock_provider.extract_labels.return_value = []

        with patch("filekor.core.labels.get_provider", return_value=mock_provider):
            with patch("filekor.core.labels.get_config") as mock_gc:
                mock_gc.return_value = LabelsConfig(synonyms={"test": ["a"]})
                suggest_from_content("text", config=None, llm_config=llm_config)

        mock_gc.assert_called_once()

    def test_llm_config_loaded_when_none(self):
        """llm_config=None triggers LLMConfig.load() call."""
        mock_provider = Mock()
        mock_provider.extract_labels.return_value = []

        with patch("filekor.core.labels.get_provider", return_value=mock_provider):
            with patch("filekor.core.labels.LLMConfig.load") as mock_load:
                mock_load.return_value = LLMConfig(
                    enabled=True, api_key="x", provider="mock"
                )
                suggest_from_content("text")

        mock_load.assert_called_once()

    def test_truncates_long_content(self, tmp_path):
        """Content is truncated to max_content_chars before passing to provider."""
        mock_provider = Mock()
        mock_provider.extract_labels.return_value = []

        llm_config = LLMConfig(
            enabled=True,
            api_key="test",
            provider="mock",
            max_content_chars=10,
        )

        with patch("filekor.core.labels.get_provider", return_value=mock_provider):
            suggest_from_content("A" * 100, llm_config=llm_config)

        call_args = mock_provider.extract_labels.call_args
        content_passed = call_args[0][0]
        assert content_passed == "A" * 10
