# AGENTS.md — fileKor

Python 3.11+ CLI/library for extracting metadata from files (PDF, TXT, MD), generating `.kor` YAML sidecars, classifying with an LLM taxonomy, and indexing into SQLite with FTS5 search.

## Dev commands

```bash
# Setup (uses uv, NOT pip/poetry)
uv venv && .venv\Scripts\activate   # Windows
uv pip install -e .                 # install in dev mode

# Tests
pytest tests/                       # all tests (355 tests, ~15s)
pytest tests/test_<file>.py -v      # single file
pytest tests/ --cov                 # coverage report

# Lint/format
ruff check src/ tests/
ruff format src/ tests/
```

## Architecture

```
src/filekor/
├── cli/           # Click commands — each file is one command
│   └── __init__.py  registers all commands on the cli group
├── core/          # Business logic
│   ├── config.py
│   ├── delete.py
│   ├── events.py
│   ├── hasher.py
│   ├── labels.py       # taxonomy + LLMConfig
│   ├── list.py
│   ├── llm.py          # providers (Google, OpenAI, Groq, OpenRouter, Mock)
│   ├── merge.py
│   ├── models/         # Pydantic models (db_models, file_status, process_result)
│   ├── processor.py
│   ├── status.py
│   └── summary.py
├── constants.py   # ALL magic strings centralized here
├── db.py          # SQLite singleton (Database class), FTS5 search
├── sidecar.py     # Sidecar/FileMetadata/FileInfo/Content models
└── adapters/      # Metadata extraction — exiftool.py
```

**Entry point:** `filekor.cli:cli` (Click group). Also runnable via `python -m filekor`.

**Legacy root modules were removed** (2025 refactor). The real implementations live in `core/`. Do not recreate `events.py`, `processor.py`, `status.py`, `labels.py`, or `llm.py` at the root level.

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
- `--labels`: Generate labels via LLM.
- `--summary`: Generate summaries via LLM (both by default, or `--summary=short`/`--summary=long`).
- YAML format with fields: version, file, metadata, content, summary, labels, parser_status, generated_at.

## Magic strings

**All magic strings live in `src/filekor/constants.py`**. When adding new literals that appear in multiple places (file extensions, config keys, DB column names, etc.), define them there and import. See the file for existing constants.

## Documentation

After modifying CLI commands or core behavior, update the corresponding documentation:
- `docs/usage.md` — CLI usage and examples
- `docs/library.md` — Python library API

## Testing — critical rules

### Mocking
- **`patch()` must target where the function is USED, not where it is defined.**
  - `summary.py` does `from filekor.cli.base import extract_text` — patch `filekor.cli.summary.extract_text` (not `filekor.cli.base.extract_text`).
  - Same rule applies to `generate_summary`, `create_emitter`, etc.
- LLM provider tests mock the actual client (e.g. `google.genai.Client`) — never make real API calls.

### Database singleton
- There is a **double singleton**: `Database._instance` AND `filekor.db._db_instance`.
- Tests must reset **both** in `setUp`/`tearDown`:
  ```python
  import filekor.db as _db_module
  Database._instance = None
  _db_module._db_instance = None
  ```

### CLI testing
- Use `CliRunner` from `click.testing`.
- `CliRunner` strips Rich formatting tags (`[green]`, `[red]`) from output — do not assert on them.
- `auto_sync` hook in `cli/sidecar.py` swallows exceptions intentionally — don't treat silent failures as bugs in tests.

### Other quirks
- Tests mock `filekor.cli.HAS_PYPDF` to `False` when testing CLI commands that would otherwise need pypdf installed.
- Sidecar CLI tests need a `config.yaml` with `provider: mock` in a temp directory.

## Key imports

```python
# Library API
from filekor.db import get_db, sync_file, search_files
from filekor.sidecar import Sidecar, FileInfo, FileMetadata, Content
from filekor.core.labels import LabelsConfig, LLMConfig, suggest_labels

# Core logic
from filekor.core.config import FilekorConfig
from filekor.core.processor import process_directory
```

## Logging and user output

- **NEVER use `logging`** for messages visible to the user — logging is designed for debugging/monitoring and is invisible by default.
- **ALWAYS use `console.print()` (Rich)** with colors for user-facing output:
  - `[green]` for success (e.g., `console.print("[green]OK[/green] file.txt")`)
  - `[red]` for fatal errors (e.g., `console.print("[red]Error: File not found[/red]")`)
  - `[yellow]` for non-fatal warnings (e.g., `console.print("[yellow]Warning: Auto-sync failed: {e}[/yellow]")`)
- This is consistent with the rest of the codebase (`cli/sidecar.py:162` uses exactly this pattern for DB sync warnings).

## External dependencies

- **exiftool** — required for metadata extraction. Tests that need it mock `PyExifToolAdapter.is_available`.
- **pypdf** — optional, for PDF text extraction. `HAS_PYPDF` flag controls fallback.
