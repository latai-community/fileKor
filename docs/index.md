# fileKor

Local metadata engine that extracts, summarizes, classifies, and tags files using taxonomy-based labeling.

## Index

| Section | Description |
|---------|-------------|
| [Installation](installation.md) | Setup and installation guide |
| [Usage](usage.md) | CLI commands and Library API |
| [Taxonomy](taxonomy.md) | Labels configuration |
| [LLM](llm.md) | LLM-based labeling setup (Gemini, OpenAI, Groq, OpenRouter) |
| [Development](development.md) | Development guide |

---

## Quick Start

```bash
# Install uv
winget install astral-sh.uv

# Setup
uv venv
.venv\Scripts\activate
uv pip install -e .

# Use
filekor extract documento.pdf
filekor sidecar documento.pdf
filekor labels documento.pdf
```

---

## Features

- **Metadata Extraction** - Extract metadata from PDF, TXT, MD files using PyExifTool
- **Text Extraction** - Extract and summarize text content from supported files
- **LLM-based Labeling** - Classify files using LLM (Gemini) with content analysis
- **Sidecar Generation** - Generate YAML sidecar files (.kor) with full metadata
- **CLI Interface** - Simple command-line interface with multiple commands