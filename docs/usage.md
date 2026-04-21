# Usage

**Important:** Always activate the virtual environment before using filekor.

```bash
# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate
```

---

## Contents

| Section | Description |
|---------|-------------|
| [Commands](#commands) | Overview of all available commands |
| [Extract](#extract) | Extract text content from files |
| [Sidecar](#sidecar) | Generate .kor sidecar files with metadata |
| [Labels](#labels) | Add taxonomy labels using LLM |
| [Summary](#summary) | Generate summaries using LLM |
| [Status](#status) | Show status of .kor files |
| [List](#list) | List .kor files with format options |
| [Merge](#merge) | Merge multiple .kor files into one |
| [Delete](#delete) | Delete .kor files and database records |
| [Sync](#sync) | Sync .kor files to database |
| [Database](database.md) | SQLite database configuration and queries |
| [Exit Codes](#exit-codes) | CLI exit code reference |
| [Examples](#examples) | Usage examples and workflows |
| [Library API](#library-api) | Python library reference |

---

## Commands

| Command | Description |
|---------|-------------|
| `extract` | Extract text content from supported files |
| `sidecar` | Generate .kor sidecar file with metadata |
| `labels` | Add taxonomy labels to a file |
| `summary` | Generate summaries using LLM |
| `db` | Show database configuration and statistics |
| `sync` | Sync .kor files to database |
| `status` | Show status of .kor files |
| `list` | List SHA256 hashes and file names |
| `delete` | Delete .kor files and/or database records |
| `merge` | Merge multiple .kor files into one |

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

## Summary

Generate summaries for files using LLM. Creates or updates `.kor` file.

```bash
# Generate both short and long summaries (default)
filekor summary <path>

# Generate short summary only
filekor summary <path> --short

# Generate long summary only
filekor summary <path> --long

# Override max characters sent to LLM
filekor summary <path> --max-chars 3000

# With custom config.yaml for LLM
filekor summary <path> --llm-config <config.yaml>

# Process directory recursively
filekor summary ./documentos/ --dir

# Watch mode for real-time progress
filekor summary ./documentos/ --dir --watch
```

**Options:**
| Option | Description |
|--------|-------------|
| `--short` | Generate short summary only |
| `--long` | Generate long summary only |
| `--max-chars` | Max characters to send to LLM (overrides config) |
| `--llm-config` | Custom config.yaml path |
| `-d`, `--dir` | Process directory instead of single file |
| `--workers` | Number of parallel workers (from config.yaml) |
| `--watch` | Enable event emitter for real-time progress |

**Behavior:**
- If `.kor` exists: loads it and updates summary (overwrites existing)
- If `.kor` does NOT exist: creates new `.kor` with file info and summary
- By default generates **both** short and long summaries
- LLM is required (will fail if not configured)

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

```bash
filekor db              # Summary: path, schema, files, labels, size
filekor db files        # List all indexed files
filekor db labels       # List all labels with file counts
filekor db search <q>   # Full-text search
filekor db show <hash>  # Show file details by SHA256
```

Full documentation: [database.md](database.md)

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
# List all .kor files (includes merged.kor by default)
filekor list ./documentos

# Output as JSON (full hashes)
filekor list ./documentos -f json

# Output as CSV (full hashes)
filekor list ./documentos -f csv

# Output only SHA256 hashes (useful for pipes)
filekor list ./documentos -f sha

# Filter by file extension
filekor list ./documentos --ext pdf

# Exclude merged.kor entries (show only individual .kor files)
filekor list ./documentos --no-merged
```

**Options:**
| Option | Description |
|--------|-------------|
| `-f`, `--format` | Output format (default: `text`) |
| `--ext` | Filter by file extension (pdf, md, txt) |
| `--no-merged` | Exclude entries from merged.kor files |

**Formats:**
| Format | Output | Hash |
|--------|--------|------|
| `text` | Name + type, human-readable | truncated (16 chars + `...`) |
| `json` | Structured JSON | full |
| `csv` | CSV with header | full |
| `sha` | One hash per line | full |

**Important:** By default, `filekor list` includes entries from `merged.kor` files (generated by `filekor sidecar --dir`). The `text` format truncates hashes to 16 characters for readability. Use `-f json`, `-f csv`, or `-f sha` for full hashes.

**Example:**
```bash
# Shows all entries from merged.kor (default behavior)
filekor list ./documentos

# Exclude merged entries, show only standalone .kor files
filekor list ./documentos --no-merged

# Full hashes in CSV format
filekor list ./documentos -f csv
```

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