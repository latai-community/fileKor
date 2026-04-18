# filekor - PDF metadata extraction CLI
__version__ = "0.1.0"

# Core exports
from filekor.sidecar import Sidecar, FileInfo, FileMetadata, Content
from filekor.core.labels import LabelsConfig, LLMConfig, suggest_labels
from filekor.core.processor import DirectoryProcessor, process_directory, ProcessResult
from filekor.core.events import EventEmitter, EventType, FilekorEvent, create_emitter
from filekor.db import (
    get_db,
    sync_file,
    query_by_label,
    query_by_labels,
    query_all,
    search_content,
    search_files,
    close_db,
    Database,
)
from filekor.core.models.db_models import DBFile, DBLabel, DBCollection
from filekor.core import status

# Core module exports (new - Oct 2025 refactor)
from filekor.core.hasher import calculate_sha256
from filekor.core.delete import (
    delete_by_sha,
    delete_by_path,
    delete_by_input,
    get_deletion_preview,
)
from filekor.core.merge import merge_kor_files, load_merged_kor
from filekor.core.list import (
    list_kor_files,
    list_as_text,
    list_as_json,
    list_as_csv,
    list_sha_only,
)

__all__ = [
    "Sidecar",
    "FileInfo",
    "FileMetadata",
    "Content",
    "LabelsConfig",
    "LLMConfig",
    "suggest_labels",
    "DirectoryProcessor",
    "process_directory",
    "ProcessResult",
    "EventEmitter",
    "EventType",
    "FilekorEvent",
    "create_emitter",
    "status",
    # Database exports
    "get_db",
    "sync_file",
    "query_by_label",
    "query_by_labels",
    "query_all",
    "search_content",
    "search_files",
    "close_db",
    "Database",
    "DBFile",
    "DBLabel",
    "DBCollection",
    # Core module exports
    "calculate_sha256",
    "delete_by_sha",
    "delete_by_path",
    "delete_by_input",
    "get_deletion_preview",
    "merge_kor_files",
    "load_merged_kor",
    "list_kor_files",
    "list_as_text",
    "list_as_json",
    "list_as_csv",
    "list_sha_only",
]
