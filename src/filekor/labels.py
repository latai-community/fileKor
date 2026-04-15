"""Labels configuration module for taxonomy-based file labeling."""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from filekor.llm import LLMProvider, get_provider

# Default labels when no config file is found
DEFAULT_LABELS: Dict[str, List[str]] = {
    "finance": [
        "economy",
        "budget",
        "cost",
        "costs",
        "money",
        "financial",
        "billing",
        "invoice",
    ],
    "contract": ["agreement", "contract", "terms", "conditions", "legal"],
    "legal": ["law", "compliance", "gdpr", "privacy", "policy", "regulation"],
    "architecture": ["design", "architecture", "blueprint", "structure"],
    "specification": ["spec", "specs", "requirement", "requirements"],
    "documentation": ["docs", "documentation", "manual", "guide", "readme"],
}


class LabelsConfig:
    """Configuration for label taxonomy.

    Loads label definitions from a properties file and provides
    methods to suggest labels based on file paths.

    Attributes:
        synonyms: Dictionary mapping label names to their synonyms.
        confidence_threshold: Minimum confidence to include in suggestions.
    """

    synonyms: Dict[str, List[str]]
    confidence_threshold: float

    def __init__(
        self, synonyms: Dict[str, List[str]], confidence_threshold: float = 0.2
    ) -> None:
        """Initialize LabelsConfig with synonym mappings.

        Args:
            synonyms: Dictionary mapping label names to synonym lists.
            confidence_threshold: Minimum confidence to include (default 0.2).
        """
        self.synonyms = synonyms
        self.confidence_threshold = confidence_threshold

    @classmethod
    def load(cls, custom_path: Optional[str] = None) -> "LabelsConfig":
        """Load labels from a properties file.

        Searches for labels.properties in the following order:
        1. Custom path (if provided)
        2. Current directory
        3. .filekor/ subdirectory
        4. ~/.filekor/ directory
        5. Built-in defaults

        Args:
            custom_path: Optional path to a custom labels.properties file.

        Returns:
            LabelsConfig instance with loaded synonyms.
        """
        if custom_path:
            path = Path(custom_path)
            if path.exists():
                return cls._from_file(path)

        # Search order: current dir -> .filekor/ -> ~/.filekor/ -> defaults
        search_paths = [
            Path("labels.properties"),
            Path(".filekor/labels.properties"),
            Path.home() / ".filekor" / "labels.properties",
        ]

        for search_path in search_paths:
            if search_path.exists():
                return cls._from_file(search_path)

        # Fall back to defaults
        return cls(DEFAULT_LABELS.copy(), confidence_threshold=0.2)

    @classmethod
    def _from_file(cls, file_path: Path) -> "LabelsConfig":
        """Load labels from a properties file.

        Args:
            file_path: Path to the labels.properties file.

        Returns:
            LabelsConfig instance with parsed synonyms.
        """
        content = file_path.read_text(encoding="utf-8")
        synonyms = cls.parse_properties(content)
        return cls(synonyms)

    @staticmethod
    def parse_properties(content: str) -> Dict[str, List[str]]:
        """Parse properties content in LABEL=synonym1,synonym2 format.

        Args:
            content: The properties file content.

        Returns:
            Dictionary mapping label names to synonym lists.
        """
        synonyms: Dict[str, List[str]] = {}

        for line in content.splitlines():
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse key=value
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Skip empty synonyms
            if not value:
                continue

            # Parse comma-separated synonyms
            synonym_list = [s.strip().lower() for s in value.split(",") if s.strip()]

            if synonym_list:
                synonyms[key.lower()] = synonym_list

        return synonyms


# Global config instance - loaded lazily
_config: Optional[LabelsConfig] = None


def get_config() -> LabelsConfig:
    """Get the global labels config, loading it if necessary.

    Returns:
        The global LabelsConfig instance.
    """
    global _config
    if _config is None:
        _config = LabelsConfig.load()
    return _config


def reload_config(custom_path: Optional[str] = None) -> LabelsConfig:
    """Reload the global labels config.

    Args:
        custom_path: Optional path to a custom labels.properties file.

    Returns:
        The reloaded LabelsConfig instance.
    """
    global _config
    _config = LabelsConfig.load(custom_path)
    return _config


# LLM Config - loaded from config.yaml
DEFAULT_LLM_CONFIG = {
    "enabled": False,
    "provider": "gemini",
    "model": "gemini-2.0-flash",
    "max_content_chars": 1500,
    "workers": 4,
}


def _expand_env_vars(value: str) -> str:
    """Expand ${VAR} patterns in config values.

    Args:
        value: String that may contain ${VAR} patterns.

    Returns:
        String with environment variables expanded.
    """
    pattern = re.compile(r"\$\{([^}]+)\}")

    def replace(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return pattern.sub(replace, value)


class LLMConfig:
    """Configuration for LLM-based label extraction.

    Loads from config.yaml in ~/.filekor/ directory.
    """

    enabled: bool
    provider: str
    model: str
    api_key: Optional[str]
    max_content_chars: int
    workers: int
    auto_sync: bool

    def __init__(
        self,
        enabled: bool = False,
        provider: str = "gemini",
        model: str = "gemini-2.0-flash",
        api_key: Optional[str] = None,
        max_content_chars: int = 1500,
        workers: int = 4,
        auto_sync: bool = False,
    ):
        """Initialize LLMConfig.

        Args:
            enabled: Whether LLM label extraction is enabled.
            provider: LLM provider name (gemini, groq, openai, openrouter, mock).
            model: Model name to use.
            api_key: API key for the provider.
            max_content_chars: Maximum characters to send to LLM.
            workers: Number of parallel workers for directory processing.
            auto_sync: Whether to auto-sync to SQLite database after operations.
        """
        self.enabled = enabled
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.max_content_chars = max_content_chars
        self.workers = workers
        self.auto_sync = auto_sync

    @classmethod
    def load(cls, custom_path: Optional[str] = None) -> "LLMConfig":
        """Load LLM config from config.yaml.

        Searches in:
        1. Custom path (if provided)
        2. Current directory
        3. .filekor/ in current directory
        4. ~/.filekor/config.yaml

        Args:
            custom_path: Optional path to a custom config.yaml file.

        Returns:
            LLMConfig instance.
        """
        import yaml

        if custom_path:
            search_paths = [Path(custom_path)]
        else:
            search_paths = [
                Path("config.yaml"),
                Path(".filekor/config.yaml"),
                Path.home() / ".filekor" / "config.yaml",
            ]

        for search_path in search_paths:
            if search_path.exists():
                try:
                    content = search_path.read_text(encoding="utf-8")
                    data = yaml.safe_load(content)

                    if data and "filekor" in data:
                        filekor_config = data["filekor"]
                        llm_config = filekor_config.get("llm", {})

                        # Expand environment variables
                        api_key = llm_config.get("api_key")
                        if api_key and isinstance(api_key, str):
                            api_key = _expand_env_vars(api_key)

                        # Get workers count from filekor config (not under llm)
                        workers = filekor_config.get("workers", 4)

                        return cls(
                            enabled=llm_config.get("enabled", False),
                            provider=llm_config.get("provider", "gemini"),
                            model=llm_config.get("model", "gemini-2.0-flash"),
                            api_key=api_key,
                            max_content_chars=llm_config.get("max_content_chars", 1500),
                            workers=workers,
                            auto_sync=llm_config.get("auto_sync", False),
                        )
                except Exception:
                    # If config is invalid, fall back to defaults
                    pass

        # No config found, return defaults
        return cls()


def suggest_from_content(
    content: str,
    config: Optional[LabelsConfig] = None,
    llm_config: Optional[LLMConfig] = None,
) -> List[str]:
    """Suggest labels based on file content using LLM.

    Lower-level function that returns empty list if LLM is not configured
    (does not raise).

    Args:
        content: Text content from the file.
        config: LabelsConfig for taxonomy (provides available labels).
        llm_config: LLMConfig for LLM settings.

    Returns:
        List of suggested label names, or empty list if not configured.
    """
    if config is None:
        config = get_config()

    if llm_config is None:
        llm_config = LLMConfig.load()

    # Return empty if LLM is not configured
    if not llm_config.enabled or not llm_config.api_key:
        return []

    # Truncate content to max chars
    max_chars = llm_config.max_content_chars
    truncated_content = content[:max_chars] if len(content) > max_chars else content

    # Get taxonomy with synonyms (for LLM context)
    taxonomy = config.synonyms

    # Create provider and extract labels
    try:
        provider = get_provider(
            provider_name=llm_config.provider,
            api_key=llm_config.api_key,
            model=llm_config.model,
        )
        return provider.extract_labels(truncated_content, taxonomy)
    except Exception:
        # Return empty on error
        return []


def suggest_labels(
    content: str,
    config: Optional[LabelsConfig] = None,
    llm_config: Optional[LLMConfig] = None,
) -> List[str]:
    """Suggest labels based on file content using LLM only.

    Raises an error if LLM is not configured.

    Args:
        content: Text content from the file.
        config: LabelsConfig for taxonomy (provides available labels).
        llm_config: LLMConfig for LLM settings.

    Returns:
        List of suggested label names.

    Raises:
        RuntimeError: If LLM is not enabled or not configured.
    """
    if config is None:
        config = get_config()

    if llm_config is None:
        llm_config = LLMConfig.load()

    # Raise error if LLM is not configured
    if not llm_config.enabled or not llm_config.api_key:
        raise RuntimeError(
            "LLM is not configured. Please enable LLM in config.yaml "
            "with a valid API key."
        )

    # Use lower-level function for extraction
    return suggest_from_content(content, config, llm_config)
