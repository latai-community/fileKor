"""Event emitter for real-time progress updates and --watch mode."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional


class EventType(Enum):
    """Event types for the emitter."""

    STARTED = "started"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    FINISHED = "finished"
    STATUS = "status"


@dataclass
class FilekorEvent:
    """Event data structure."""

    type: EventType
    timestamp: str
    data: Dict

    @classmethod
    def create(cls, event_type: EventType, **data) -> "FilekorEvent":
        """Create a new event with current timestamp.

        Args:
            event_type: Type of the event.
            **data: Additional event data.

        Returns:
            FilekorEvent instance.
        """
        return cls(
            type=event_type,
            timestamp=datetime.utcnow().isoformat() + "Z",
            data=data,
        )


class EventEmitter:
    """Event emitter for filekor operations.

    Supports real-time progress updates for --watch mode.
    """

    def __init__(self, enabled: bool = False, output_file: Optional[Path] = None):
        """Initialize EventEmitter.

        Args:
            enabled: Whether events are enabled.
            output_file: Optional file to write events to.
        """
        self.enabled = enabled
        self.output_file = output_file
        self._handlers: Dict[EventType, List[Callable[[FilekorEvent], None]]] = {
            event_type: [] for event_type in EventType
        }

    def on(
        self, event_type: EventType, handler: Callable[[FilekorEvent], None]
    ) -> None:
        """Register an event handler.

        Args:
            event_type: Type of event to listen for.
            handler: Callback function for the event.
        """
        self._handlers[event_type].append(handler)

    def off(
        self, event_type: EventType, handler: Callable[[FilekorEvent], None]
    ) -> None:
        """Unregister an event handler.

        Args:
            event_type: Type of event.
            handler: Handler to remove.
        """
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def emit(self, event: FilekorEvent) -> None:
        """Emit an event to all registered handlers.

        Args:
            event: Event to emit.
        """
        if not self.enabled:
            return

        # Call registered handlers
        for handler in self._handlers[event.type]:
            try:
                handler(event)
            except Exception:
                pass  # Ignore handler errors

        # Write to output file if configured
        if self.output_file:
            try:
                self.output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.output_file, "a") as f:
                    f.write(json.dumps(asdict(event)) + "\n")
            except Exception:
                pass  # Ignore file write errors

    # Convenience methods

    def started(self, directory: str, total_files: int) -> None:
        """Emit started event.

        Args:
            directory: Directory being processed.
            total_files: Total number of files to process.
        """
        self.emit(
            FilekorEvent.create(
                EventType.STARTED,
                directory=directory,
                total_files=total_files,
            )
        )

    def processing(self, file_path: str, file_index: int, total: int) -> None:
        """Emit processing event.

        Args:
            file_path: Path to file being processed.
            file_index: Current file index (0-based).
            total: Total number of files.
        """
        self.emit(
            FilekorEvent.create(
                EventType.PROCESSING,
                file_path=file_path,
                file_index=file_index,
                total=total,
            )
        )

    def completed(
        self,
        file_path: str,
        output_path: str,
        labels: Optional[List[str]] = None,
    ) -> None:
        """Emit completed event.

        Args:
            file_path: Original file path.
            output_path: Path to output .kor file.
            labels: Labels generated (if any).
        """
        self.emit(
            FilekorEvent.create(
                EventType.COMPLETED,
                file_path=file_path,
                output_path=output_path,
                labels=labels or [],
            )
        )

    def error(self, file_path: str, error: str) -> None:
        """Emit error event.

        Args:
            file_path: Path to file that failed.
            error: Error message.
        """
        self.emit(
            FilekorEvent.create(
                EventType.ERROR,
                file_path=file_path,
                error=error,
            )
        )

    def finished(self, total: int, successful: int, failed: int) -> None:
        """Emit finished event.

        Args:
            total: Total files processed.
            successful: Number of successful operations.
            failed: Number of failed operations.
        """
        self.emit(
            FilekorEvent.create(
                EventType.FINISHED,
                total=total,
                successful=successful,
                failed=failed,
            )
        )

    def status(self, directory: str, files: List[str], kor_files: List[str]) -> None:
        """Emit status event for status command.

        Args:
            directory: Directory being checked.
            files: List of supported files found.
            kor_files: List of .kor files found.
        """
        self.emit(
            FilekorEvent.create(
                EventType.STATUS,
                directory=directory,
                total_files=len(files),
                kor_files=len(kor_files),
                files=files,
                kor_file_paths=kor_files,
            )
        )


def create_emitter(
    watch: bool = False, output_file: Optional[str] = None
) -> EventEmitter:
    """Create an event emitter based on --watch flag.

    Args:
        watch: Whether to enable watch mode.
        output_file: Optional output file path.

    Returns:
        EventEmitter instance.
    """
    return EventEmitter(
        enabled=watch,
        output_file=Path(output_file) if output_file else None,
    )
