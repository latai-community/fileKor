# filekor - PDF metadata extraction CLI
__version__ = "0.1.0"

# Core exports
from filekor.sidecar import Sidecar, FileInfo, FileMetadata, Content
from filekor.labels import LabelsConfig, LLMConfig, suggest_labels
from filekor.processor import DirectoryProcessor, process_directory, ProcessResult
from filekor.events import EventEmitter, EventType, FilekorEvent, create_emitter
from filekor import status

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
]
