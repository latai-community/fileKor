# Library API Reference

filekor can be used as a Python library for programmatic access to file metadata extraction, sidecar generation, and database operations.

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
from filekor.db import get_db, sync_file, search_files

# Get database instance (lazy singleton)
db = get_db()

# Sync a .kor file to the database
sync_file("./document.kor")

# Search files by labels and content with scoring
results = search_files(
    labels=["finance", "2026"],
    query="budget report"
)

# Print results
for result in results:
    print(f"{result['name']}: {result['score']}")
```

---

## Database API

The database module provides SQLite-backed storage with full-text search capabilities.

### get_db()

Get the singleton database instance. Creates the database on first call.

```python
from filekor.db import get_db

db = get_db()
# Database is created at ~/.filekor/index.db on first call
```

### sync_file()

Synchronize a .kor file to the database.

```python
from filekor.db import sync_file

# Sync a single .kor file
sync_file("./docs/report.pdf.kor")

# The .kor file is parsed and stored in the database
# Labels are extracted and stored in the labels table
```

### query_by_label()

Query files by a single label.

```python
from filekor.db import query_by_label

# Find all files with the "finance" label
files = query_by_label("finance")
# Returns: ['./docs/budget.pdf', './docs/invoice.pdf']
```

### query_by_labels()

Query files by multiple labels (OR logic).

```python
from filekor.db import query_by_labels

# Find files with ANY of these labels
results = query_by_labels(["finance", "2024", "invoice"])

# Returns list of file records with their labels
for result in results:
    print(f"{result['file_path']}: {result['labels']}")
```

### query_all()

Get all files in the database.

```python
from filekor.db import query_all

# Get all files with their labels
all_files = query_all()

for file in all_files:
    print(f"{file['name']}: {file['labels']}")
```

### search_content()

Full-text search in filename and .kor metadata (FTS5).

```python
from filekor.db import search_content

# Search in filename and metadata
results = search_content("budget report", limit=10)

for result in results:
    print(f"{result['name']} (rank: {result.get('fts_rank', 0)})")
    print(f"  Labels: {result['labels']}")
```

### search_files()

Combined search by labels and/or content with relevance scoring.

```python
from filekor.db import search_files

# Search with filters and scoring
results = search_files(
    labels=["finance", "2026"],      # OR logic - any of these
    query="provider costs",          # Full-text search
    limit=50,                        # Max results
    weights={                        # Scoring weights
        "label_match": 0.50,
        "filename_match": 0.30,
        "kor_content_match": 0.20
    }
)

# Result includes relevance score
for result in results:
    print(f"{result['name']}: {result['score']}")
    print(f"  Breakdown: {result['score_breakdown']}")
```

**Scoring Weights:**

| Factor | Default | Description |
|--------|---------|-------------|
| `label_match` | 0.50 | Percentage of requested labels found |
| `filename_match` | 0.30 | Query presence in filename |
| `kor_content_match` | 0.20 | Query presence in .kor metadata |

---

## Sidecar API

Create and manipulate .kor sidecar files programmatically.

### Sidecar.create()

Create a new sidecar file.

```python
from filekor.sidecar import Sidecar

# Create sidecar from file
sidecar = Sidecar.create(
    file_path="./document.pdf",
    metadata=None,           # Optional: FileMetadata object
    content=None,            # Optional: Content object
    labels_config=None,      # Optional: LabelsConfig
    text_content=None,       # Optional: Extracted text for LLM
    verbose=False
)

# Save to file
import pathlib
kor_path = pathlib.Path("./document.pdf.kor")
kor_path.write_text(sidecar.to_yaml())
```

### Sidecar.load()

Load an existing sidecar file.

```python
from filekor.sidecar import Sidecar

# Load existing .kor file
sidecar = Sidecar.load("./document.pdf.kor")

# Access file info
print(sidecar.file.name)
print(sidecar.file.size_bytes)
print(sidecar.file.hash_sha256)

# Access labels
if sidecar.labels:
    print(sidecar.labels.suggested)
    print(sidecar.labels.source)
```

### Sidecar.update_labels()

Update labels in a sidecar.

```python
from filekor.sidecar import Sidecar

# Load existing sidecar
sidecar = Sidecar.load("./document.pdf.kor")

# Update labels
sidecar.update_labels(["finance", "invoice", "2024"])

# Save back
import pathlib
pathlib.Path("./document.pdf.kor").write_text(sidecar.to_yaml())
```

### Sidecar.to_yaml()

Export sidecar to YAML format.

```python
from filekor.sidecar import Sidecar

sidecar = Sidecar.load("./document.pdf.kor")
yaml_content = sidecar.to_yaml()

# Save or transmit
with open("./output.kor", "w") as f:
    f.write(yaml_content)
```

### Sidecar.to_json()

Export sidecar to JSON format.

```python
from filekor.sidecar import Sidecar

sidecar = Sidecar.load("./document.pdf.kor")
json_content = sidecar.to_json()

# Parse or transmit
import json
data = json.loads(json_content)
```

---

## Labels API

Work with taxonomy labels and LLM-based classification.

### suggest_labels()

Get label suggestions from LLM.

```python
from filekor.labels import suggest_labels, LabelsConfig, LLMConfig

# Load configurations
labels_config = LabelsConfig.load()
llm_config = LLMConfig.load()

# Extract text from file
with open("./document.txt", "r") as f:
    content = f.read()

# Get suggestions
suggestions = suggest_labels(
    content=content,
    config=labels_config,
    llm_config=llm_config
)

print(suggestions)  # ['finance', 'invoice']
```

### LabelsConfig

Configuration for label taxonomy.

```python
from filekor.labels import LabelsConfig

# Load from default locations
config = LabelsConfig.load()

# Or load from specific file
config = LabelsConfig.load("./my-labels.properties")

# Access labels
for label in config.labels:
    print(f"{label.name}: {label.synonyms}")
```

### LLMConfig

Configuration for LLM providers.

```python
from filekor.labels import LLMConfig

# Load from config.yaml
config = LLMConfig.load()

# Check if enabled
if config.enabled and config.api_key:
    print(f"Provider: {config.provider}")
    print(f"Model: {config.model}")
    print(f"Auto-sync: {config.auto_sync}")
```

---

## Status API

Check file and directory status.

### get_file_status()

Get status for a single file.

```python
from filekor.status import get_file_status

status = get_file_status("./document.pdf")

print(f"File: {status.file_path}")
print(f"Kor path: {status.kor_path}")
print(f"Has .kor: {status.exists}")

if status.sidecar:
    print(f"Labels: {status.sidecar.labels.suggested}")
```

### get_directory_status()

Get status for all files in a directory.

```python
from filekor.status import get_directory_status

status = get_directory_status("./docs", recursive=True)

print(f"Total files: {status.total_files}")
print(f"With .kor: {status.kor_files}")

for file_status in status.file_statuses:
    if file_status.exists:
        print(f"✓ {file_status.file_path.name}")
    else:
        print(f"✗ {file_status.file_path.name} (no .kor)")
```

---

## Complete Example

Here's a complete workflow using the library:

```python
import pathlib
from filekor.sidecar import Sidecar
from filekor.labels import suggest_labels, LabelsConfig, LLMConfig
from filekor.db import get_db, sync_file, search_files

# 1. Process a file and create sidecar
file_path = pathlib.Path("./contract.pdf")

# Create sidecar with metadata
sidecar = Sidecar.create(
    file_path=str(file_path),
    metadata=None,  # Could add metadata here
    content=None,   # Could add content info here
)

# 2. Get label suggestions from LLM
labels_config = LabelsConfig.load()
llm_config = LLMConfig.load()

with open(file_path, "rb") as f:
    # Extract text (simplified - use actual extraction in production)
    text = "This is a contract for financial services..."

suggestions = suggest_labels(
    content=text,
    config=labels_config,
    llm_config=llm_config
)

# 3. Update sidecar with labels
sidecar.update_labels(suggestions)

# 4. Save .kor file
kor_dir = file_path.parent / ".filekor"
kor_dir.mkdir(parents=True, exist_ok=True)

ext = file_path.suffix.lstrip(".").lower()
kor_path = kor_dir / f"{file_path.stem}.{ext}.kor"
kor_path.write_text(sidecar.to_yaml())

# 5. Sync to database
db = get_db()
sync_file(str(kor_path))

# 6. Search for files
results = search_files(
    labels=["finance"],
    query="contract",
    limit=10
)

print(f"Found {len(results)} files:")
for result in results:
    print(f"  {result['name']} (score: {result['score']})")
```

---

## Configuration

### config.yaml

Library behavior can be configured via `~/.filekor/config.yaml`:

```yaml
filekor:
  workers: 4
  
  labels:
    taxonomy: default
    
  llm:
    enabled: true
    provider: gemini  # or openai, groq, openrouter, mock
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

### Database Functions

| Function | Description |
|----------|-------------|
| `get_db()` | Get singleton database instance |
| `sync_file(kor_path)` | Sync .kor file to database |
| `query_by_label(label)` | Query by single label |
| `query_by_labels(labels)` | Query by multiple labels (OR) |
| `query_all()` | Get all files |
| `search_content(query, limit)` | Full-text search |
| `search_files(labels, query, limit, weights)` | Combined search |

### Sidecar Class

| Method | Description |
|--------|-------------|
| `Sidecar.create(file_path, ...)` | Create new sidecar |
| `Sidecar.load(kor_path)` | Load existing sidecar |
| `update_labels(labels)` | Update labels |
| `to_yaml()` | Export to YAML |
| `to_json()` | Export to JSON |

### Labels Functions

| Function | Description |
|----------|-------------|
| `suggest_labels(content, config, llm_config)` | Get LLM suggestions |
| `LabelsConfig.load(path)` | Load label configuration |
| `LLMConfig.load()` | Load LLM configuration |

### Status Functions

| Function | Description |
|----------|-------------|
| `get_file_status(file_path)` | Get single file status |
| `get_directory_status(directory, recursive)` | Get directory status |