# Installation

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended)
- [exiftool](https://exiftool.org/) (required for metadata extraction)

### Install exiftool

```bash
# Windows
# Download from https://exiftool.org/

# Linux
sudo apt install libimage-exiftool-perl

# Mac
brew install exiftool
```

## Install with uv

```bash
# 1. Install uv (Windows)
winget install astral-sh.uv

# 1. Install uv (Linux/Mac)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Create virtual environment
uv venv

# 3. Activate (Windows)
.venv\Scripts\activate

# 3. Activate (Linux/Mac)
source .venv/bin/activate

# 4. Install package
uv pip install -e .
```

## Verify Installation

```bash
filekor --version
filekor --help
```

## Uninstall

```bash
# Remove virtual environment
rm -rf .venv

# Or if installed globally via pip
pip uninstall filekor
```