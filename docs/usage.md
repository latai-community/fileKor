# Usage

**Important:** Always activate the virtual environment before using filekor.

```bash
# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate
```

---

## Commands

| Command | Description |
|---------|-------------|
| `extract` | Extract text content from supported files |
| `sidecar` | Generate .kor sidecar file with metadata |
| `labels` | Add taxonomy labels to a file |
| `sync` | Sync .kor files to database |
| `status` | Show status of .kor files |
| `process` | Legacy - extract metadata |

---

## Extract

Extract text content from PDF, TXT, or MD files.

```bash
filekor extract <path>

# Extract to file
filekor extract <path> -o <output>

# Process directory recursively
filekor extract ./documentos/ --dir

# Show help
filekor extract --help
```

**Options:**
| Option | Description |
|--------|-------------|
| `-o`, `--output` | Output file path |
| `-d`, `--dir` | Process directory instead of single file |

---

## Sidecar

Generate a `.kor` YAML sidecar file with metadata.

```bash
filekor sidecar <path>

# Custom output path
filekor sidecar <path> -o <output>

# Process directory recursively
filekor sidecar ./documentos/ --dir

# Force regeneration (ignore existing .kor)
filekor sidecar <path> --no-cache

# Custom config.yaml for LLM (if needed in future)
filekor sidecar <path> -c <config.yaml>

# Verbose output
filekor sidecar <path> --verbose

# Watch mode for real-time progress
filekor sidecar ./documentos/ --dir --watch
```

**Options:**
| Option | Description |
|--------|-------------|
| `-o`, `--output` | Output .kor file path |
| `--no-cache` | Force regeneration |
| `-c`, `--config` | Custom config.yaml path |
| `-v`, `--verbose` | Show detailed output |
| `-d`, `--dir` | Process directory instead of single file |
| `--workers` | Number of parallel workers (from config.yaml) |
| `--watch` | Enable event emitter for real-time progress |

**Output:** Creates `{filename}.kor` in same directory. For directory: creates `.filekor/` subdirectory with .kor files.

---

## Labels

Add taxonomy labels to a file using LLM. Creates or updates `.kor` file.

```bash
filekor labels <path>

# With custom config.yaml for LLM
filekor labels <path> --llm-config <config.yaml>

# With custom taxonomy (labels.properties)
filekor labels <path> -c <labels.properties>

# Process directory recursively
filekor labels ./documentos/ --dir

# Watch mode for real-time progress
filekor labels ./documentos/ --dir --watch
```

**Options:**
| Option | Description |
|--------|-------------|
| `-c`, `--config` | Custom labels.properties path |
| `--llm-config` | Custom config.yaml path |
| `-d`, `--dir` | Process directory instead of single file |
| `--workers` | Number of parallel workers (from config.yaml) |
| `--watch` | Enable event emitter for real-time progress |

**Behavior:**
- If `.kor` exists: loads it and adds/replaces labels
- If `.kor` does NOT exist: creates new `.kor` with file info and labels
- LLM is required (will fail if not configured)

**Output Example:**
```
documentation
testing
code
Loading existing: documento.kor
Saved: documento.kor
```

---

## Status

Show status of .kor files for a file or directory.

```bash
filekor status <path>

# Show status for directory
filekor status ./documentos/ --dir

# Watch mode for real-time updates
filekor status ./documentos/ --dir --watch
```

**Options:**
| Option | Description |
|--------|-------------|
| `-d`, `--dir` | Show status for directory instead of single file |
| `--watch` | Enable watch mode for real-time updates |

---

## Process (Legacy)

Legacy command for metadata extraction.

```bash
filekor process <path>
filekor process <path> --output <output>
```

**Options:**
| Option | Description |
|--------|-------------|
| `-o`, `--output` | Output file path |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | ExifTool not found or unsupported file |
| 2 | File not found |
| 3 | Permission denied |

---

## Examples

### Full workflow

```bash
# 1. Generate sidecar (without labels)
filekor sidecar documento.pdf --no-cache
# Output: documento.kor (labels: null)

# 2. Add labels
filekor labels documento.pdf
# Output: documento.kor (labels: [documentation, testing])

# 3. View the .kor file
cat documento.kor
```

### With custom configs

```bash
# Use custom LLM config
filekor labels documento.pdf --llm-config /path/to/config.yaml

# Use custom taxonomy
filekor labels documento.pdf -c /path/to/labels.properties

# Verbose mode to see what's happening
filekor sidecar documento.pdf --verbose
filekor labels documento.pdf --verbose
```

### Directory processing

```bash
# Process entire directory
filekor sidecar ./documentos/ --dir

# With custom workers
filekor sidecar ./documentos/ --dir --workers 8

# Watch mode for real-time progress
filekor sidecar ./documentos/ --dir --watch

# Add labels to all files
filekor labels ./documentos/ --dir

# Check status of processed files
filekor status ./documentos/ --dir
```

---

## Database

filekor includes a SQLite database for indexing and querying files by labels.

### Configuration

Enable auto-sync in `config.yaml`:

```yaml
llm:
  provider: gemini
  api_key: ${GEMINI_API_KEY}
  model: gemini-1.5-flash
  auto_sync: true  # Auto-sync to database on sidecar/labels commands
```

When `auto_sync: true`, the database at `~/.filekor/index.db` is automatically updated when using `filekor sidecar` or `filekor labels` commands.

### Library Usage

Use filekor as a Python library for database queries:

```python
from filekor.db import get_db, sync_file, query_by_label

# Get database instance (lazy singleton - created on first call)
db = get_db()

# Manually sync a .kor file
sync_file("./documento.kor")

# Query files by label
files = query_by_label("finance")
# ['/docs/report.pdf', '/docs/invoice.pdf']

# Query all files
all_files = db.query_all()
```

---

## Sync

Synchronize existing `.kor` files to the database without regenerating or re-labeling them.

```bash
# Sync a single .kor file
filekor sync document.kor

# Sync all .kor files in a directory
filekor sync ./docs/ --dir

# Sync with verbose output
filekor sync ./docs/ --dir --verbose
```

**Options:**
| Option | Description |
|--------|-------------|
| `-d`, `--dir` | Sync all .kor files in directory |
| `-v`, `--verbose` | Show detailed output |

**Use Cases:**
- Sync existing .kor files to a new database
- Re-sync after database corruption
- Bulk sync files created before auto_sync was enabled

### Database Schema

The SQLite database includes:

- **files** - File metadata (path, hash, timestamps)
- **labels** - Associated labels with confidence scores
- **files_fts** - Full-text search index (FTS5)
- **schema_version** - Migration tracking

---

## Library API

filekor can be used as a Python library for programmatic access to the database.

### Quick Start

```python
from filekor.db import get_db, sync_file, search_files

# Get database instance
db = get_db()

# Sync a .kor file to the database
sync_file("./document.kor")

# Search files by labels and content
results = search_files(
    labels=["finance", "2026"],
    query="budget report"
)
```

### Available Functions

| Function | Description |
|----------|-------------|
| `get_db()` | Get singleton database instance |
| `sync_file(kor_path)` | Sync .kor file to database |
| `query_by_label(label)` | Query files by single label |
| `query_by_labels(labels)` | Query files by multiple labels (OR) |
| `query_all()` | Get all files with labels |
| `search_content(query)` | Full-text search in filename + metadata |
| `search_files(labels, query)` | Combined search with scoring |

### Search API

The search API supports filtering by labels and full-text search:

```python
from filekor.db import search_files, query_by_labels, search_content

# 1. Query by multiple labels (OR logic)
results = query_by_labels(["finance", "2026"])
# Returns files with label "finance" OR "2026"

# 2. Full-text search (FTS5)
results = search_content("provider costs", limit=10)
# Searches in filename and .kor metadata

# 3. Combined search with scoring
results = search_files(
    labels=["finance", "2026"],
    query="provider costs",
    weights={
        "label_match": 0.50,
        "filename_match": 0.30,
        "kor_content_match": 0.20
    }
)

# Result format:
# {
#     "file_path": "./docs/report.pdf",
#     "name": "report.pdf",
#     "labels": ["finance", "2026", "budget"],
#     "score": 0.85,
#     "score_breakdown": {
#         "label_match": 1.0,
#         "filename_match": 0.5,
#         "kor_content_match": 0.8
#     }
# }
```

### Scoring System

The `search_files()` function calculates relevance scores:

| Factor | Weight | Description |
|--------|--------|-------------|
| label_match | 0.50 | Files matching requested labels |
| filename_match | 0.30 | Query matches filename |
| kor_content_match | 0.20 | Query matches .kor metadata |

Weights are configurable via the `weights` parameter.