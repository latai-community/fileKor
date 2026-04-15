"""Labels configuration module for taxonomy-based file labeling."""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def suggest_from_path(
    file_path: str,
    config: Optional[LabelsConfig] = None,
    threshold: Optional[float] = None,
) -> List[Tuple[str, float]]:
    """Suggest labels based on a file path.

    Extracts words from the file path (filename and directory components),
    converts them to lowercase, and matches them against synonyms to calculate
    confidence scores.

    Args:
        file_path: Path to the file.
        config: LabelsConfig instance (uses global config if None).
        threshold: Minimum confidence threshold (uses config.confidence_threshold if None).

    Returns:
        List of (label, confidence) tuples sorted by confidence descending.
    """
    if config is None:
        config = get_config()

    # Use config threshold if not provided
    if threshold is None:
        threshold = config.confidence_threshold

    # Extract words from path
    path = Path(file_path)
    words = set()

    # Add filename parts
    name_without_ext = path.stem.lower()
    for word in (
        name_without_ext.replace("-", " ").replace("_", " ").replace("/", " ").split()
    ):
        if word:
            words.add(word)

    # Add directory parts
    for part in path.parts[:-1]:
        for word in part.lower().replace("-", " ").replace("_", " ").split():
            if word:
                words.add(word)

    # Match against synonyms
    scores: Dict[str, float] = {}

    for label, synonym_list in config.synonyms.items():
        matched = 0
        for synonym in synonym_list:
            if synonym in words:
                matched += 1

        if matched > 0:
            confidence = matched / len(synonym_list)
            if confidence >= threshold:
                scores[label] = confidence

    # Sort by confidence descending
    sorted_labels = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return sorted_labels


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

    def __init__(
        self,
        enabled: bool = False,
        provider: str = "gemini",
        model: str = "gemini-2.0-flash",
        api_key: Optional[str] = None,
        max_content_chars: int = 1500,
    ):
        """Initialize LLMConfig.

        Args:
            enabled: Whether LLM label extraction is enabled.
            provider: LLM provider name (gemini, mock).
            model: Model name to use.
            api_key: API key for the provider.
            max_content_chars: Maximum characters to send to LLM.
        """
        self.enabled = enabled
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.max_content_chars = max_content_chars

    @classmethod
    def load(cls) -> "LLMConfig":
        """Load LLM config from config.yaml.

        Searches in:
        1. Current directory
        2. .filekor/ in current directory
        3. ~/.filekor/config.yaml

        Returns:
            LLMConfig instance.
        """
        import yaml

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

                        return cls(
                            enabled=llm_config.get("enabled", False),
                            provider=llm_config.get("provider", "gemini"),
                            model=llm_config.get("model", "gemini-2.0-flash"),
                            api_key=api_key,
                            max_content_chars=llm_config.get("max_content_chars", 1500),
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

    Args:
        content: Text content from the file.
        config: LabelsConfig for taxonomy (provides available labels).
        llm_config: LLMConfig for LLM settings.

    Returns:
        List of suggested label names.
    """
    if config is None:
        config = get_config()

    if llm_config is None:
        llm_config = LLMConfig.load()

    # Check if LLM is enabled and configured
    if not llm_config.enabled or not llm_config.api_key:
        return []

    # Truncate content to max chars
    max_chars = llm_config.max_content_chars
    truncated_content = content[:max_chars] if len(content) > max_chars else content

    # Get available labels from taxonomy
    available_labels = list(config.synonyms.keys())

    # Create provider and extract labels
    try:
        provider = get_provider(
            provider_name=llm_config.provider,
            api_key=llm_config.api_key,
            model=llm_config.model,
        )
        return provider.extract_labels(truncated_content, available_labels)
    except Exception:
        # Silent fallback on any error - return empty list
        return []


def suggest_hybrid(
    file_path: str,
    content: Optional[str] = None,
    use_llm: Optional[bool] = None,
    config: Optional[LabelsConfig] = None,
    llm_config: Optional[LLMConfig] = None,
    threshold: Optional[float] = None,
) -> Tuple[List[str], str]:
    """Suggest labels using hybrid approach (LLM + path-based).

    Args:
        file_path: Path to the file.
        content: Optional text content for LLM analysis.
        use_llm: Force LLM usage (True=LLM, False=path only, None=auto from config).
        config: LabelsConfig for taxonomy.
        llm_config: LLMConfig for LLM settings.
        threshold: Confidence threshold for path-based matching.

    Returns:
        Tuple of (labels: List[str], source: str)
        source is "llm" or "path"
    """
    if config is None:
        config = get_config()

    if llm_config is None:
        llm_config = LLMConfig.load()

    # Determine whether to use LLM
    if use_llm is None:
        use_llm = llm_config.enabled and bool(llm_config.api_key)

    # Try LLM first if enabled
    if use_llm and content:
        llm_labels = suggest_from_content(content, config, llm_config)
        if llm_labels:
            return llm_labels, "llm"

    # Fallback to path-based
    path_labels = suggest_from_path(file_path, config, threshold)
    return [label for label, _ in path_labels], "path"
