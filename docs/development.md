# Development

## Setup

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install with dev dependencies
uv pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_labels.py -v

# Run with coverage
pytest tests/ --cov
```

## Running CLI

```bash
# Using filekor command (if installed)
filekor extract test-files/document.pdf
filekor sidecar test-files/document.pdf
filekor labels test-files/document.pdf

# Or using Python module
python -m filekor extract test-files/document.pdf
python -m filekor sidecar test-files/document.pdf
python -m filekor labels test-files/document.pdf
```

## Project Structure

```
fileKor/
├── src/filekor/
│   ├── adapters/          # Adapter pattern implementations
│   │   ├── base.py      # MetadataAdapter abstract class
│   │   └── exiftool.py  # PyExifToolAdapter
│   ├── cli.py          # CLI interface with commands
│   ├── sidecar.py     # Sidecar YAML model
│   ├── labels.py      # Taxonomy labels with synonyms
│   ├── llm.py       # LLM provider abstraction
│   └── extractors/    # Text extraction modules
├── docs/               # Documentation
├── test-files/          # Test files
├── tests/             # Test suite
├── pyproject.toml      # Package configuration
└── README.md
```

## Adding Commands

Commands are defined in `src/filekor/cli.py` using Click:

```python
import click

@click.command()
@click.argument("path")
def my_command(path):
    """Command description."""
    click.echo(f"Processing: {path}")
```

## Adding Tests

Place tests in `tests/` directory:

```python
def test_my_feature():
    # Test code here
    assert expected == actual
```

## Requirements

- Python 3.11+
- Black for formatting
- Ruff for linting
- Pytest for testing

## License

Apache License 2.0 - See [LICENSE](../LICENSE) file for details.