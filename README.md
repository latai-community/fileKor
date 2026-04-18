# fileKor

Local metadata engine that extracts, summarizes, classifies, and tags files using taxonomy-based labeling.

## Quick Start

```bash
# Install uv
winget install astral-sh.uv


git clone filekor 

cd filekor

# Setup
uv venv

# Windows
.venv\Scripts\activate
# MacOS/Linux
source venv/bin/activate

uv pip install -e .

# CLI Usage
filekor extract documento.pdf
filekor sidecar documento.pdf
filekor sidecar ./documentos --dir           # Process directory (generates merged.kor by default)
filekor sidecar ./documentos --dir --no-merge # Generate individual .kor files
filekor sidecar ./documentos --dir --db     # Use database to regenerate when available
filekor labels documento.pdf
filekor sync documento.kor          # Sync existing .kor to database
filekor merge ./directorio         # Merge multiple .kor files
filekor delete --path ./doc.pdf    # Delete by path
filekor delete --sha <hash>        # Delete by SHA256
```

## Library Usage

filekor can be used as a Python library for database-backed queries and search:

```python
from filekor.db import get_db, sync_file, search_files

# Get database instance (lazy singleton)
db = get_db()

# Sync a .kor file to the database
sync_file("./documento.kor")

# Search files by labels and content with scoring
results = search_files(
    labels=["finance", "2026"],
    query="budget report"
)
# Returns ranked results with relevance scores
```

Enable auto-sync in `config.yaml` to automatically update the database when using CLI commands.

## Features

### Core Features
- **Metadata Extraction** - Extract metadata from PDF, TXT, MD files using PyExifTool
- **Text Extraction** - Extract and summarize text content from supported files
- **Sidecar Generation** - Generate YAML sidecar files (.kor) with full metadata
- **Taxonomy Labels** - LLM-based classification with custom taxonomy support

### LLM Providers
- **Google Gemini** - Native Gemini API support
- **OpenAI** - GPT-4o, GPT-4o-mini support
- **Groq** - Fast inference with Llama models
- **OpenRouter** - Access to 200+ free models
- **Mock Provider** - Testing without API calls

### Database & Search
- **SQLite Database** - Index all .kor metadata
- **Full-Text Search** - FTS5 for fast filename/metadata search
- **Multi-Label Search** - OR logic for filtering by multiple labels
- **Relevance Scoring** - Configurable weights for search ranking
- **Auto-Sync** - Automatic database updates from CLI

### Interfaces
- **CLI** - Complete command-line interface
- **Library API** - Python API for integration
- **100 Tests** - Comprehensive test coverage

## Documentation

| Guide | Description |
|-------|-------------|
| [Installation](docs/installation.md) | Setup and installation |
| [Usage](docs/usage.md) | CLI commands reference |
| [Library](docs/library.md) | Python Library API with code examples |
| [Taxonomy](docs/taxonomy.md) | Labels and taxonomy configuration |
| [LLM](docs/llm.md) | LLM provider setup (Gemini, OpenAI, Groq, OpenRouter) |
| [Development](docs/development.md) | Development and testing guide |

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