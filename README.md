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

# Use
filekor extract documento.pdf
filekor sidecar documento.pdf
filekor labels documento.pdf
```

## Features

- **Metadata Extraction** - Extract metadata from PDF, TXT, MD files using PyExifTool
- **Text Extraction** - Extract and summarize text content from supported files
- **LLM-based Labeling** - Classify files using LLM (Gemini) with content analysis
- **Sidecar Generation** - Generate YAML sidecar files (.kor) with full metadata
- **CLI Interface** - Simple command-line interface with multiple commands

## Documentation

| Guide | Description |
|-------|-------------|
| [Installation](docs/installation.md) | Setup and installation |
| [Usage](docs/usage.md) | CLI commands reference |
| [Taxonomy](docs/taxonomy.md) | Labels configuration |
| [LLM](docs/llm.md) | LLM setup |
| [Development](docs/development.md) | Developer guide |

## Project Structure

```
fileKor/
├── src/filekor/       # Source code
│   ├── cli.py        # CLI interface
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