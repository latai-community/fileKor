# fileKor

Local metadata engine that extracts, summarizes, classifies, and tags files.

## Index

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Exit Codes](#exit-codes)
- [Development](#development)
- [License](#license)

---

## Features

- **Metadata Extraction** - Extract metadata from PDF files using PyExifTool
- **Sidecar Generation** - Generate JSON sidecar files with extracted metadata
- **CLI Interface** - Simple command-line interface

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

```bash
# Process a PDF and extract metadata (print to stdout)
filekor process documento.pdf

# Generate sidecar JSON file
filekor process documento.pdf --output metadata.kor

# Show help
filekor --help
```

### Available Commands

| Command | Description |
|---------|-------------|
| `process` | Extract metadata from PDF and optionally save to sidecar |

---

## Project Structure

```
fileKor/
├── src/filekor/
│   ├── adapters/          # Adapter pattern implementations
│   │   ├── base.py        # MetadataAdapter abstract class
│   │   └── exiftool.py    # PyExifToolAdapter
│   ├── cli.py            # CLI interface
│   └── sidecar.py        # Sidecar JSON model
├── test-files/           # Test files
├── pyproject.toml        # Package configuration
└── README.md
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | ExifTool not found |
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

# Run CLI
python -m filekor process test-files/PDF_metadata.pdf

# Or use the installed command
filekor process test-files/PDF_metadata.pdf
```

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.