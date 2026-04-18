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
| `list` | List SHA256 hashes and file names |
| `delete` | Delete .kor files and/or database records |
| `merge` | Merge multiple .kor files into one |
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

## List

List SHA256 hashes and file names for all `.kor` files in a directory.

```bash
# List all .kor files in directory
filekor list ./documentos

# Output as JSON
filekor list ./documentos --json

# Output as CSV
filekor list ./documentos --csv

# Output only SHA256 hashes (useful for pipes)
filekor list ./documentos --sha-only

# Filter by file extension
filekor list ./documentos --ext pdf

# Include entries from merged.kor files
filekor list ./documentos --include-merged
```

**Options:**
| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `--csv` | Output as CSV |
| `--sha-only` | Output only SHA256 hashes |
| `--ext` | Filter by file extension (pdf, md, txt) |
| `--include-merged` | Include entries from merged.kor files |

---

## Delete

Delete `.kor` files and/or database records by SHA256 hash.

```bash
# Delete by SHA256 hash (from both DB and files)
filekor delete ./documentos --sha <hash>

# Delete by file path (calculates SHA internally)
filekor delete ./documentos --path ./documento.pdf

# Delete from multiple hashes in a file
filekor delete ./documentos --input hashes.txt

# Delete only from database
filekor delete ./documentos --sha <hash> --db

# Delete only .kor files (not from database)
filekor delete ./documentos --sha <hash> --file

# Dry run - show what would be deleted
filekor delete ./documentos --sha <hash> --dry-run

# Skip confirmation prompt
filekor delete ./documentos --sha <hash> --force

# Limit search depth
filekor delete ./documentos --sha <hash> --max-depth 2

# Don't search subdirectories
filekor delete ./documentos --sha <hash> --no-recursive
```

**Options:**
| Option | Description |
|--------|-------------|
| `--sha` | SHA256 hash of the file to delete |
| `--path` | Path to file (SHA256 calculated internally) |
| `--input` | File containing SHA256 hashes (one per line) |
| `--db` | Delete only from database |
| `--file` | Delete only .kor files (not from database) |
| `--all` | Delete from both database and .kor files |
| `--dry-run` | Show what would be deleted without actually deleting |
| `--force` | Skip confirmation prompt |
| `--no-recursive` | Do not search in subdirectories |
| `--max-depth` | Maximum directory depth to search |
| `-v`, `--verbose` | Show detailed output |

---

## Merge

Merge multiple `.kor` files into a single aggregated `.kor` file.

```bash
# Merge all .kor files in .filekor/ directory
filekor merge ./documentos

# Keep original .kor files after merge
filekor merge ./documentos --no-erase

# Specify output path
filekor merge ./documentos -o ./output.kor
```

**Options:**
| Option | Description |
|--------|-------------|
| `-o`, `--output` | Output file for merged .kor |
| `--no-erase` | Keep original .kor files after merge |

---

## Library API

filekor can be used as a Python library for programmatic access.

For complete library documentation including:
- Database API (get_db, sync_file, search_files, etc.)
- Sidecar API (create, load, update labels)
- Labels API (suggest_labels, configuration)
- Status API (file and directory status)
- Code examples and snippets

**See: [Library API Reference](library.md)**