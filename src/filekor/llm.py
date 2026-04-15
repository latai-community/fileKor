"""LLM provider abstraction for label extraction."""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def extract_labels(
        self,
        content: str,
        taxonomy: Dict[str, List[str]],
    ) -> List[str]:
        """Extract labels from content using LLM.

        Args:
            content: Text content to analyze.
            taxonomy: Dict mapping label names to synonym lists.

        Returns:
            List of suggested labels.
        """
        pass


class GoogleProvider(LLMProvider):
    """Google Gemini provider for label extraction."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
    ):
        """Initialize Google provider.

        Args:
            api_key: Google API key. If None, reads from GOOGLE_API_KEY env var.
            model: Model name to use (default: gemini-2.0-flash).
        """
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.model = model

    def extract_labels(
        self,
        content: str,
        taxonomy: Dict[str, List[str]],
    ) -> List[str]:
        """Extract labels from content using Google Gemini.

        Args:
            content: Text content to analyze.
            taxonomy: Dict mapping label names to synonym lists.

        Returns:
            List of suggested labels.
        """
        if not self.api_key:
            raise ValueError(
                "API key required. Set GOOGLE_API_KEY env var or pass api_key."
            )

        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai not installed. Run: uv pip install google-genai"
            )

        client = genai.Client(api_key=self.api_key)

        # Build taxonomy context with synonyms
        taxonomy_lines = []
        for label, synonyms in taxonomy.items():
            synonyms_str = ", ".join(synonyms)
            taxonomy_lines.append(f"- {label}: {synonyms_str}")
        taxonomy_str = "\n".join(taxonomy_lines)

        prompt = f"""Based on the following file content, suggest 1-5 taxonomy labels from this list:

{taxonomy_str}

Content:
{content}

Return ONLY the labels as comma-separated list, nothing else. If no labels apply, return "none"."""

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        text = response.text.strip().lower()

        if text == "none" or not text:
            return []

        # Parse comma-separated labels
        labels = [label.strip() for label in text.split(",")]
        # Filter to only valid labels from the taxonomy
        valid_labels = [label for label in labels if label in taxonomy]

        return valid_labels


class GroqProvider(LLMProvider):
    """Groq provider for fast LLM inference."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama-3.1-8b-instant",
    ):
        """Initialize Groq provider.

        Args:
            api_key: Groq API key.
            model: Model name to use.
        """
        self.api_key = api_key
        self.model = model

    def extract_labels(
        self,
        content: str,
        taxonomy: Dict[str, List[str]],
    ) -> List[str]:
        """Extract labels using Groq."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required. pip install openai")

        client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
        )

        # Build taxonomy context
        taxonomy_lines = []
        for label, synonyms in taxonomy.items():
            synonyms_str = ", ".join(synonyms)
            taxonomy_lines.append(f"- {label}: {synonyms_str}")
        taxonomy_str = "\n".join(taxonomy_lines)

        prompt = f"""Based on the following file content, suggest 1-5 taxonomy labels from this list:

{taxonomy_str}

Content:
{content}

Return ONLY the labels as comma-separated list, nothing else. If no labels apply, return "none"."""

        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
        )

        text = response.choices[0].message.content.strip().lower()

        if text == "none" or not text:
            return []

        labels = [label.strip() for label in text.split(",")]
        valid_labels = [label for label in labels if label in taxonomy]

        return valid_labels


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider - gateway to 200+ free models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "deepseek/deepseek-chat-v3-0324:free",
    ):
        """Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key.
            model: Model name (e.g., deepseek/deepseek-chat-v3-0324:free).
        """
        self.api_key = api_key
        self.model = model

    def extract_labels(
        self,
        content: str,
        taxonomy: Dict[str, List[str]],
    ) -> List[str]:
        """Extract labels using OpenRouter."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required. pip install openai")

        client = OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
        )

        # Build taxonomy context
        taxonomy_lines = []
        for label, synonyms in taxonomy.items():
            synonyms_str = ", ".join(synonyms)
            taxonomy_lines.append(f"- {label}: {synonyms_str}")
        taxonomy_str = "\n".join(taxonomy_lines)

        prompt = f"""Based on the following file content, suggest 1-5 taxonomy labels from this list:

{taxonomy_str}

Content:
{content}

Return ONLY the labels as comma-separated list, nothing else. If no labels apply, return "none"."""

        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
        )

        text = response.choices[0].message.content.strip().lower()

        if text == "none" or not text:
            return []

        labels = [label.strip() for label in text.split(",")]
        valid_labels = [label for label in labels if label in taxonomy]

        return valid_labels


class MockProvider(LLMProvider):
    """Mock provider for testing without API calls."""

    def __init__(self, labels: Optional[List[str]] = None):
        """Initialize mock provider.

        Args:
            labels: Labels to return (default: ["documentation"]).
        """
        self.labels = labels or ["documentation"]

    def extract_labels(
        self,
        content: str,
        taxonomy: Dict[str, List[str]],
    ) -> List[str]:
        """Return mock labels.

        Args:
            content: Text content (ignored).
            taxonomy: Dict mapping label names to synonym lists.

        Returns:
            Mock labels.
        """
        # Return first few valid labels for testing
        return [label for label in self.labels if label in taxonomy][:3]


def get_provider(
    provider_name: str = "gemini",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMProvider:
    """Get LLM provider instance.

    Args:
        provider_name: Provider name (gemini, groq, openrouter, mock).
        api_key: API key for the provider.
        model: Model name (for Gemini, Groq, OpenRouter).

    Returns:
        LLMProvider instance.
    """
    if provider_name == "gemini" or provider_name == "google":
        return GoogleProvider(api_key=api_key, model=model or "gemini-2.0-flash")
    elif provider_name == "groq":
        return GroqProvider(api_key=api_key, model=model or "llama-3.1-8b-instant")
    elif provider_name == "openrouter":
        return OpenRouterProvider(
            api_key=api_key, model=model or "deepseek/deepseek-chat-v3-0324:free"
        )
    elif provider_name == "mock":
        return MockProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
