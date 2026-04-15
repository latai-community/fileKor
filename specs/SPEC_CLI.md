# SPEC: CLI Interface

**Document:** Command-line interface for fileKor  
**Reference:** INIT_SPEC.md section 2

---

## Main Commands

| Command | Description |
|---------|-------------|
| `filekor extract <path>` | Extract text from file, -d for directories|
| `filekor summarize <path>` | Generate summary (short by default) |
| `filekor labels <path>` | Suggest labels |
| `filekor preview <path>` | Generate preview |
| `filekor sidecar <path>` | Generate sidecar YAML file |

---

## Detailed Usage

### `filekor extract`

```bash
filekor extract <path> [OPTIONS]

# Extract text from a PDF
filekor extract documento.pdf

# Extract to specific file
filekor extract documento.pdf --output texto.txt

# Output format
filekor extract documento.pdf --format json

# Process directory recursively (uses SQLite index)
filekor extract ./documentos/ --dir
```

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--output, -o` | Output file | stdout |
| `--format, -f` | Format: text, json | text |
| `--dir` | Process directory recursively | False |
| `--workers` | Parallel workers (from config) | config (4) |
| `--watch` | Enable event emitter for progress | False |
| `--no-cache` | Force reprocessing | False |

---

### `filekor summarize`

```bash
filekor summarize <path> [OPTIONS]

# Short summary (default)
filekor summarize documento.pdf

# Long summary
filekor summarize documento.pdf --type long
filekor summarize documento.pdf -t long

# Save to file
filekor summarize documento.pdf --output resumen.txt
```

**Options:**

| Flag | Description | Default |
|------|-------------|---------|

### `filekor labels`

```bash
filekor labels <path> [OPTIONS]

# Suggest labels (creates/updates .kor file)
filekor labels documento.pdf

# With custom LLM config
filekor labels documento.pdf --llm-config /path/to/config.yaml

# With custom taxonomy
filekor labels documento.pdf --config /path/to/labels.properties
```

**Behavior:**
- If `.kor` file EXISTS: loads it and adds/replaces labels
- If `.kor` file does NOT exist: creates new `.kor` with file info and labels
- Labels are identified by SHA256 hash

**Example output:**

```
documentation
testing
code
Loading existing: documento.kor
Saved: documento.kor
```

**New .kor created example:**
```yaml
version: "1.0"
file:
  path: documento.pdf
  name: documento.pdf
  extension: pdf
  size_bytes: 12345
  modified_at: "2026-04-15T10:00:00Z"
  hash_sha256: "abc123..."
labels:
  suggested:
    - documentation
    - testing
    - code
  source: llm
parser_status: OK
generated_at: "2026-04-15T10:30:00Z"
```

---

### `filekor preview`

```bash
filekor preview <path> [OPTIONS]

# File preview
filekor preview documento.pdf

# Preview with metadata
filekor preview documento.pdf --show-metadata

# Limited lines
filekor preview documento.pdf --lines 50
```

**Example output:**

```
File: contrato-proveedor-2026.pdf
Size: 120 KB | Pages: 12 | Lang: es
----------------------------------------
[Preview]
This service contract establishes the terms and
conditions for cloud services provision...
----------------------------------------
Labels: contract, provider
Summary: Commercial annex with provider pricing...
```

---

### `filekor sidecar`

```bash
filekor sidecar <path> [OPTIONS]

# Generate sidecar for single file
filekor sidecar documento.pdf

# Generate .kor files in .filekor/ subdirectory
filekor sidecar ./documentos/ --dir

# Custom workers from config or override
filekor sidecar ./documentos/ --dir --workers 8

# Watch mode for real-time progress
filekor sidecar ./documentos/ --dir --watch

# Force regeneration
filekor sidecar documento.pdf --no-cache
```

**Output:**

For single file: generates `{filename}.kor` in same directory.
For directory: generates `.filekor/` subdirectory with .kor files.

---

### `filekor batch`

> **Note:** Use `--dir` flag instead: `filekor sidecar ./docs/ --dir`

---

## Global Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--help, -h` | Show help | - |
| `--version, -v` | Show version | - |
| `--verbose` | Detailed output | False |
| `--config` | Config file path | auto-search |

---

## Config File

Config file is located at `~/.filekor/config.yaml` (user home directory).

### Config Format

```yaml
# ~/.filekor/config.yaml
filekor:
  version: "1.0"
  
  workers: 4  # Parallel workers for directory processing
      
  labels:
    taxonomy: default
    confidence_threshold: 0.7
    config_file: ./labels.properties  # Optional path to labels.properties
     
  llm:
    enabled: true
    provider: gemini  # gemini, groq, openrouter, mock
    api_key: ${GEMINI_API_KEY}  # Supports env var interpolation
    model: gemini-2.0-flash
    max_content_chars: 1500
```

### Environment Variable Interpolation

Config values support `${VAR_NAME}` syntax to read from environment variables:

```yaml
llm:
  api_key: ${GEMINI_API_KEY}  # Reads GEMINI_API_KEY env var
```

This keeps sensitive data (API keys) out of config files.

---

## Analysis Levels (CLI)

> **Note:** Analysis levels (minimal/fast/standard/deep) are planned for future implementation.

```bash
# Future: process with different analysis levels
filekor sidecar ./docs --level minimal  # hash only
filekor sidecar ./docs --level fast    # metadata only
filekor sidecar ./docs --level standard  # metadata + content (current)
filekor sidecar ./docs --level deep   # metadata + content + LLM
```

---

## Usage Examples

```bash
# 1. Process directory with parallel workers
filekor sidecar ./proyecto/ --dir

# 2. Watch mode for real-time progress
filekor sidecar ./proyecto/ --dir --watch

# 3. Quick preview of a single file
filekor preview ./proyecto/contrato.pdf

# 4. Generate all sidecars with custom workers
filekor sidecar ./proyecto/ --dir --workers 8

# 5. Add labels to all files in directory
filekor labels ./proyecto/ --dir

# 6. View status of processed files
filekor status ./proyecto/
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Argument error |
| 3 | File not found |
| 4 | Corrupted cache |
| 5 | Permission error |