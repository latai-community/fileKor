"""Tests for LLM providers."""

import os
from unittest.mock import MagicMock, patch

import pytest

from filekor.core.llm import (
    GoogleProvider,
    GroqProvider,
    OpenAIProvider,
    OpenRouterProvider,
    MockProvider,
    get_provider,
)


class TestGoogleProvider:
    """Tests for Google Gemini provider."""

    def test_provider_initialization(self):
        """Test Google provider initializes correctly."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")
        assert provider.api_key == "test-key"
        assert provider.model == "gemini-2.0-flash"

    def test_provider_reads_env_var(self):
        """Test Google provider reads API key from environment."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "env-key"}):
            provider = GoogleProvider()
            assert provider.api_key == "env-key"

    def test_provider_raises_without_key(self):
        """Test Google provider raises error without API key."""
        with patch.dict(os.environ, {}, clear=True):
            provider = GoogleProvider()
            taxonomy = {"finance": ["budget"]}
            with pytest.raises(ValueError, match="API key required"):
                provider.extract_labels("test content", taxonomy)

    def test_extract_labels_returns_valid_labels(self):
        """Test Google provider extracts and filters labels."""
        # Import is local inside the method, need to patch where it's imported
        with patch("google.genai.Client") as mock_client_class:
            # Setup mock client
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.text = "finance, invoice, invalid"
            mock_client.models.generate_content.return_value = mock_response

            provider = GoogleProvider(api_key="test-key")
            taxonomy = {"finance": ["budget"], "invoice": ["billing"]}
            labels = provider.extract_labels("budget document", taxonomy)

            assert labels == ["finance", "invoice"]

    def test_extract_labels_returns_empty_for_none(self):
        """Test Google provider returns empty list for 'none' response."""
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.text = "none"
            mock_client.models.generate_content.return_value = mock_response

            provider = GoogleProvider(api_key="test-key")
            taxonomy = {"finance": ["budget"]}
            labels = provider.extract_labels("content", taxonomy)

            assert labels == []

    def test_extract_labels_parses_comma_separated(self):
        """Test Google provider correctly parses comma-separated labels."""
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.text = "finance , legal , contract"
            mock_client.models.generate_content.return_value = mock_response

            provider = GoogleProvider(api_key="test-key")
            taxonomy = {"finance": [], "legal": [], "contract": []}
            labels = provider.extract_labels("content", taxonomy)

            assert labels == ["finance", "legal", "contract"]


class TestOpenAIProvider:
    """Tests for OpenAI provider."""

    def test_provider_initialization(self):
        """Test OpenAI provider initializes correctly."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini")
        assert provider.api_key == "test-key"
        assert provider.model == "gpt-4o-mini"

    def test_provider_default_model(self):
        """Test OpenAI provider uses default model."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.model == "gpt-4o-mini"

    def test_provider_reads_env_var(self):
        """Test OpenAI provider reads API key from environment."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            provider = OpenAIProvider()
            assert provider.api_key == "env-key"

    def test_provider_raises_without_key(self):
        """Test OpenAI provider raises error without API key."""
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAIProvider()
            taxonomy = {"finance": ["budget"]}
            with pytest.raises(ValueError, match="API key required"):
                provider.extract_labels("test content", taxonomy)

    def test_extract_labels_returns_valid_labels(self):
        """Test OpenAI provider extracts and filters labels."""
        with patch("openai.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="finance, invoice, invalid"))
            ]
            mock_client.chat.completions.create.return_value = mock_response

            provider = OpenAIProvider(api_key="test-key")
            taxonomy = {"finance": ["budget"], "invoice": ["billing"]}
            labels = provider.extract_labels("budget document", taxonomy)

            assert labels == ["finance", "invoice"]
            # Verify correct API call
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            assert call_args.kwargs["model"] == "gpt-4o-mini"
            assert call_args.kwargs["max_tokens"] == 50

    def test_extract_labels_returns_empty_for_none(self):
        """Test OpenAI provider returns empty list for 'none' response."""
        with patch("openai.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="none"))]
            mock_client.chat.completions.create.return_value = mock_response

            provider = OpenAIProvider(api_key="test-key")
            taxonomy = {"finance": ["budget"]}
            labels = provider.extract_labels("content", taxonomy)

            assert labels == []


class TestGroqProvider:
    """Tests for Groq provider."""

    def test_provider_initialization(self):
        """Test Groq provider initializes correctly."""
        provider = GroqProvider(api_key="test-key", model="llama-3.1-8b-instant")
        assert provider.api_key == "test-key"
        assert provider.model == "llama-3.1-8b-instant"

    def test_provider_uses_correct_base_url(self):
        """Test Groq provider uses correct base URL."""
        with patch("openai.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="finance"))]
            mock_client.chat.completions.create.return_value = mock_response

            provider = GroqProvider(api_key="test-key")
            taxonomy = {"finance": []}
            provider.extract_labels("content", taxonomy)

            # Verify correct base URL
            mock_openai_class.assert_called_once_with(
                api_key="test-key",
                base_url="https://api.groq.com/openai/v1",
            )

    def test_extract_labels_returns_valid_labels(self):
        """Test Groq provider extracts and filters labels."""
        with patch("openai.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="finance, legal"))
            ]
            mock_client.chat.completions.create.return_value = mock_response

            provider = GroqProvider(api_key="test-key")
            taxonomy = {"finance": [], "legal": [], "contract": []}
            labels = provider.extract_labels("content", taxonomy)

            assert labels == ["finance", "legal"]


class TestOpenRouterProvider:
    """Tests for OpenRouter provider."""

    def test_provider_initialization(self):
        """Test OpenRouter provider initializes correctly."""
        provider = OpenRouterProvider(
            api_key="test-key", model="deepseek/deepseek-chat-v3-0324:free"
        )
        assert provider.api_key == "test-key"
        assert provider.model == "deepseek/deepseek-chat-v3-0324:free"

    def test_provider_uses_correct_base_url(self):
        """Test OpenRouter provider uses correct base URL."""
        with patch("openai.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="finance"))]
            mock_client.chat.completions.create.return_value = mock_response

            provider = OpenRouterProvider(api_key="test-key")
            taxonomy = {"finance": []}
            provider.extract_labels("content", taxonomy)

            # Verify correct base URL
            mock_openai_class.assert_called_once_with(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
            )

    def test_extract_labels_returns_valid_labels(self):
        """Test OpenRouter provider extracts and filters labels."""
        with patch("openai.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="finance, legal"))
            ]
            mock_client.chat.completions.create.return_value = mock_response

            provider = OpenRouterProvider(api_key="test-key")
            taxonomy = {"finance": [], "legal": [], "contract": []}
            labels = provider.extract_labels("content", taxonomy)

            assert labels == ["finance", "legal"]


class TestMockProvider:
    """Tests for Mock provider."""

    def test_default_labels(self):
        """Test mock provider returns default labels."""
        provider = MockProvider()
        taxonomy = {"documentation": [], "finance": []}
        labels = provider.extract_labels("any content", taxonomy)
        assert labels == ["documentation"]

    def test_custom_labels(self):
        """Test mock provider returns custom labels."""
        provider = MockProvider(labels=["finance", "invoice"])
        taxonomy = {"finance": [], "invoice": [], "legal": []}
        labels = provider.extract_labels("any content", taxonomy)
        assert labels == ["finance", "invoice"]

    def test_content_rules_matching(self):
        """Test mock provider matches content to labels."""
        provider = MockProvider(
            content_rules={
                "budget": "finance",
                "contract": "legal",
            },
            default_labels=["other"],
        )
        taxonomy = {"finance": [], "legal": [], "other": []}

        # Budget should match finance
        labels = provider.extract_labels("annual budget report", taxonomy)
        assert labels == ["finance"]

        # Contract should match legal
        labels = provider.extract_labels("contract agreement", taxonomy)
        assert labels == ["legal"]

    def test_content_rules_no_match(self):
        """Test mock provider returns defaults when no rules match."""
        provider = MockProvider(
            content_rules={"budget": "finance"},
            default_labels=["other"],
        )
        taxonomy = {"finance": [], "other": []}

        labels = provider.extract_labels("random text", taxonomy)
        assert labels == ["other"]

    def test_filters_invalid_labels(self):
        """Test mock provider filters labels not in taxonomy."""
        provider = MockProvider(labels=["finance", "invalid", "legal"])
        taxonomy = {"finance": [], "legal": []}
        labels = provider.extract_labels("content", taxonomy)
        assert labels == ["finance", "legal"]
        assert "invalid" not in labels

    def test_limits_to_three_labels(self):
        """Test mock provider limits to 3 labels."""
        provider = MockProvider(labels=["a", "b", "c", "d", "e"])
        taxonomy = {"a": [], "b": [], "c": [], "d": [], "e": []}
        labels = provider.extract_labels("content", taxonomy)
        assert len(labels) == 3


class TestGetProvider:
    """Tests for get_provider factory function."""

    def test_get_gemini_provider(self):
        """Test factory returns Google provider for 'gemini'."""
        provider = get_provider("gemini", api_key="test")
        assert isinstance(provider, GoogleProvider)

    def test_get_google_provider(self):
        """Test factory returns Google provider for 'google'."""
        provider = get_provider("google", api_key="test")
        assert isinstance(provider, GoogleProvider)

    def test_get_groq_provider(self):
        """Test factory returns Groq provider."""
        provider = get_provider("groq", api_key="test")
        assert isinstance(provider, GroqProvider)

    def test_get_openai_provider(self):
        """Test factory returns OpenAI provider."""
        provider = get_provider("openai", api_key="test")
        assert isinstance(provider, OpenAIProvider)

    def test_get_openrouter_provider(self):
        """Test factory returns OpenRouter provider."""
        provider = get_provider("openrouter", api_key="test")
        assert isinstance(provider, OpenRouterProvider)

    def test_get_mock_provider(self):
        """Test factory returns Mock provider."""
        provider = get_provider("mock")
        assert isinstance(provider, MockProvider)

    def test_get_provider_default(self):
        """Test factory defaults to Gemini."""
        provider = get_provider()
        assert isinstance(provider, GoogleProvider)

    def test_get_provider_unknown_raises(self):
        """Test factory raises error for unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider: unknown"):
            get_provider("unknown")

    def test_provider_default_models(self):
        """Test factory sets correct default models."""
        gemini = get_provider("gemini", api_key="test")
        assert gemini.model == "gemini-2.0-flash"

        openai = get_provider("openai", api_key="test")
        assert openai.model == "gpt-4o-mini"

        groq = get_provider("groq", api_key="test")
        assert groq.model == "llama-3.1-8b-instant"

        openrouter = get_provider("openrouter", api_key="test")
        assert openrouter.model == "deepseek/deepseek-chat-v3-0324:free"
