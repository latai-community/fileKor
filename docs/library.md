# Library API Reference

filekor can be used as a Python library for programmatic access to file metadata extraction, sidecar generation, database operations, batch processing, and more.

## Index

| Section | Description |
|---------|-------------|
| [Installation](#installation) | pip install or build from source |
| [Quick Start](#quick-start) | Minimal working example |
| [Data Models Reference](#data-models-reference) | Core data structures (FileInfo, Sidecar fields, DB models, etc.) |
| [Database API](#database-api) | SQLite storage, search, CRUD (12 functions) |
| [Sidecar API](#sidecar-api) | Create, load, export .kor sidecar files |
| [Labels API](#labels-api) | Taxonomy config and LLM-based label suggestions |
| [Summary API](#summary-api) | LLM content summarization |
| [List API](#list-api) | Query and list .kor files in directories |
| [Merge API](#merge-api) | Combine multiple .kor files |
| [Delete API](#delete-api) | Delete .kor files and DB records |
| [Processor API](#processor-api) | Parallel directory processing engine |
| [Events API](#events-api) | Event system for progress and watch mode |
| [Status API](#status-api) | Check file and directory processing status |
| [Hasher](#hasher) | SHA256 file hashing |
| [Exceptions & Error Handling](#exceptions--error-handling) | What each function raises |
| [Library vs CLI](#library-vs-cli) | When to use each interface |
| [Complete Example](#complete-example) | End-to-end workflow |
| [Configuration](#configuration) | config.yaml reference |
| [API Reference Summary](#api-reference-summary) | Quick lookup table of all 32 symbols |

## Installation

```bash
pip install filekor
```

Or install from source:

```bash
git clone https://github.com/latai-community/filekor.git
cd filekor
pip install -e .
```

## Quick Start

```python
from filekor import (
    Sidecar, get_db, sync_file, search_files,
    suggest_labels, process_directory, list_kor_files,
)

# 1. Process a directory (parallel, with LLM labels if configured)
results = process_directory("./docs")

# 2. Sync results to the database
db = get_db()
for r in results:
    if r.success and r.output_path:
        sync_file(str(r.output_path))

# 3. Search files by labels and content
matches = search_files(labels=["finance"], query="budget report")
for m in matches:
    print(f"{m['name']}: {m['score']}")
```

---

## Data Models Reference

These are the core data structures returned and used throughout the library.

### FileInfo

File identification metadata. Part of every `Sidecar`.

| Field | Type | Description |
|-------|------|-------------|
| `path` | `str` | Absolute path to the source file |
| `name` | `str` | File name with extension |
| `extension` | `str` | File extension (without dot) |
| `size_bytes` | `int` | File size in bytes |
| `modified_at` | `datetime` | Last modification timestamp (UTC) |
| `hash_sha256` | `str` | SHA256 hash of the file contents |

### FileMetadata

Optional extracted metadata (from ExifTool).

| Field | Type | Description |
|-------|------|-------------|
| `author` | `Optional[str]` | Document author |
| `created` | `Optional[datetime]` | Creation date |
| `pages` | `Optional[int]` | Page count |

### Content

Optional content information from text extraction.

| Field | Type | Description |
|-------|------|-------------|
| `language` | `Optional[str]` | Detected language code (e.g., "en") |
| `word_count` | `Optional[int]` | Word count |
| `page_count` | `Optional[int]` | Page count |

### FileSummary

Optional LLM-generated summary.

| Field | Type | Description |
|-------|------|-------------|
| `short` | `Optional[str]` | 1-2 sentence summary |
| `long` | `Optional[str]` | Detailed summary |

### FileLabels

Labels assigned to a file.

| Field | Type | Description |
|-------|------|-------------|
| `suggested` | `List[str]` | List of label names |
| `source` | `Literal["llm"]` | Source of the labels |

### SummaryResult

Result of `generate_summary()`.

| Field | Type | Description |
|-------|------|-------------|
| `short` | `Optional[str]` | Short summary |
| `long` | `Optional[str]` | Long summary |

### ProcessResult

Result of processing a single file.

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | `Path` | Original file path |
| `success` | `bool` | Whether processing succeeded |
| `output_path` | `Optional[Path]` | Path to generated .kor file |
| `error` | `Optional[str]` | Error message if failed |
| `labels` | `Optional[List[str]]` | Labels generated (if any) |

### FileStatus

Status information for a single file.

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | `Path` | Path to the source file |
| `kor_path` | `Path` | Expected path to .kor sidecar |
| `exists` | `bool` | Whether .kor file exists and is valid |
| `sidecar` | `Optional[Sidecar]` | Loaded Sidecar (if exists) |
| `error` | `Optional[str]` | Error message if loading failed |

### DirectoryStatus

Status information for a directory.

| Field | Type | Description |
|-------|------|-------------|
| `directory` | `Path` | Directory path |
| `total_files` | `int` | Total supported files found |
| `kor_files` | `int` | Files with valid .kor sidecars |
| `files_without_kor` | `List[Path]` | Files missing .kor sidecars |
| `file_statuses` | `List[FileStatus]` | Per-file status list |

### DBFile

Database record for a file.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `Optional[int]` | Primary key |
| `kor_path` | `str` | Path to .kor file (unique) |
| `file_path` | `str` | Path to source file |
| `name` | `str` | File name |
| `extension` | `Optional[str]` | File extension |
| `size_bytes` | `Optional[int]` | File size |
| `modified_at` | `Optional[datetime]` | Last modified |
| `hash_sha256` | `Optional[str]` | SHA256 hash |
| `metadata_json` | `Optional[str]` | JSON metadata string |
| `summary_short` | `Optional[str]` | Short summary |
| `summary_long` | `Optional[str]` | Long summary |
| `created_at` | `Optional[datetime]` | Record creation time |
| `updated_at` | `Optional[datetime]` | Record update time |

### DBLabel

Database record for a label.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `Optional[int]` | Primary key |
| `file_id` | `int` | Foreign key to files table |
| `label` | `str` | Label name |
| `confidence` | `Optional[float]` | Confidence score (0-1) |
| `source` | `Optional[str]` | Source (e.g., "llm", "manual") |
| `created_at` | `Optional[datetime]` | Creation time |

### DBCollection

Database record for a collection (future expansion).

| Field | Type | Description |
|-------|------|-------------|
| `id` | `Optional[int]` | Primary key |
| `name` | `str` | Collection name |
| `query` | `Optional[str]` | Query/filter criteria |
| `created_at` | `Optional[datetime]` | Creation time |
| `updated_at` | `Optional[datetime]` | Update time |

---

## Database API

SQLite-backed storage with full-text search capabilities.

### get_db()

Get the singleton database instance. Thread-safe lazy initialization.

```python
from filekor.db import get_db

# Default: ~/.filekor/index.db
db = get_db()

# Custom path
from pathlib import Path
db = get_db(path=Path("./my-project/index.db"))
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `Optional[Path]` | `None` | Custom database path. Uses `~/.filekor/index.db` if None. |

**Returns:** `Database` instance.

---

### sync_file()

Synchronize a .kor file to the database. Parses the sidecar and inserts/updates the record.

```python
from filekor.db import sync_file

file_ids = sync_file("./docs/report.pdf.kor")
print(f"Synced with IDs: {file_ids}")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `kor_path` | `str` | required | Path to .kor sidecar file |
| `db` | `Optional[Database]` | `None` | Database instance (uses singleton if None) |

**Returns:** `int` — file ID of the inserted/updated record.

---

### query_by_label()

Query files by a single label.

```python
from filekor.db import query_by_label

files = query_by_label("finance")
# Returns: ['./docs/budget.pdf', './docs/invoice.pdf']
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | required | Label name to search for |
| `db` | `Optional[Database]` | `None` | Database instance |

**Returns:** `List[str]` — file paths matching the label.

---

### query_by_labels()

Query files by multiple labels using OR logic.

```python
from filekor.db import query_by_labels

results = query_by_labels(["finance", "2024", "invoice"])
for result in results:
    print(f"{result['file_path']}: {result['labels']}")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `labels` | `List[str]` | required | Labels to search for (OR logic) |
| `db` | `Optional[Database]` | `None` | Database instance |

**Returns:** `List[Dict[str, Any]]` — dicts with `file_path`, `labels`, and other file info.

---

### query_all()

Get all files in the database.

```python
from filekor.db import query_all

all_files = query_all()
for file in all_files:
    print(f"{file['name']}: {file['labels']}")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `db` | `Optional[Database]` | `None` | Database instance |

**Returns:** `List[Dict[str, Any]]` — list of file dicts with labels.

---

### search_content()

Full-text search in filename and .kor metadata using FTS5.

```python
from filekor.db import search_content

results = search_content("budget report", limit=10)
for result in results:
    print(f"{result['name']} (rank: {result.get('fts_rank', 0)})")
    print(f"  Labels: {result['labels']}")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | Search query text |
| `limit` | `int` | `50` | Maximum results |
| `db` | `Optional[Database]` | `None` | Database instance |

**Returns:** `List[Dict[str, Any]]` — dicts with file info, labels, and `fts_rank`.

---

### search_files()

Combined search by labels and/or content with configurable relevance scoring.

```python
from filekor.db import search_files

results = search_files(
    labels=["finance", "2026"],
    query="provider costs",
    limit=50,
    weights={
        "label_match": 0.50,
        "filename_match": 0.30,
        "kor_content_match": 0.20,
    }
)

for result in results:
    print(f"{result['name']}: {result['score']}")
    print(f"  Breakdown: {result['score_breakdown']}")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `labels` | `Optional[List[str]]` | `None` | Labels to filter by (OR logic) |
| `query` | `Optional[str]` | `None` | Full-text search query |
| `limit` | `int` | `50` | Maximum results |
| `weights` | `Optional[Dict[str, float]]` | `None` | Scoring weights (see below) |
| `db` | `Optional[Database]` | `None` | Database instance |

**Returns:** `List[Dict[str, Any]]` — dicts with `name`, `score`, `score_breakdown`, labels, and file info.

**Scoring Weights:**

| Factor | Default | Description |
|--------|---------|-------------|
| `label_match` | 0.50 | Percentage of requested labels found |
| `filename_match` | 0.30 | Query presence in filename |
| `kor_content_match` | 0.20 | Query presence in .kor metadata |

---

### query_labels_with_counts()

Get all labels with their file counts.

```python
from filekor.db import query_labels_with_counts

labels = query_labels_with_counts()
for entry in labels:
    print(f"{entry['label']}: {entry['file_count']} files")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `db` | `Optional[Database]` | `None` | Database instance |

**Returns:** `List[Dict[str, Any]]` — dicts with `label` and `file_count`.

---

### close_db()

Close the database connection. Call this when done to release resources.

```python
from filekor.db import get_db, close_db

db = get_db()
# ... do work ...
close_db()
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `db` | `Optional[Database]` | `None` | Database instance |

**Returns:** `None`.

---

### get_file_by_hash()

Look up a file in the database by SHA256 hash.

```python
from filekor.db import get_file_by_hash

record = get_file_by_hash("abc123...")
if record:
    print(f"Found: {record['name']}")
else:
    print("Not found")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hash_sha256` | `str` | required | SHA256 hash to search for |
| `db` | `Optional[Database]` | `None` | Database instance |

**Returns:** `Optional[Dict[str, Any]]` — file dict or `None` if not found.

---

### delete_file_by_hash()

Delete a file record from the database by SHA256 hash.

```python
from filekor.db import delete_file_by_hash

deleted = delete_file_by_hash("abc123...")
print(f"Deleted {deleted} record(s)")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hash_sha256` | `str` | required | SHA256 hash of the file to delete |
| `db` | `Optional[Database]` | `None` | Database instance |

**Returns:** `int` — number of records deleted.

---

### get_all_files()

Get all files from the database. Alias for `query_all()`.

```python
from filekor.db import get_all_files

files = get_all_files()
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `db` | `Optional[Database]` | `None` | Database instance |

**Returns:** `List[Dict[str, Any]]`.

---

## Sidecar API

Create and manipulate .kor sidecar files programmatically.

### Sidecar

The main model. A Pydantic `BaseModel` with these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `version` | `str` | `"1.0"` | Schema version |
| `file` | `FileInfo` | required | File identification |
| `metadata` | `Optional[FileMetadata]` | `None` | Extracted metadata |
| `content` | `Optional[Content]` | `None` | Content info |
| `summary` | `Optional[FileSummary]` | `None` | LLM summaries |
| `labels` | `Optional[FileLabels]` | `None` | Assigned labels |
| `parser_status` | `str` | `"OK"` | Parser status |
| `generated_at` | `datetime` | required | Generation timestamp |

---

### Sidecar.create()

Create a new sidecar from a file. Computes file info (hash, size, timestamps) but does **not** generate labels.

```python
from filekor.sidecar import Sidecar, FileMetadata, Content

sidecar = Sidecar.create(
    file_path="./document.pdf",
    metadata=FileMetadata(author="Jane Doe", pages=10),
    content=Content(language="en", word_count=5000, page_count=10),
    verbose=False,
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | required | Path to source file |
| `metadata` | `Optional[FileMetadata]` | `None` | Extracted metadata |
| `content` | `Optional[Content]` | `None` | Content information |
| `verbose` | `bool` | `False` | Print detailed output |

**Returns:** `Sidecar` instance (without labels).

> **Note:** Labels and summaries are not auto-generated. Use `suggest_labels()` + `update_labels()` for labels, or `generate_summary()` for summaries. Alternatively, use the CLI commands `filekor labels` or `filekor summary`.

---

### Sidecar.load()

Load an existing .kor sidecar file from disk.

```python
from filekor.sidecar import Sidecar

sidecar = Sidecar.load("./document.pdf.kor")

print(sidecar.file.name)
print(sidecar.file.hash_sha256)
if sidecar.labels:
    print(sidecar.labels.suggested)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Path to .kor file |

**Returns:** `Sidecar` instance.

**Raises:**
- `FileNotFoundError` — if .kor file does not exist
- `ValueError` — if .kor file contains invalid YAML

---

### Sidecar.update_labels()

Update labels on a sidecar instance (in-place).

```python
sidecar.update_labels(["finance", "invoice", "2024"])
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `labels` | `List[str]` | required | New label list |

**Returns:** `None`. Modifies the sidecar in place.

---

### Sidecar.to_yaml()

Serialize sidecar to YAML string.

```python
yaml_content = sidecar.to_yaml()
pathlib.Path("./output.kor").write_text(yaml_content)
```

**Returns:** `str` — YAML representation.

---

### Sidecar.to_json()

Serialize sidecar to JSON string.

```python
json_content = sidecar.to_json()
data = json.loads(json_content)
```

**Returns:** `str` — JSON representation.

---

## Labels API

Work with taxonomy labels and LLM-based classification.

### suggest_labels()

Get label suggestions from LLM. **Raises** if LLM is not configured.

```python
from filekor.labels import suggest_labels

with open("./document.txt", "r") as f:
    content = f.read()

suggestions = suggest_labels(content=content)
print(suggestions)  # ['finance', 'invoice']
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | required | Text content to analyze |
| `config` | `Optional[LabelsConfig]` | `None` | Taxonomy config. Loads default if None |
| `llm_config` | `Optional[LLMConfig]` | `None` | LLM config. Loads from config.yaml if None |

**Returns:** `List[str]` — suggested label names.

**Raises:**
- `RuntimeError` — if LLM is not enabled or API key is missing

---

### suggest_from_content()

Lower-level label suggestion. Returns empty list instead of raising when LLM is not configured.

```python
from filekor.labels import suggest_from_content

suggestions = suggest_from_content(content="Some document text...")
# Returns [] if LLM not configured, no exception
```

**Parameters:** Same as `suggest_labels()`.

**Returns:** `List[str]` — suggested labels, or empty list if LLM not available.

---

### LabelsConfig

Configuration for label taxonomy.

```python
from filekor.labels import LabelsConfig

# Load from default locations (searches current dir, .filekor/, ~/.filekor/)
config = LabelsConfig.load()

# Load from specific file
config = LabelsConfig.load("./my-labels.properties")

# Access synonyms
for label_name, synonyms in config.synonyms.items():
    print(f"{label_name}: {synonyms}")
```

**Attributes:**

| Field | Type | Description |
|-------|------|-------------|
| `synonyms` | `Dict[str, List[str]]` | Label name → synonym list mapping |
| `confidence_threshold` | `float` | Minimum confidence to include (default 0.2) |

**Class Methods:**

| Method | Description |
|--------|-------------|
| `load(custom_path=None)` | Load from properties file. Searches: custom path → current dir → `.filekor/` → `~/.filekor/` → defaults |

---

### get_config()

Get the global labels config singleton. Loads lazily on first call.

```python
from filekor.labels import get_config

config = get_config()
print(config.synonyms.keys())
```

**Returns:** `LabelsConfig` instance.

---

### reload_config()

Force-reload the global labels config from disk.

```python
from filekor.labels import reload_config

config = reload_config()  # Reloads from default locations
config = reload_config("./custom-labels.properties")  # From specific path
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `custom_path` | `Optional[str]` | `None` | Path to custom labels.properties |

**Returns:** `LabelsConfig` instance.

---

### LLMConfig

Configuration for LLM providers. Loaded from `config.yaml`.

```python
from filekor.labels import LLMConfig

config = LLMConfig.load()

if config.enabled and config.api_key:
    print(f"Provider: {config.provider}")
    print(f"Model: {config.model}")
    print(f"Auto-sync: {config.auto_sync}")
```

**Attributes:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | Whether LLM is enabled |
| `provider` | `str` | `"gemini"` | Provider name (gemini, openai, groq, openrouter, mock) |
| `model` | `str` | `"gemini-2.0-flash"` | Model name |
| `api_key` | `Optional[str]` | `None` | API key (supports `${ENV_VAR}` expansion) |
| `max_content_chars` | `int` | `1500` | Max chars sent to LLM |
| `workers` | `int` | `4` | Parallel workers for directory processing |
| `auto_sync` | `bool` | `False` | Auto-sync to database after CLI operations |

**Class Methods:**

| Method | Description |
|--------|-------------|
| `load(custom_path=None)` | Load from config.yaml. Searches: custom path → current dir → `.filekor/` → `~/.filekor/` |

---

## Summary API

LLM-based content summarization.

### generate_summary()

Generate short and/or long summaries of text content using LLM.

```python
from filekor.core.summary import generate_summary

result = generate_summary(
    content="Long document text...",
    length="both",  # "short", "long", or "both"
    max_chars=2000,
)

print(result.short)  # 1-2 sentences
print(result.long)   # Detailed summary
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | required | Text content to summarize |
| `length` | `Literal["short", "long", "both"]` | `"both"` | Which summary to generate |
| `llm_config` | `Optional[LLMConfig]` | `None` | LLM config. Loads from config.yaml if None |
| `max_chars` | `Optional[int]` | `None` | Max chars to send to LLM. Overrides config if set |

**Returns:** `SummaryResult` with `short` and/or `long` fields.

**Raises:**
- `RuntimeError` — if LLM is not enabled or API key is missing

---

## List API

Query and list .kor files in directories.

### list_kor_files()

List all .kor files in a directory with metadata.

```python
from filekor.list import list_kor_files

# Basic listing
files = list_kor_files("./docs")

# Filter by extension
pdfs = list_kor_files("./docs", extension="pdf")

# Include merged .kor entries
all_files = list_kor_files("./docs", include_merged=True)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `directory` | `str` | required | Directory to scan |
| `extension` | `Optional[str]` | `None` | Filter by extension (e.g., "pdf") |
| `include_merged` | `bool` | `False` | Include entries from merged .kor files |
| `recursive` | `bool` | `True` | Search subdirectories |

**Returns:** `List[Dict[str, Any]]` — dicts with keys: `sha256`, `name`, `path`, `type` (either `"individual"` or `"merged"`).

---

### list_as_text()

List .kor files as formatted text output.

```python
from filekor.list import list_as_text

print(list_as_text("./docs", extension="pdf"))
# Output:
# abc123def456... report.pdf
# 789ghi012jkl... invoice.pdf
```

**Parameters:** Same as `list_kor_files()`.

**Returns:** `str` — one entry per line with truncated SHA and name.

---

### list_as_json()

List .kor files as JSON string.

```python
from filekor.list import list_as_json

json_str = list_as_json("./docs")
```

**Parameters:** Same as `list_kor_files()`.

**Returns:** `str` — JSON array string.

---

### list_as_csv()

List .kor files as CSV string.

```python
from filekor.list import list_as_csv

csv_str = list_as_csv("./docs")
```

**Parameters:** Same as `list_kor_files()`.

**Returns:** `str` — CSV with header row: `sha256,name,path,type`.

---

### list_sha_only()

List only SHA256 hashes, one per line.

```python
from filekor.list import list_sha_only

hashes = list_sha_only("./docs")
```

**Parameters:** Same as `list_kor_files()`.

**Returns:** `str` — one SHA256 per line.

---

## Merge API

Combine multiple .kor files into a single aggregated file.

### merge_kor_files()

Merge all .kor files in a `.filekor/` directory into one file.

```python
from filekor.merge import merge_kor_files

# Merge and delete source files
sidecars = merge_kor_files("./docs")

# Merge but keep source files
sidecars = merge_kor_files("./docs", delete_sources=False)

# Custom output path
sidecars = merge_kor_files("./docs", output_path="./merged-output.kor")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `directory` | `str` | required | Directory containing `.filekor/` subfolder |
| `output_path` | `Optional[str]` | `None` | Output path. Defaults to `.filekor/merged.kor` |
| `delete_sources` | `bool` | `True` | Delete original .kor files after merge |

**Returns:** `List[Sidecar]` — list of merged sidecar objects.

**Raises:**
- `FileNotFoundError` — if `.filekor/` directory does not exist

---

### load_merged_kor()

Load a merged .kor file (multi-document YAML) as a list of Sidecar objects.

```python
from filekor.merge import load_merged_kor

sidecars = load_merged_kor("./docs/.filekor/merged.kor")
for sc in sidecars:
    print(f"{sc.file.name}: {sc.labels.suggested if sc.labels else 'no labels'}")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Path to merged .kor file |

**Returns:** `List[Sidecar]`.

**Raises:**
- `FileNotFoundError` — if file does not exist

---

## Delete API

Delete .kor files and database records by SHA256 hash or file path.

### delete_by_sha()

Delete by SHA256 hash. Can target database, .kor files, or both.

```python
from filekor.delete import delete_by_sha

# Delete from both DB and file system
db_deleted, files_deleted = delete_by_sha("abc123...")

# Delete only from database
db_deleted, files_deleted = delete_by_sha("abc123...", scope="db")

# Delete only .kor files
db_deleted, files_deleted = delete_by_sha("abc123...", scope="file")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sha256` | `str` | required | SHA256 hash |
| `directory` | `str` | `"."` | Directory to search for .kor files |
| `scope` | `Literal["all", "db", "file"]` | `"all"` | What to delete |
| `recursive` | `bool` | `True` | Search subdirectories |
| `max_depth` | `int` | `-1` | Max depth (-1 for unlimited) |
| `verbose` | `bool` | `False` | Print detailed output |

**Returns:** `Tuple[int, int]` — `(deleted_db_count, deleted_files_count)`.

---

### delete_by_path()

Delete by file path. Internally computes the SHA256 hash.

```python
from filekor.delete import delete_by_path

db_deleted, files_deleted = delete_by_path("./docs/old-report.pdf")
```

**Parameters:** Same as `delete_by_sha()` except `path` instead of `sha256`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Path to source file |

**Returns:** `Tuple[int, int]`.

---

### delete_by_input()

Batch delete from a file containing SHA256 hashes (one per line). Lines starting with `#` are ignored.

```python
from filekor.delete import delete_by_input

total_db, total_files = delete_by_input("./hashes-to-delete.txt")
```

**Parameters:** Same as `delete_by_sha()` except `input_path` instead of `sha256`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_path` | `str` | required | Path to file with SHA256 hashes |

**Returns:** `Tuple[int, int]` — `(total_deleted_db, total_deleted_files)`.

**Raises:**
- `FileNotFoundError` — if input file does not exist

---

### get_deletion_preview()

Dry-run: preview what would be deleted without actually deleting.

```python
from filekor.delete import get_deletion_preview

db_hashes, files = get_deletion_preview("abc123...")
print(f"Would delete {len(db_hashes)} DB record(s)")
for name, path in files:
    print(f"  Would delete: {name} ({path})")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sha256` | `str` | required | SHA256 hash |
| `directory` | `str` | `"."` | Directory to search |
| `recursive` | `bool` | `True` | Search subdirectories |
| `max_depth` | `int` | `-1` | Max search depth |

**Returns:** `Tuple[List[str], List[Tuple[str, str]]]` — `(db_hashes_to_delete, [(name, path), ...])`.

---

## Processor API

Parallel directory processing engine.

### DirectoryProcessor

Class for batch-processing directories with parallel workers.

```python
from filekor.processor import DirectoryProcessor

processor = DirectoryProcessor(
    workers=4,
    llm_config=None,   # Loads from config.yaml
    labels_config=None, # Loads from labels.properties
)

# Process a single file
result = processor.process_file("./document.pdf")
print(f"Success: {result.success}, Output: {result.output_path}")

# Process a directory
results = processor.process_directory(
    directory="./docs",
    recursive=True,
    callback=lambda r: print(f"  Processed: {r.file_path.name}"),
)
```

**Constructor Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `workers` | `int` | `4` | Number of parallel workers |
| `output_dir` | `Optional[Path]` | `None` | Output directory. Defaults to `.filekor/` next to each file |
| `llm_config` | `Optional[LLMConfig]` | `None` | LLM config for label extraction |
| `labels_config` | `Optional[LabelsConfig]` | `None` | Taxonomy config |

**Methods:**

| Method | Description |
|--------|-------------|
| `process_file(file_path)` | Process a single file. Returns `ProcessResult` |
| `process_directory(directory, recursive, callback)` | Process all supported files. Returns `List[ProcessResult]` |
| `get_output_path(input_path)` | Compute .kor output path for a file |

---

### process_directory()

Convenience function for directory processing. Creates a `DirectoryProcessor` internally.

```python
from filekor.processor import process_directory

results = process_directory(
    path="./docs",
    workers=4,
    recursive=True,
    callback=lambda r: print(f"Done: {r.file_path.name}"),
)

successful = [r for r in results if r.success]
print(f"Processed {len(successful)}/{len(results)} files")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Directory path |
| `workers` | `Optional[int]` | `None` | Workers (default from config) |
| `output_dir` | `Optional[str]` | `None` | Output directory |
| `recursive` | `bool` | `True` | Process subdirectories |
| `llm_config` | `Optional[LLMConfig]` | `None` | LLM config |
| `labels_config` | `Optional[LabelsConfig]` | `None` | Labels config |
| `callback` | `Optional[Callable[[ProcessResult], None]]` | `None` | Progress callback |

**Returns:** `List[ProcessResult]`.

**Supported file extensions:** `.pdf`, `.txt`, `.md`

---

## Events API

Event system for real-time progress updates and `--watch` mode integration.

### EventType

Enum of event types.

```python
from filekor.events import EventType

EventType.STARTED     # Processing started
EventType.PROCESSING  # Single file being processed
EventType.COMPLETED   # Single file completed
EventType.ERROR       # Single file failed
EventType.FINISHED    # All files processed
EventType.STATUS      # Status check event
```

---

### FilekorEvent

Event data structure.

```python
from filekor.events import FilekorEvent, EventType

event = FilekorEvent.create(EventType.COMPLETED, file_path="./doc.pdf", labels=["finance"])
print(event.type)       # EventType.COMPLETED
print(event.timestamp)  # ISO timestamp
print(event.data)       # {'file_path': './doc.pdf', 'labels': ['finance']}
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | `EventType` | Event type |
| `timestamp` | `str` | ISO 8601 timestamp |
| `data` | `Dict` | Event-specific data |

---

### EventEmitter

Event dispatcher with handler registration and optional file output.

```python
from filekor.events import EventEmitter, EventType

emitter = EventEmitter(enabled=True)

# Register handlers
emitter.on(EventType.COMPLETED, lambda e: print(f"Done: {e.data['file_path']}"))
emitter.on(EventType.ERROR, lambda e: print(f"Error: {e.data['error']}"))

# Emit events
emitter.completed("./doc.pdf", "./doc.pdf.kor", labels=["finance"])
emitter.finished(total=10, successful=9, failed=1)
```

**Constructor Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | `bool` | `False` | Whether to dispatch events |
| `output_file` | `Optional[Path]` | `None` | File to append JSON events to |

**Methods:**

| Method | Description |
|--------|-------------|
| `on(event_type, handler)` | Register a handler for an event type |
| `off(event_type, handler)` | Unregister a handler |
| `emit(event)` | Emit a `FilekorEvent` |
| `started(directory, total_files)` | Emit STARTED event |
| `processing(file_path, file_index, total)` | Emit PROCESSING event |
| `completed(file_path, output_path, labels)` | Emit COMPLETED event |
| `error(file_path, error)` | Emit ERROR event |
| `finished(total, successful, failed)` | Emit FINISHED event |
| `status(directory, files, kor_files)` | Emit STATUS event |

---

### create_emitter()

Convenience factory for creating an EventEmitter.

```python
from filekor.events import create_emitter

emitter = create_emitter(watch=True, output_file="./events.jsonl")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `watch` | `bool` | `False` | Enable event dispatching |
| `output_file` | `Optional[str]` | `None` | Path for JSONL event log |

**Returns:** `EventEmitter` instance.

---

## Status API

Check file and directory processing status.

### get_file_status()

Get status for a single file.

```python
from filekor.status import get_file_status

status = get_file_status("./document.pdf")

print(f"Has .kor: {status.exists}")
if status.sidecar:
    print(f"Labels: {status.sidecar.labels.suggested}")
if status.error:
    print(f"Error: {status.error}")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | required | Path to the file |

**Returns:** `FileStatus` dataclass.

---

### get_directory_status()

Get status for all files in a directory.

```python
from filekor.status import get_directory_status

status = get_directory_status("./docs", recursive=True, max_depth=2)

print(f"Total: {status.total_files}")
print(f"With .kor: {status.kor_files}")
print(f"Missing: {len(status.files_without_kor)}")

for fs in status.file_statuses:
    icon = "✓" if fs.exists else "✗"
    print(f"  {icon} {fs.file_path.name}")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `directory` | `str` | required | Directory path |
| `recursive` | `bool` | `True` | Search subdirectories |
| `max_depth` | `int` | `-1` | Maximum depth (-1 for unlimited) |

**Returns:** `DirectoryStatus` dataclass.

---

### summarize()

Create a lightweight summary dict from a `FileStatus`.

```python
from filekor.status import get_file_status, summarize

status = get_file_status("./document.pdf")
summary = summarize(status)
# {'file': './document.pdf', 'kor_exists': True, 'name': 'document.pdf', ...}
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `s` | `FileStatus` | required | FileStatus to summarize |

**Returns:** `Dict` with keys: `file`, `kor_exists`, and (if exists) `name`, `size_bytes`, `labels`, `parser_status`.

---

## Hasher

### calculate_sha256()

Calculate SHA256 hash for a file.

```python
from filekor.hasher import calculate_sha256

hash_val = calculate_sha256("./document.pdf")
print(hash_val)  # "a1b2c3d4e5f6..."
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Path to the file |

**Returns:** `str` — SHA256 hex digest.

---

## Exceptions & Error Handling

| Function/Method | Exception | Condition |
|----------------|-----------|-----------|
| `Sidecar.load()` | `FileNotFoundError` | .kor file not found |
| `Sidecar.load()` | `ValueError` | Invalid YAML content |
| `suggest_labels()` | `RuntimeError` | LLM not enabled or API key missing |
| `generate_summary()` | `RuntimeError` | LLM not enabled or API key missing |
| `merge_kor_files()` | `FileNotFoundError` | `.filekor/` directory not found |
| `load_merged_kor()` | `FileNotFoundError` | Merged .kor file not found |
| `delete_by_input()` | `FileNotFoundError` | Input hash file not found |
| `suggest_from_content()` | *never raises* | Returns `[]` on any error |

---

## Library vs CLI

| Use the **Library** when... | Use the **CLI** when... |
|----------------------------|------------------------|
| Integrating filekor into another Python app | One-off file processing |
| Building custom workflows with callbacks | Quick metadata extraction |
| Need programmatic search queries | Interactive exploration |
| Batch processing with custom logic | Status checks and listing |
| Building dashboards or APIs | Shell scripting |

**Key advantage of the library:** You get full access to the `ProcessResult`, `EventEmitter`, and programmatic search with custom scoring weights — none of which are available via CLI.

**Key advantage of the CLI:** Zero setup, immediate results, and `--watch` mode for development workflows.

---

## Complete Example

End-to-end workflow: process a directory, sync to DB, search, and clean up.

```python
import pathlib
from filekor import (
    Sidecar,
    suggest_labels,
    process_directory,
    get_db, sync_file, search_files, close_db,
    list_kor_files,
    calculate_sha256,
)

# 1. Process all files in ./docs (parallel, with LLM labels if configured)
results = process_directory("./docs", workers=4)

# 2. Sync successful results to database
db = get_db()
for result in results:
    if result.success and result.output_path:
        sync_file(str(result.output_path))

# 3. Search by labels and content
matches = search_files(
    labels=["finance", "contract"],
    query="quarterly report",
    limit=10,
)

print(f"Found {len(matches)} files:")
for m in matches:
    print(f"  {m['name']} (score: {m['score']:.2f})")

# 4. List all .kor files
all_kor = list_kor_files("./docs")
print(f"\nTotal .kor files: {len(all_kor)}")

# 5. Verify a file's hash
file_hash = calculate_sha256("./docs/report.pdf")
print(f"SHA256: {file_hash}")

# 6. Clean up
close_db()
```

---

## Configuration

Library behavior is configured via `~/.filekor/config.yaml`:

```yaml
filekor:
  workers: 4

  labels:
    taxonomy: default

  llm:
    enabled: true
    provider: gemini   # or openai, groq, openrouter, mock
    api_key: ${GEMINI_API_KEY}
    model: gemini-2.0-flash
    max_content_chars: 1500
    auto_sync: true

  search:
    weights:
      label_match: 0.50
      filename_match: 0.30
      kor_content_match: 0.20
```

---

## API Reference Summary

### Sidecar & Models

| Symbol | Description |
|--------|-------------|
| `Sidecar` | Main sidecar model (Pydantic BaseModel) |
| `FileInfo` | File identification (path, name, hash, size) |
| `FileMetadata` | Optional extracted metadata (author, pages) |
| `Content` | Optional content info (language, word count) |

### Labels

| Function/Class | Description |
|----------------|-------------|
| `suggest_labels(content, config?, llm_config?)` | LLM label suggestions (raises if not configured) |
| `suggest_from_content(content, config?, llm_config?)` | LLM label suggestions (returns [] if not configured) |
| `LabelsConfig` | Taxonomy configuration |
| `LLMConfig` | LLM provider configuration |
| `get_config()` | Get global LabelsConfig singleton |
| `reload_config(custom_path?)` | Force-reload global config |

### Summary

| Function/Class | Description |
|----------------|-------------|
| `generate_summary(content, length?, llm_config?, max_chars?)` | Generate LLM summaries |
| `SummaryResult` | Result model (short, long) |

### Database

| Function/Class | Description |
|----------------|-------------|
| `get_db(path?)` | Get singleton Database instance |
| `sync_file(kor_path, db?)` | Sync .kor to database (returns list of file IDs) |
| `query_by_label(label, db?)` | Query by single label |
| `query_by_labels(labels, db?)` | Query by multiple labels (OR) |
| `query_all(db?)` | Get all files |
| `search_content(query, limit?, db?)` | FTS5 full-text search |
| `search_files(labels?, query?, limit?, weights?, db?)` | Combined search with scoring |
| `query_labels_with_counts(db?)` | Labels with file counts |
| `close_db(db?)` | Close database connection |
| `get_file_by_hash(hash, db?)` | Lookup by SHA256 |
| `delete_file_by_hash(hash, db?)` | Delete DB record by SHA256 |
| `get_all_files(db?)` | Alias for query_all() |
| `Database` | Database class (low-level) |
| `DBFile` | File record model |
| `DBLabel` | Label record model |
| `DBCollection` | Collection record model |

### List

| Function | Description |
|----------|-------------|
| `list_kor_files(directory, extension?, include_merged?, recursive?)` | List .kor files |
| `list_as_text(...)` | List as formatted text |
| `list_as_json(...)` | List as JSON |
| `list_as_csv(...)` | List as CSV |
| `list_sha_only(...)` | List only SHA256 hashes |

### Merge

| Function | Description |
|----------|-------------|
| `merge_kor_files(directory, output_path?, delete_sources?)` | Merge .kor files |
| `load_merged_kor(path)` | Load merged .kor file |

### Delete

| Function | Description |
|----------|-------------|
| `delete_by_sha(sha256, directory?, scope?, ...)` | Delete by hash |
| `delete_by_path(path, directory?, scope?, ...)` | Delete by file path |
| `delete_by_input(input_path, directory?, scope?, ...)` | Batch delete from file |
| `get_deletion_preview(sha256, directory?, ...)` | Dry-run deletion preview |

### Processor

| Symbol | Description |
|--------|-------------|
| `DirectoryProcessor` | Parallel directory processor class |
| `process_directory(path, workers?, ...)` | Convenience function for batch processing |
| `ProcessResult` | Per-file processing result |

### Events

| Symbol | Description |
|--------|-------------|
| `EventEmitter` | Event dispatcher with handler registration |
| `EventType` | Event type enum (STARTED, PROCESSING, COMPLETED, ERROR, FINISHED, STATUS) |
| `FilekorEvent` | Event data structure |
| `create_emitter(watch?, output_file?)` | EventEmitter factory |

### Status

| Function | Description |
|----------|-------------|
| `get_file_status(file_path)` | Single file status |
| `get_directory_status(directory, recursive?, max_depth?)` | Directory status |
| `summarize(file_status)` | Lightweight status summary dict |

### Hasher

| Function | Description |
|----------|-------------|
| `calculate_sha256(path)` | File SHA256 hash |
