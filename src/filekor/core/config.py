"""FilekorConfig: central configuration for filekor.

Provides a single access point to all filekor settings from config.yaml.
Supports both file-based loading and programmatic construction.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from filekor.constants import (
    CONFIG_DB_KEY,
    CONFIG_FILENAME,
    CONFIG_LLM_KEY,
    CONFIG_ROOT_KEY,
    CONFIG_WORKERS_KEY,
    FILEKOR_DIR,
)
from filekor.core.labels import LLMConfig


DEFAULT_DB_PATH = Path.home() / FILEKOR_DIR / "index.db"


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


class FilekorConfig:
    """Central configuration for filekor.

    Reads the full ``filekor`` block from config.yaml and exposes
    typed attributes. Supports both file-based loading and programmatic
    construction.

    Usage from file (CLI):
        config = FilekorConfig.load()
        config = FilekorConfig.load("/path/to/config.yaml")

    Usage programmatic (library):
        config = FilekorConfig(db_path=Path("/data/index.db"), workers=8)
    """

    db_path: Path
    workers: int
    llm: LLMConfig

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        workers: int = 4,
        llm: Optional[Union[LLMConfig, Dict[str, Any]]] = None,
    ):
        """Initialize FilekorConfig.

        Args:
            db_path: Path to SQLite database file. Supports ~ and relative paths.
                     Default: ~/.filekor/index.db
            workers: Number of parallel workers for directory operations. Default: 4
            llm: LLM configuration. Can be:
                 - An LLMConfig instance
                 - A dict with LLM settings (enabled, provider, model, api_key, etc.)
                 - None for defaults (LLM disabled)
        """
        if db_path is None:
            self.db_path = DEFAULT_DB_PATH
        else:
            self.db_path = Path(db_path).expanduser().resolve()

        self.workers = workers

        if isinstance(llm, LLMConfig):
            self.llm = llm
        elif isinstance(llm, dict):
            api_key = llm.get("api_key")
            if api_key and isinstance(api_key, str):
                api_key = _expand_env_vars(api_key)

            self.llm = LLMConfig(
                enabled=llm.get("enabled", False),
                provider=llm.get("provider", "gemini"),
                model=llm.get("model", "gemini-2.0-flash"),
                api_key=api_key,
                max_content_chars=llm.get("max_content_chars", 1500),
                workers=workers,
                auto_sync=llm.get("auto_sync", False),
            )
        else:
            self.llm = LLMConfig(workers=workers)

    @classmethod
    def load(cls, custom_path: Optional[str] = None) -> "FilekorConfig":
        """Load configuration from config.yaml.

        Searches in:
        1. Custom path (if provided)
        2. Current directory
        3. .filekor/ in current directory
        4. ~/.filekor/config.yaml

        Args:
            custom_path: Optional path to a custom config.yaml file.

        Returns:
            FilekorConfig instance.
        """
        if custom_path:
            search_paths = [Path(custom_path)]
        else:
            search_paths = [
                Path(CONFIG_FILENAME),
                Path(FILEKOR_DIR) / CONFIG_FILENAME,
                Path.home() / FILEKOR_DIR / CONFIG_FILENAME,
            ]

        for search_path in search_paths:
            if search_path.exists():
                try:
                    content = search_path.read_text(encoding="utf-8")
                    data = yaml.safe_load(content)

                    if data and CONFIG_ROOT_KEY in data:
                        filekor_data = data[CONFIG_ROOT_KEY]
                        return cls._from_dict(filekor_data)
                except Exception:
                    pass

        # No config found, return defaults
        return cls()

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "FilekorConfig":
        """Create FilekorConfig from a parsed dict.

        Args:
            data: The ``filekor`` block from config.yaml.

        Returns:
            FilekorConfig instance.
        """
        # DB path
        db_data = data.get(CONFIG_DB_KEY, {})
        db_path = db_data.get("path")
        if db_path:
            db_path = Path(db_path).expanduser().resolve()

        # Workers
        workers = data.get(CONFIG_WORKERS_KEY, 4)

        # LLM (pass raw dict, let __init__ handle env vars)
        llm_data = data.get(CONFIG_LLM_KEY, {})

        return cls(
            db_path=db_path,
            workers=workers,
            llm=llm_data,
        )

    def __repr__(self) -> str:
        return (
            f"FilekorConfig(db_path={self.db_path}, "
            f"workers={self.workers}, "
            f"llm_enabled={self.llm.enabled})"
        )
