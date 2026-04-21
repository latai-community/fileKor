"""Tests for core/config.py — FilekorConfig, _expand_env_vars."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from filekor.core.config import DEFAULT_DB_PATH, FilekorConfig, _expand_env_vars
from filekor.core.labels import LLMConfig


class TestFilekorConfigInit:
    def test_defaults(self):
        """Default construction sets expected values."""
        config = FilekorConfig()

        assert config.db_path == DEFAULT_DB_PATH
        assert config.workers == 4
        assert config.llm.enabled is False
        assert config.llm.provider == "gemini"
        assert config.llm.model == "gemini-2.0-flash"
        assert config.llm.api_key is None
        assert config.llm.max_content_chars == 1500
        assert config.llm.workers == 4
        assert config.llm.auto_sync is False

    def test_custom_db_path(self, tmp_path):
        """Custom db_path is expanded and resolved."""
        custom = tmp_path / "data.db"
        config = FilekorConfig(db_path=str(custom))

        assert config.db_path == custom.resolve()

    def test_custom_workers(self):
        """Custom workers propagated to config and LLM."""
        config = FilekorConfig(workers=8)

        assert config.workers == 8
        assert config.llm.workers == 8

    def test_llm_as_dict(self):
        """LLM passed as dict is parsed into LLMConfig."""
        config = FilekorConfig(
            llm={
                "enabled": True,
                "provider": "openai",
                "model": "gpt-4",
                "api_key": "secret",
                "max_content_chars": 500,
                "auto_sync": True,
            }
        )

        assert isinstance(config.llm, LLMConfig)
        assert config.llm.enabled is True
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4"
        assert config.llm.api_key == "secret"
        assert config.llm.max_content_chars == 500
        assert config.llm.auto_sync is True

    def test_llm_as_llmconfig_instance(self):
        """LLM passed as LLMConfig instance is used directly."""
        llm = LLMConfig(enabled=True, provider="groq", model="llama3")
        config = FilekorConfig(llm=llm)

        assert config.llm is llm

    def test_llm_dict_env_expansion(self, monkeypatch):
        """Env vars in api_key are expanded when llm is a dict."""
        monkeypatch.setenv("MY_KEY", "expanded_key")
        config = FilekorConfig(llm={"api_key": "${MY_KEY}"})

        assert config.llm.api_key == "expanded_key"

    def test_llm_none_defaults(self):
        """llm=None creates default LLMConfig."""
        config = FilekorConfig(llm=None)

        assert isinstance(config.llm, LLMConfig)
        assert config.llm.enabled is False


class TestFilekorConfigLoad:
    @patch("filekor.core.config.yaml.safe_load")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_load_existing_config(self, mock_read_text, mock_exists, mock_safe_load):
        """Load finds config.yaml in CWD with filekor block."""
        mock_exists.return_value = True
        mock_read_text.return_value = "dummy"
        mock_safe_load.return_value = {
            "filekor": {
                "db": {"path": "/tmp/test.db"},
                "workers": 2,
                "llm": {"enabled": True},
            }
        }

        config = FilekorConfig.load()

        assert config.db_path == Path("/tmp/test.db").expanduser().resolve()
        assert config.workers == 2
        assert config.llm.enabled is True

    @patch("filekor.core.config.yaml.safe_load")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_load_custom_path(self, mock_read_text, mock_exists, mock_safe_load):
        """Load with custom path uses that file exclusively."""
        mock_exists.return_value = True
        mock_read_text.return_value = "dummy"
        mock_safe_load.return_value = {"filekor": {"workers": 16}}

        config = FilekorConfig.load("/custom/config.yaml")

        assert config.workers == 16

    @patch("pathlib.Path.exists")
    def test_load_no_config_returns_defaults(self, mock_exists):
        """No config found anywhere returns default instance."""
        mock_exists.return_value = False

        config = FilekorConfig.load()

        assert config.db_path == DEFAULT_DB_PATH
        assert config.workers == 4


class TestExpandEnvVars:
    def test_existing_variable(self, monkeypatch):
        """Existing env var is expanded."""
        monkeypatch.setenv("EXISTING_VAR", "hello")
        assert (
            _expand_env_vars("prefix/${EXISTING_VAR}/suffix") == "prefix/hello/suffix"
        )

    def test_missing_variable(self):
        """Missing env var is left as-is."""
        assert (
            _expand_env_vars("prefix/${MISSING_VAR}/suffix")
            == "prefix/${MISSING_VAR}/suffix"
        )

    def test_multiple_vars(self, monkeypatch):
        """Multiple env vars in one string are expanded."""
        monkeypatch.setenv("A", "alpha")
        monkeypatch.setenv("B", "beta")
        assert _expand_env_vars("${A}-${B}") == "alpha-beta"


class TestFilekorConfigFromDict:
    def test_from_dict_all_fields(self):
        """_from_dict parses db, workers and llm."""
        data = {
            "db": {"path": "~/mydb.sqlite"},
            "workers": 8,
            "llm": {
                "enabled": True,
                "provider": "openai",
                "model": "gpt-3.5",
                "api_key": "key123",
            },
        }

        config = FilekorConfig._from_dict(data)

        assert config.db_path == Path("~/mydb.sqlite").expanduser().resolve()
        assert config.workers == 8
        assert config.llm.enabled is True
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-3.5"
        assert config.llm.api_key == "key123"

    def test_from_dict_defaults(self):
        """_from_dict with empty dict falls back to defaults."""
        config = FilekorConfig._from_dict({})

        assert config.db_path == DEFAULT_DB_PATH
        assert config.workers == 4
        assert config.llm.enabled is False

    def test_from_dict_partial_llm(self):
        """_from_dict passes partial llm dict through."""
        config = FilekorConfig._from_dict({"llm": {"provider": "groq"}})

        assert config.llm.provider == "groq"
        assert config.llm.enabled is False  # default


class TestFilekorConfigRepr:
    def test_repr(self):
        """__repr__ includes db_path, workers and llm_enabled."""
        config = FilekorConfig(db_path="/tmp/db", workers=2, llm={"enabled": True})
        r = repr(config)

        assert "FilekorConfig(" in r
        assert "db_path=" in r
        assert "workers=2" in r
        assert "llm_enabled=True" in r

    def test_repr_defaults(self):
        """__repr__ works with defaults."""
        config = FilekorConfig()
        r = repr(config)

        assert "llm_enabled=False" in r
