"""Summary module for LLM-based content summarization."""

from typing import Literal, Optional

from pydantic import BaseModel

from filekor.constants import CONFIG_FILENAME
from filekor.core.llm import get_provider
from filekor.core.labels import LLMConfig


SHORT_PROMPT = (
    "Summarize the following content in 1-2 concise sentences. "
    "Only respond with the summary, no prefixes or explanations:\n\n"
    "{content}"
)

LONG_PROMPT = (
    "Generate a detailed summary of the following content. "
    "Include key points, document structure, and relevant findings. "
    "Only respond with the summary, no prefixes or explanations:\n\n"
    "{content}"
)


class SummaryResult(BaseModel):
    """Result of a summary generation."""

    short: Optional[str] = None
    long: Optional[str] = None


def generate_summary(
    content: str,
    length: Literal["short", "long", "both"] = "both",
    llm_config: Optional[LLMConfig] = None,
    max_chars: Optional[int] = None,
) -> SummaryResult:
    """Generate summaries using LLM.

    Args:
        content: Text content to summarize.
        length: Which summary to generate: "short", "long", or "both".
        llm_config: LLM configuration. If None, loads from config.yaml.
        max_chars: Maximum characters to send to LLM. Overrides config if set.

    Returns:
        SummaryResult with short and/or long summaries.

    Raises:
        RuntimeError: If LLM is not enabled or not configured.
    """
    if llm_config is None:
        llm_config = LLMConfig.load()

    if not llm_config.enabled or not llm_config.api_key:
        raise RuntimeError(
            f"LLM is not configured. Please enable LLM in {CONFIG_FILENAME} "
            "with a valid API key."
        )

    effective_max = max_chars if max_chars is not None else llm_config.max_content_chars
    truncated = content[:effective_max] if len(content) > effective_max else content

    provider = get_provider(
        provider_name=llm_config.provider,
        api_key=llm_config.api_key,
        model=llm_config.model,
    )

    result = SummaryResult()

    if length in ("short", "both"):
        result.short = _call_llm(provider, SHORT_PROMPT, truncated)

    if length in ("long", "both"):
        result.long = _call_llm(provider, LONG_PROMPT, truncated)

    return result


def _call_llm(provider, prompt_template: str, content: str) -> str:
    """Call LLM with a prompt template.

    Args:
        provider: LLM provider instance.
        prompt_template: Prompt template with {content} placeholder.
        content: Truncated content to insert.

    Returns:
        Generated text from LLM.
    """
    prompt = prompt_template.format(content=content)

    # Reuse the provider's chat interface
    # All providers use openai-compatible or genai APIs
    provider_name = type(provider).__name__

    if provider_name == "GoogleProvider":
        from google import genai

        client = genai.Client(api_key=provider.api_key)
        response = client.models.generate_content(
            model=provider.model,
            contents=prompt,
        )
        return response.text.strip()

    # Groq, OpenAI, OpenRouter all use openai-compatible API
    elif provider_name in ("GroqProvider", "OpenAIProvider", "OpenRouterProvider"):
        from openai import OpenAI

        if provider_name == "GroqProvider":
            client = OpenAI(
                api_key=provider.api_key,
                base_url="https://api.groq.com/openai/v1",
            )
        elif provider_name == "OpenRouterProvider":
            client = OpenAI(
                api_key=provider.api_key,
                base_url="https://openrouter.ai/api/v1",
            )
        else:
            client = OpenAI(api_key=provider.api_key)

        response = client.chat.completions.create(
            model=provider.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()

    elif provider_name == "MockProvider":
        return "This is a mock summary generated for testing purposes."

    else:
        raise ValueError(f"Unknown provider type: {provider_name}")
