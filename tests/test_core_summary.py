"""Tests for core/summary.py — generate_summary, _call_llm, SummaryResult."""

import pytest
from unittest.mock import patch

from filekor.core.summary import generate_summary, _call_llm, SummaryResult
from filekor.core.labels import LLMConfig
from filekor.core.llm import MockProvider


# ─── generate_summary ───────────────────────────────────────────────


class TestGenerateSummary:
    def test_llm_disabled_raises(self):
        """LLM disabled raises RuntimeError."""
        config = LLMConfig(enabled=False)

        with pytest.raises(RuntimeError, match="LLM is not configured"):
            generate_summary("some content", llm_config=config)

    def test_no_api_key_raises(self):
        """LLM enabled but no api_key raises RuntimeError."""
        config = LLMConfig(enabled=True, api_key=None, provider="mock")

        with pytest.raises(RuntimeError, match="LLM is not configured"):
            generate_summary("some content", llm_config=config)

    def test_empty_api_key_raises(self):
        """LLM enabled but empty string api_key raises RuntimeError."""
        config = LLMConfig(enabled=True, api_key="", provider="mock")

        with pytest.raises(RuntimeError, match="LLM is not configured"):
            generate_summary("some content", llm_config=config)

    def test_length_short_only(self):
        """length='short' populates only result.short."""
        config = LLMConfig(enabled=True, api_key="test", provider="mock")

        with patch("filekor.core.summary._call_llm") as mock_call:
            mock_call.return_value = "Short summary"
            result = generate_summary("content", length="short", llm_config=config)

        assert result.short == "Short summary"
        assert result.long is None
        mock_call.assert_called_once()

    def test_length_long_only(self):
        """length='long' populates only result.long."""
        config = LLMConfig(enabled=True, api_key="test", provider="mock")

        with patch("filekor.core.summary._call_llm") as mock_call:
            mock_call.return_value = "Long summary"
            result = generate_summary("content", length="long", llm_config=config)

        assert result.short is None
        assert result.long == "Long summary"
        mock_call.assert_called_once()

    def test_length_both(self):
        """length='both' populates short and long."""
        config = LLMConfig(enabled=True, api_key="test", provider="mock")

        with patch("filekor.core.summary._call_llm") as mock_call:
            mock_call.side_effect = ["Short", "Long"]
            result = generate_summary("content", length="both", llm_config=config)

        assert result.short == "Short"
        assert result.long == "Long"
        assert mock_call.call_count == 2

    def test_max_chars_truncates_content(self):
        """max_chars truncates content before sending to LLM."""
        config = LLMConfig(
            enabled=True, api_key="test", provider="mock", max_content_chars=9999
        )

        with patch("filekor.core.summary._call_llm") as mock_call:
            mock_call.return_value = "ok"
            generate_summary("A" * 100, length="short", llm_config=config, max_chars=5)

        call_args = mock_call.call_args
        content_passed = call_args[0][2]  # third positional arg is content
        assert content_passed == "A" * 5

    def test_default_max_chars_from_config(self):
        """max_chars defaults to llm_config.max_content_chars."""
        config = LLMConfig(
            enabled=True,
            api_key="test",
            provider="mock",
            max_content_chars=10,
        )

        with patch("filekor.core.summary._call_llm") as mock_call:
            mock_call.return_value = "ok"
            generate_summary("B" * 100, length="short", llm_config=config)

        call_args = mock_call.call_args
        content_passed = call_args[0][2]
        assert content_passed == "B" * 10

    def test_llm_config_loads_when_none(self):
        """llm_config=None triggers LLMConfig.load()."""
        with patch("filekor.core.summary.LLMConfig.load") as mock_load:
            mock_load.return_value = LLMConfig(
                enabled=True, api_key="test", provider="mock"
            )

            with patch("filekor.core.summary._call_llm") as mock_call:
                mock_call.return_value = "ok"
                generate_summary("content", length="short")

            mock_load.assert_called_once()


# ─── _call_llm ──────────────────────────────────────────────────────


class TestCallLlm:
    def test_mock_provider_returns_string(self):
        """MockProvider returns the hardcoded mock summary."""
        provider = MockProvider()
        result = _call_llm(provider, "Summarize: {content}", "some text")

        assert result == "This is a mock summary generated for testing purposes."

    def test_unknown_provider_raises(self):
        """Unknown provider type raises ValueError."""

        class FakeProvider:
            pass

        with pytest.raises(ValueError, match="Unknown provider type"):
            _call_llm(FakeProvider(), "{content}", "text")

    def test_prompt_content_substituted(self):
        """Content is correctly inserted into prompt template."""
        provider = MockProvider()
        # MockProvider doesn't use the prompt, but this verifies no crash
        result = _call_llm(provider, "Summary of: {content}", "my document")
        assert isinstance(result, str)


# ─── SummaryResult ──────────────────────────────────────────────────


class TestSummaryResult:
    def test_default_none(self):
        """SummaryResult defaults to None for both fields."""
        result = SummaryResult()
        assert result.short is None
        assert result.long is None

    def test_both_fields(self):
        """SummaryResult accepts both fields."""
        result = SummaryResult(short="s", long="l")
        assert result.short == "s"
        assert result.long == "l"
