# LLM-based Labeling

fileKor uses an LLM (Google Gemini) to extract labels based on file content. LLM must be configured before use.

## Config File Search Order

The tool searches for `config.yaml` in this order:

1. Custom path (via `--config` flag)
2. `config.yaml` in current directory
3. `.filekor/config.yaml`
4. `~/.filekor/config.yaml`

## Setup

### 1. Create config file

Create `~/.filekor/config.yaml`:

```yaml
filekor:
  llm:
    enabled: true
    provider: gemini
    api_key: ${GEMINI_API_KEY}
    model: gemini-2.0-flash
    max_content_chars: 1500
```

### 2. Set environment variable

```bash
# Windows
setx GOOGLE_API_KEY "your-api-key-here"

# Linux/Mac
export GOOGLE_API_KEY="your-api-key-here"
```

Or use `${VAR}` syntax in config.yaml to set directly from environment.

## Configuration Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| enabled | Yes | false | Enable LLM labeling |
| provider | No | gemini | LLM provider (gemini, mock) |
| api_key | Yes | - | API key for the provider |
| model | No | gemini-2.0-flash | Model identifier |
| max_content_chars | No | 1500 | Max chars sent to LLM |

## Usage

```bash
# Generate sidecar with LLM labels
filekor sidecar documento.pdf

# Custom config.yaml
filekor sidecar documento.pdf --config /path/to/config.yaml

# Suggest labels (REQUIRED LLM config, will fail if not configured)
filekor labels documento.pdf --llm-config /path/to/config.yaml
```

## Behavior

| LLM Config Status | Sidecar Command | Labels Command |
|--------------------|----------------|----------------|
| Not configured | Generates without labels | ❌ Error |
| Configured, invalid API key | ❌ Error (fails) | ❌ Error (fails) |
| Configured, valid API key | ✅ With labels | ✅ With labels |

## Error Handling

If LLM is not configured:
- **sidecar**: Generates without labels, continues normally
- **labels**: Fails with error (user explicitly requested labels)

## How It Works

1. **Text Extraction**: fileKor extracts the first 1500 characters from the file
2. **Taxonomy Context**: The LLM receives the taxonomy with synonyms as context:
   ```
   - finance: budget, cost, money, financial, billing, invoice
   - contract: agreement, contract, terms, conditions, legal
   - legal: law, compliance, gdpr, privacy, policy, regulation
   ```
3. **LLM Analysis**: Gemini analyzes the content and returns relevant labels
4. **Validation**: Responses are filtered to only valid taxonomy labels

## Error Handling

If LLM is not configured:

```
Error: LLM is not configured. Please enable LLM in config.yaml with a valid API key.
```

## Using Mock Provider (Testing)

For testing without API calls, use the mock provider:

```yaml
filekor:
  llm:
    enabled: true
    provider: mock
    api_key: test-key
```

This returns dummy labels for testing the workflow.

## API Keys

- **Google Gemini**: Get your API key at https://aistudio.google.com/app/apikey