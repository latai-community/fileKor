# fileKor

Local metadata engine that extracts, summarizes, classifies, and tags files using taxonomy-based labeling.

## Index

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Taxonomy Configuration](#taxonomy-configuration)
- [Project Structure](#project-structure)
- [Exit Codes](#exit-codes)
- [Development](#development)
- [License](#license)

---

## Features

- **Metadata Extraction** - Extract metadata from PDF, TXT, MD files using PyExifTool
- **Text Extraction** - Extract and summarize text content from supported files
- **Taxonomy-based Labeling** - Classify files based on path patterns and synonyms
- **Sidecar Generation** - Generate YAML sidecar files (.kor) with full metadata
- **CLI Interface** - Simple command-line interface with multiple commands

## Installation

### 1. Install uv (optional but recommended)

```bash
# Windows
winget install astral-sh.uv

# Linux/Mac
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Setup environment

```bash
# Create virtual environment
uv venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install package in editable mode
uv pip install -e .

# Requirements: exiftool must be installed on your system
# - Windows: Download from https://exiftool.org/
# - Linux: sudo apt install libimage-exiftool-perl
# - Mac: brew install exiftool
```

## Usage

**Importante:** Siempre activá el entorno virtual antes de usar filekor:

```bash
# En el directorio del proyecto
source .venv/bin/activate  # Linux/Mac
# o
.venv\Scripts\activate    # Windows

# Luego ejecutá los comandos
filekor extract documento.pdf

# Extract to a file
filekor extract documento.pdf -o extracted.txt

# Generate sidecar YAML file (.kor)
filekor sidecar documento.pdf

# Generate sidecar with custom output path
filekor sidecar documento.pdf -o metadata.kor

# Suggest labels for a file path
filekor labels documento.pdf

# Show labels with confidence scores
filekor labels documento.pdf --show-confidence

# Process (legacy command - extracts metadata)
filekor process documento.pdf --output metadata.kor

# Show help
filekor --help
```

### Available Commands

| Command | Description |
|---------|-------------|
| `extract` | Extract text content from supported files (PDF, TXT, MD) |
| `sidecar` | Generate .kor sidecar file with metadata, content, and labels |
| `labels` | Suggest taxonomy labels based on file path |
| `process` | Extract metadata from file (legacy command) |

---

## Taxonomy Configuration

Labels are configured via a `labels.properties` file. The tool searches in this order:

1. Custom path (via `--config` flag)
2. `labels.properties` in current directory
3. `.filekor/labels.properties`
4. `~/.filekor/labels.properties`
5. Built-in defaults

### Format

```properties
# Labels configuration
# Format: LABEL=synonym1,synonym2,synonym3

finance=economy,budget,cost,costs,money,financial,billing,invoice
contract=agreement,contract,terms,conditions,legal
legal=law,compliance,gdpr,privacy,policy,regulation
architecture=design,architecture,blueprint,structure
specification=spec,specs,requirement,requirements
documentation=docs,documentation,manual,guide,readme
```

### Labels Command

```bash
# Show suggested labels for a path
filekor labels /path/to/finance/report.pdf

# With confidence scores
filekor labels /path/to/finance/report.pdf --show-confidence

# Using custom config
filekor labels /path/to/doc.pdf -c custom-labels.properties
```

### LLM-based Labels (Optional)

fileKor can use an LLM (Google Gemini) to extract labels based on file content instead of just path matching.

#### Setup

1. Create config file at `~/.filekor/config.yaml`:

```yaml
filekor:
  llm:
    enabled: true
    provider: gemini
    api_key: ${GEMINI_API_KEY}  # Set GOOGLE_API_KEY env var
    model: gemini-2.0-flash
    max_content_chars: 1500
```

2. Set environment variable:

```bash
export GOOGLE_API_KEY="your-api-key-here"
```

#### Usage

```bash
# Use LLM for label extraction (requires config with enabled: true)
filekor sidecar documento.pdf

# Force LLM on (override config)
filekor sidecar documento.pdf --llm

# Force path-based only
filekor sidecar documento.pdf --no-llm

# Labels command also supports LLM
filekor labels documento.pdf --llm
```

#### How it works

- When LLM is enabled, fileKor sends the first 1500 characters of file content to Gemini
- Gemini returns comma-separated labels based on the taxonomy in `labels.properties`
- If LLM fails or is not configured, falls back to path-based matching
- Labels in sidecar include `source: llm` or `source: path` to indicate origin

---

## Project Structure

```
fileKor/
├── src/filekor/
│   ├── adapters/          # Adapter pattern implementations
│   │   ├── base.py        # MetadataAdapter abstract class
│   │   └── exiftool.py    # PyExifToolAdapter
│   ├── cli.py            # CLI interface with commands
│   ├── sidecar.py        # Sidecar YAML model
│   ├── labels.py         # Taxonomy labels with synonyms
│   └── extractors/       # Text extraction modules
├── labels.properties     # Default labels configuration
├── test-files/           # Test files
├── pyproject.toml        # Package configuration
└── README.md
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | ExifTool not found or unsupported file |
| 2 | File not found |
| 3 | Permission denied |

## Development

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install with dev dependencies (if added)
uv pip install -e ".[dev]"

# Run tests
pytest tests/

# Run CLI commands
filekor extract test-files/document.pdf
filekor sidecar test-files/document.pdf
filekor labels test-files/document.pdf

# Or use python module directly
python -m filekor sidecar test-files/document.pdf
```

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.