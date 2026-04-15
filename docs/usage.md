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
| `labels` | Suggest taxonomy labels |
| `process` | Legacy - extract metadata |

---

## Extract

Extract text content from PDF, TXT, or MD files.

```bash
# Extract to stdout
filekor extract documento.pdf

# Extract to file
filekor extract documento.pdf -o extracted.txt

# Show help
filekor extract --help
```

---

## Sidecar

Generate a `.kor` YAML sidecar file with full metadata.

```bash
# Generate sidecar (same directory)
filekor sidecar documento.pdf

# Custom output path
filekor sidecar documento.pdf -o metadata.kor

# Custom config.yaml for LLM
filekor sidecar documento.pdf --config /path/to/config.yaml

# Force regeneration
filekor sidecar documento.pdf --no-cache
```

### Sidecar Output Format

```yaml
version: "1.0"
file:
  path: /path/to/documento.pdf
  name: documento.pdf
  extension: .pdf
  size_bytes: 12345
  modified_at: "2026-04-14T10:30:00Z"
  hash_sha256: "abc123..."
metadata:
  author: "John Doe"
  created: "2026-04-01"
  pages: 5
content:
  language: en
  word_count: 1500
  page_count: 5
labels:
  suggested:
    - documentation
    - legal
  source: llm
parser_status: OK
generated_at: "2026-04-14T10:30:00Z"
```

---

## Labels

Suggest taxonomy labels for a file using LLM.

```bash
# Suggest labels
filekor labels documento.pdf

# Custom taxonomy config (labels.properties)
filekor labels documento.pdf --config custom-labels.properties

# Custom LLM config (config.yaml)
filekor labels documento.pdf --llm-config /path/to/config.yaml

# Show help
filekor labels --help
```

### Output Example

```
documentation
legal
```

---

## Process (Legacy)

Legacy command for metadata extraction.

```bash
filekor process documento.pdf --output metadata.kor
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | ExifTool not found or unsupported file |
| 2 | File not found |
| 3 | Permission denied |