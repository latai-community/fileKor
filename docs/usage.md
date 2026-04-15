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
| `process` | Legacy - extract metadata |

---

## Extract

Extract text content from PDF, TXT, or MD files.

```bash
filekor extract <path>

# Extract to file
filekor extract <path> -o <output>

# Show help
filekor extract --help
```

**Options:**
| Option | Description |
|--------|-------------|
| `-o`, `--output` | Output file path |

---

## Sidecar

Generate a `.kor` YAML sidecar file with metadata.

```bash
filekor sidecar <path>

# Custom output path
filekor sidecar <path> -o <output>

# Force regeneration (ignore existing .kor)
filekor sidecar <path> --no-cache

# Custom config.yaml for LLM (if needed in future)
filekor sidecar <path> -c <config.yaml>

# Verbose output
filekor sidecar <path> --verbose
```

**Options:**
| Option | Description |
|--------|-------------|
| `-o`, `--output` | Output .kor file path |
| `--no-cache` | Force regeneration |
| `-c`, `--config` | Custom config.yaml path |
| `-v`, `--verbose` | Show detailed output |

**Output:** Creates `{filename}.kor` in same directory.

---

## Labels

Add taxonomy labels to a file using LLM. Creates or updates `.kor` file.

```bash
filekor labels <path>

# With custom config.yaml for LLM
filekor labels <path> --llm-config <config.yaml>

# With custom taxonomy (labels.properties)
filekor labels <path> -c <labels.properties>

# Verbose output
filekor labels <path> --verbose
```

**Options:**
| Option | Description |
|--------|-------------|
| `-c`, `--config` | Custom labels.properties path |
| `--llm-config` | Custom config.yaml path |
| `-v`, `--verbose` | Show detailed output |

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