# Database

filekor includes a SQLite database for indexing and querying files by labels.

---

## Commands

```bash
filekor db              # Summary: path, schema, files, labels, size
filekor db files        # List all indexed files with path, hash, extension
filekor db labels       # List all labels with file counts
filekor db search <q>   # Full-text search (FTS5)
filekor db show <hash>  # Show file details by SHA256 prefix
```

### `filekor db` (summary)

Show database configuration and statistics:

```bash
filekor db
filekor db -c /path/to/config.yaml   # custom config
```

Output:
```
Database: C:\Users\joseb\.filekor\index.db
Exists:   yes
Schema:   v2
Files:    3
Labels:   6
Size:     52.0 KB
```

### `filekor db files`

List all indexed files:

```bash
filekor db files
```

Output:
```
SHA256              EXT   PATH
87319164c0efd5f8... pdf   test-files\PDF_metadata.pdf
4d1f8aa3717fe40a... md    test-files\sample.md
7097eab71c2dceea... txt   test-files\sample.txt

Total: 3 files
```

### `filekor db labels`

List all labels with file counts, ordered by popularity:

```bash
filekor db labels
```

Output:
```
LABEL          FILES
documentation  3
analysis       2
testing        2
code           1
data           1
python         1

Total: 6 unique labels
```

### `filekor db search <query>`

Full-text search over file names, metadata, and summaries:

```bash
filekor db search "sample"
filekor db search "contract finance"
```

Output:
```
SHA256              NAME       PATH
4d1f8aa3717fe40a... sample.md  test-files\sample.md
7097eab71c2dceea... sample.txt test-files\sample.txt

Total: 2 results
```

Uses SQLite FTS5 with porter stemming — supports partial matches, boolean operators (`AND`, `OR`, `NOT`).

### `filekor db show <hash>`

Show details for a file by SHA256 hash (prefix is enough):

```bash
filekor db show 87319164c0efd5f8
```

Output:
```
File:      PDF_metadata.pdf
Path:      test-files\PDF_metadata.pdf
Extension: pdf
Size:      191.7 KB
SHA256:    87319164c0efd5f8...
Modified:  2026-04-15 03:30:08
Labels:    analysis, data, documentation, testing
```

---

## Configuration

Configure the database path and auto-sync in `config.yaml`:

```yaml
filekor:
  db:
    path: ~/.filekor/index.db    # configurable, default: ~/.filekor/index.db
  llm:
    enabled: true
    provider: gemini
    api_key: ${GEMINI_API_KEY}
    model: gemini-1.5-flash
    auto_sync: true
  workers: 4
```

- `db.path`: Path to the SQLite database file. Supports `~` and relative paths.
- `llm.auto_sync`: When `true`, the database is automatically updated when using `filekor sidecar`, `filekor labels`, or `filekor summary` commands.

---

## Library Usage

Use filekor as a Python library for database queries:

```python
from filekor.db import (
    get_db, sync_file, query_by_label,
    query_all, query_labels_with_counts, search_content, get_file_by_hash,
)

# Get database instance (lazy singleton - created on first call)
db = get_db()

# Manually sync a .kor file
sync_file("./documento.kor")

# Query files by label
files = query_by_label("finance")
# ['/docs/report.pdf', '/docs/invoice.pdf']

# Query all files with labels
all_files = query_all()

# Labels with counts
labels = query_labels_with_counts()
# [{'label': 'finance', 'file_count': 2}, ...]

# Full-text search
results = search_content("contract")
# [{'file_path': '/docs/contract.pdf', 'name': 'contract.pdf', ...}]

# Get file by hash
file_info = get_file_by_hash("87319164c0efd5f8...")
```

---

## Schema

### `files` table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| kor_path | TEXT | Path to .kor file (unique) |
| file_path | TEXT | Path to source file |
| name | TEXT | Filename |
| extension | TEXT | File extension |
| size_bytes | INTEGER | File size |
| modified_at | TIMESTAMP | Last modification |
| hash_sha256 | TEXT | SHA256 hash |
| metadata_json | TEXT | JSON metadata |
| summary_short | TEXT | Short summary (LLM) |
| summary_long | TEXT | Long summary (LLM) |

### `labels` table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| file_id | INTEGER | FK to files |
| label | TEXT | Label name |
| confidence | REAL | Confidence score |
| source | TEXT | Source (llm, manual) |

### `files_fts` (FTS5 virtual table)

Full-text search index over `name`, `metadata_json`, `summary_short`, `summary_long`.
