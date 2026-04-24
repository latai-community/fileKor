"""filekor constants — centralize all magic strings."""

from enum import Enum, auto
from pathlib import Path


# ─── Directories ────────────────────────────────────────────────────

FILEKOR_DIR = ".filekor"
"""Name of the sidecar directory (created next to source files)."""

# ─── Extensions ─────────────────────────────────────────────────────

KOR_EXTENSION = ".kor"
"""Extension for sidecar files."""

SUPPORTED_EXTENSIONS = {"pdf", "txt", "md"}
"""Set of supported file extensions (without leading dot)."""

# ─── Filenames ──────────────────────────────────────────────────────

MERGED_KOR_FILENAME = "merged.kor"
"""Default filename for merged sidecar output."""

CONFIG_FILENAME = "config.yaml"
"""Configuration file name."""

LABELS_PROPERTIES_FILENAME = "labels.properties"
"""Default taxonomy file name."""

# ─── Default paths ──────────────────────────────────────────────────

DEFAULT_CONFIG_PATH = Path.home() / FILEKOR_DIR / CONFIG_FILENAME
"""Default path to user-level config."""

DEFAULT_DB_PATH = Path.home() / FILEKOR_DIR / "index.db"
"""Default path to SQLite database."""

# ─── Config YAML keys ───────────────────────────────────────────────

CONFIG_ROOT_KEY = "filekor"
"""Root key in config.yaml."""

CONFIG_DB_KEY = "db"
CONFIG_LLM_KEY = "llm"
CONFIG_WORKERS_KEY = "workers"

# ─── Sidecar YAML field keys ───────────────────────────────────────

FIELD_LABELS = "labels"
FIELD_SUMMARY = "summary"
FIELD_METADATA = "metadata"
FIELD_CONTENT = "content"
FIELD_FILE = "file"
FIELD_PARSER_STATUS = "parser_status"
FIELD_VERSION = "version"

# ─── Delete scopes ──────────────────────────────────────────────────

SCOPE_ALL = "all"
SCOPE_DB = "db"
SCOPE_FILE = "file"


class DeleteScope(Enum):
    """Delete operation scopes."""

    ALL = SCOPE_ALL
    DB = SCOPE_DB
    FILE = SCOPE_FILE


# ─── Output formats ─────────────────────────────────────────────────

FORMAT_TEXT = "text"
FORMAT_JSON = "json"
FORMAT_CSV = "csv"
FORMAT_SHA = "sha"
FORMAT_SEPARATED = "separated"


class OutputFormat(Enum):
    """CLI output formats."""

    TEXT = FORMAT_TEXT
    JSON = FORMAT_JSON
    CSV = FORMAT_CSV
    SHA = FORMAT_SHA
    SEPARATED = FORMAT_SEPARATED


# ─── LLM providers ──────────────────────────────────────────────────

PROVIDER_GEMINI = "gemini"
PROVIDER_GOOGLE = "google"
PROVIDER_GROQ = "groq"
PROVIDER_OPENAI = "openai"
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_MOCK = "mock"


class LLMProvider(Enum):
    """Supported LLM providers."""

    GEMINI = PROVIDER_GEMINI
    GOOGLE = PROVIDER_GOOGLE
    GROQ = PROVIDER_GROQ
    OPENAI = PROVIDER_OPENAI
    OPENROUTER = PROVIDER_OPENROUTER
    MOCK = PROVIDER_MOCK


# ─── LLM API keys ───────────────────────────────────────────────────

LLM_ROLE_USER = "user"
LLM_KEY_ROLE = "role"
LLM_KEY_CONTENT = "content"
LLM_KEY_MESSAGES = "messages"

# ─── DB table names ─────────────────────────────────────────────────

TABLE_FILES = "files"
TABLE_LABELS = "labels"
TABLE_SCHEMA_VERSION = "schema_version"
TABLE_FILES_FTS = "files_fts"

# ─── DB column names ────────────────────────────────────────────────

COL_HASH_SHA256 = "hash_sha256"
COL_EXTENSION = "extension"
COL_FILE_PATH = "file_path"
COL_KOR_PATH = "kor_path"
COL_SIZE_BYTES = "size_bytes"
COL_MODIFIED_AT = "modified_at"
COL_CREATED_AT = "created_at"
COL_UPDATED_AT = "updated_at"
COL_SUMMARY_SHORT = "summary_short"
COL_SUMMARY_LONG = "summary_long"
COL_NAME = "name"
COL_ID = "id"
COL_FILE_ID = "file_id"
COL_LABEL = "label"
COL_SOURCE = "source"

# ─── FTS5 search weights ────────────────────────────────────────────

WEIGHT_LABEL_MATCH = "label_match"
WEIGHT_FILENAME_MATCH = "filename_match"
WEIGHT_KOR_CONTENT_MATCH = "kor_content_match"

# ─── Label source ───────────────────────────────────────────────────

SOURCE_LLM = "llm"

# ─── Default label values ───────────────────────────────────────────

DEFAULT_LABELS: dict[str, list[str]] = {
    "finance": ["budget", "invoice", "payment", "cost", "expense", "financial"],
    "contract": ["agreement", "contract", "terms", "conditions", "legal"],
    "legal": ["law", "compliance", "gdpr", "privacy", "policy", "regulation"],
    "architecture": ["design", "architecture", "blueprint", "structure"],
    "specification": ["spec", "specs", "requirement", "requirements"],
    "documentation": ["docs", "documentation", "manual", "guide", "readme"],
}

# ─── LLM synonym mappings ───────────────────────────────────────────

LLM_SYNONYM_MAPPING: dict[str, str] = {
    "budget": "finance",
    "contract": "legal",
    "invoice": "finance",
}
