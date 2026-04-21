# AGENTS.md — fileKor

## What this is

Python 3.11+ CLI/library for extracting metadata from files (PDF, TXT, MD), generating `.kor` YAML sidecars, classifying with an LLM taxonomy, and indexing into SQLite with FTS5 search.

## Dev commands

```bash
# Setup (uses uv, NOT pip/poetry)
uv venv && .venv\Scripts\activate   # Windows
uv pip install -e .                 # install in dev mode
uv pip install -e ".[dev]"          # if dev extras exist

# Tests
pytest tests/                       # all tests
pytest tests/test_labels.py -v      # single file
pytest tests/ --cov                 # with coverage

# Lint/format (ruff is available, no formatter script found)
ruff check src/ tests/
ruff format src/ tests/
```

No lint/typecheck/formatter scripts defined in `pyproject.toml` — run ruff directly.

## Architecture

```
src/filekor/
├── cli/           # Click commands — each file is one command (extract.py, sidecar.py, etc.)
│   └── __init__.py  registers all commands on the cli group
├── core/          # Business logic (config, labels, processor, merge, list, delete, summary)
│   └── models/    # Pydantic data models (db_models, file_status, process_result)
├── adapters/      # Metadata extraction — base.py defines MetadataAdapter ABC, exiftool.py implements it
├── db.py          # SQLite singleton (Database class), FTS5 search, schema migrations
├── llm.py         # LLM provider abstraction (Google, OpenAI, Groq, OpenRouter, Mock)
├── labels.py      # Taxonomy loading from labels.properties, synonym matching
├── sidecar.py     # Sidecar/FileMetadata/FileInfo/Content Pydantic models, YAML serialization
└── processor.py   # Directory processing orchestration
```

Entry point: `filekor.cli:cli` (Click group). Also runnable via `python -m filekor`.

## Config

- `config.yaml` searched in: CWD → `.filekor/` → `~/.filekor/`. See `FilekorConfig.load()` in `core/config.py`.
- Supports `${ENV_VAR}` expansion in config values.
- `config-example.yaml` is the template. Real `config.yaml` is gitignored and may contain API keys — never commit it.
- LLM requires: `enabled: true`, `provider`, `api_key`, `model`. Providers read env vars as fallback (e.g. `GOOGLE_API_KEY`).
- DB path defaults to `~/.filekor/index.db`.

## Labels / taxonomy

- `labels.properties` at project root defines canonical labels and synonyms (format: `KEY=syn1,syn2`).
- `LabelsConfig.load()` reads it. Falls back to built-in defaults if file missing.
- Labels are multilingual (English + German synonyms).

## .kor sidecar files

- Generated in `.filekor/` subdirectory next to the source file (NOT alongside it).
- Single file → `merged.kor` by default. Use `--no-merge` for individual `.kor` files.
- YAML format with fields: version, file, metadata, content, summary, labels, parser_status, generated_at.

## Testing quirks

- Tests mock `filekor.cli.HAS_PYPDF` to `False` when testing CLI commands that would otherwise need pypdf installed.
- Database tests must reset `Database._instance = None` before and after — it's a singleton.
- Sidecar CLI tests need a `config.yaml` with `provider: mock` in a temp directory.
- `auto_sync` hook in `cli/sidecar.py` swallows exceptions intentionally — don't treat silent failures as bugs in tests.
- LLM provider tests mock the actual client (e.g. `google.genai.Client`) — never make real API calls in tests.

## Key imports

```python
# Library API
from filekor.db import get_db, sync_file, search_files
from filekor.sidecar import Sidecar, FileInfo, FileMetadata, Content
from filekor.labels import LabelsConfig, LLMConfig, suggest_labels

# Core logic
from filekor.core.config import FilekorConfig
from filekor.core.processor import process_directory
```

## External dependencies

- **exiftool** — required for metadata extraction. Tests that need it mock `PyExifToolAdapter.is_available`.
- **pypdf** — optional, for PDF text extraction. `HAS_PYPDF` flag controls fallback.
