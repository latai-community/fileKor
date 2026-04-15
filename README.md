# fileKor

Local metadata engine that extracts, summarizes, classifies, and tags files using taxonomy-based labeling.

## Quick Start

```bash
# Install uv
winget install astral-sh.uv

# Setup
uv venv
.venv\Scripts\activate
uv pip install -e .

# CLI Usage
filekor extract documento.pdf
filekor sidecar documento.pdf
filekor labels documento.pdf
filekor sync documento.kor          # Sync existing .kor to database
```

## Library Usage

filekor can also be used as a Python library for database-backed queries:

```python
from filekor.db import get_db, sync_file, query_by_label

# Get database instance (lazy singleton)
db = get_db()

# Sync a .kor file to the database
sync_file("./documento.kor")

# Query files by label
files = query_by_label("finance")
# ['/docs/report.pdf', '/docs/invoice.pdf']
```

Enable auto-sync in `config.yaml` to automatically update the database when using CLI commands.

## Features

- **Metadata Extraction** - Extract metadata from PDF, TXT, MD files using PyExifTool
- **Text Extraction** - Extract and summarize text content from supported files
- **LLM-based Labeling** - Classify files using LLM (Gemini, OpenAI, Groq, OpenRouter)
- **Sidecar Generation** - Generate YAML sidecar files (.kor) with full metadata
- **Database Sync** - Sync .kor files to SQLite database
- **Database Indexing** - SQLite backend for querying files by labels
- **Library API** - Use filekor as a Python library
- **CLI Interface** - Simple command-line interface with multiple commands

## Documentation

| Guide | Description |
|-------|-------------|
| [Installation](docs/installation.md) | Setup and installation |
| [Usage](docs/usage.md) | CLI commands reference (extract, sidecar, labels, sync, status) |
| [Taxonomy](docs/taxonomy.md) | Labels configuration |
| [LLM](docs/llm.md) | LLM setup |
| [Development](docs/development.md) | Developer guide |

## Project Structure

```
fileKor/
├── src/filekor/       # Source code
│   ├── cli.py        # CLI interface
│   ├── db.py         # Database module (SQLite)
│   ├── models.py     # Database models
│   ├── sidecar.py    # Sidecar model
│   ├── labels.py     # Labels module
│   └── llm.py       # LLM providers
├── docs/             # Documentation
├── test-files/        # Test files
├── tests/           # Test suite
└── README.md
```

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.