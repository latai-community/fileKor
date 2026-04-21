"""Tests for core/events.py — EventType, FilekorEvent, EventEmitter, create_emitter."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from filekor.core.events import (
    EventEmitter,
    EventType,
    FilekorEvent,
    create_emitter,
)


class TestEventType:
    def test_enum_values(self):
        """EventType enum contains all expected values."""
        assert EventType.STARTED.value == "started"
        assert EventType.PROCESSING.value == "processing"
        assert EventType.COMPLETED.value == "completed"
        assert EventType.ERROR.value == "error"
        assert EventType.FINISHED.value == "finished"
        assert EventType.STATUS.value == "status"


class TestFilekorEventCreate:
    def test_timestamp_format(self):
        """create generates an ISO timestamp ending in Z."""
        event = FilekorEvent.create(EventType.STARTED, directory="/tmp")

        assert event.type == EventType.STARTED
        assert event.timestamp.endswith("Z")
        # Verify it's parseable
        dt = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        assert isinstance(dt, datetime)

    def test_data_payload(self):
        """create stores extra kwargs in data."""
        event = FilekorEvent.create(EventType.ERROR, file_path="a.txt", error="boom")

        assert event.data == {"file_path": "a.txt", "error": "boom"}


class TestEventEmitterInit:
    def test_disabled_no_output(self):
        """Default emitter is disabled and has no output file."""
        emitter = EventEmitter()

        assert emitter.enabled is False
        assert emitter.output_file is None
        assert all(handlers == [] for handlers in emitter._handlers.values())

    def test_enabled_with_output_file(self, tmp_path):
        """Emitter can be enabled and point to an output file."""
        out = tmp_path / "events.jsonl"
        emitter = EventEmitter(enabled=True, output_file=out)

        assert emitter.enabled is True
        assert emitter.output_file == out


class TestEventEmitterOnOff:
    def test_on_registers_handler(self):
        """on() appends a handler for the given event type."""
        emitter = EventEmitter(enabled=True)
        handler = MagicMock()

        emitter.on(EventType.COMPLETED, handler)

        assert handler in emitter._handlers[EventType.COMPLETED]

    def test_off_removes_handler(self):
        """off() removes a previously registered handler."""
        emitter = EventEmitter(enabled=True)
        handler = MagicMock()
        emitter.on(EventType.COMPLETED, handler)

        emitter.off(EventType.COMPLETED, handler)

        assert handler not in emitter._handlers[EventType.COMPLETED]

    def test_off_unknown_handler_no_error(self):
        """off() on a non-registered handler does not raise."""
        emitter = EventEmitter(enabled=True)
        handler = MagicMock()

        emitter.off(EventType.COMPLETED, handler)  # Should not raise


class TestEventEmitterEmit:
    def test_emit_disabled_does_nothing(self):
        """emit() returns immediately when disabled."""
        emitter = EventEmitter(enabled=False)
        handler = MagicMock()
        emitter.on(EventType.STARTED, handler)
        event = FilekorEvent.create(EventType.STARTED, directory="/tmp")

        emitter.emit(event)

        handler.assert_not_called()

    def test_emit_calls_handlers(self):
        """emit() invokes all registered handlers for the event type."""
        emitter = EventEmitter(enabled=True)
        handler1 = MagicMock()
        handler2 = MagicMock()
        emitter.on(EventType.STARTED, handler1)
        emitter.on(EventType.STARTED, handler2)
        event = FilekorEvent.create(EventType.STARTED, directory="/tmp")

        emitter.emit(event)

        handler1.assert_called_once_with(event)
        handler2.assert_called_once_with(event)

    def test_emit_ignores_handler_errors(self):
        """emit() swallows exceptions from individual handlers."""
        emitter = EventEmitter(enabled=True)
        bad_handler = MagicMock(side_effect=RuntimeError("boom"))
        good_handler = MagicMock()
        emitter.on(EventType.STARTED, bad_handler)
        emitter.on(EventType.STARTED, good_handler)
        event = FilekorEvent.create(EventType.STARTED, directory="/tmp")

        emitter.emit(event)  # Should not raise

        bad_handler.assert_called_once()
        good_handler.assert_called_once()

    def test_emit_writes_to_output_file(self, tmp_path):
        """emit() appends JSON lines to output_file when configured."""
        out = tmp_path / "events.jsonl"
        emitter = EventEmitter(enabled=True, output_file=out)
        event = FilekorEvent.create(EventType.FINISHED, total=1, successful=1, failed=0)

        with patch(
            "filekor.core.events.json.dumps", return_value='{"type":"finished"}'
        ):
            emitter.emit(event)

        lines = out.read_text().strip().splitlines()
        assert len(lines) == 1
        written = json.loads(lines[0])
        assert written["type"] == "finished"

    def test_emit_creates_parent_directories(self, tmp_path):
        """emit() creates parent directories for output_file if needed."""
        out = tmp_path / "deep" / "nested" / "events.jsonl"
        emitter = EventEmitter(enabled=True, output_file=out)
        event = FilekorEvent.create(
            EventType.STATUS, directory="/tmp", files=[], kor_files=[]
        )

        emitter.emit(event)

        assert out.exists()

    def test_emit_file_write_error_silenced(self, tmp_path):
        """File write errors during emit are silently ignored."""
        out = tmp_path / "events.jsonl"
        emitter = EventEmitter(enabled=True, output_file=out)
        event = FilekorEvent.create(EventType.STARTED, directory="/tmp", total_files=0)

        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            emitter.emit(event)  # Should not raise


class TestConvenienceMethods:
    def test_started(self):
        """started() emits a STARTED event."""
        emitter = EventEmitter(enabled=True)
        handler = MagicMock()
        emitter.on(EventType.STARTED, handler)

        emitter.started("/tmp", 5)

        event = handler.call_args[0][0]
        assert event.type == EventType.STARTED
        assert event.data["directory"] == "/tmp"
        assert event.data["total_files"] == 5

    def test_processing(self):
        """processing() emits a PROCESSING event."""
        emitter = EventEmitter(enabled=True)
        handler = MagicMock()
        emitter.on(EventType.PROCESSING, handler)

        emitter.processing("a.txt", 0, 3)

        event = handler.call_args[0][0]
        assert event.type == EventType.PROCESSING
        assert event.data["file_path"] == "a.txt"
        assert event.data["file_index"] == 0
        assert event.data["total"] == 3

    def test_completed(self):
        """completed() emits a COMPLETED event with labels."""
        emitter = EventEmitter(enabled=True)
        handler = MagicMock()
        emitter.on(EventType.COMPLETED, handler)

        emitter.completed("a.txt", "a.txt.kor", labels=["finance"])

        event = handler.call_args[0][0]
        assert event.type == EventType.COMPLETED
        assert event.data["file_path"] == "a.txt"
        assert event.data["output_path"] == "a.txt.kor"
        assert event.data["labels"] == ["finance"]

    def test_completed_no_labels(self):
        """completed() defaults labels to empty list."""
        emitter = EventEmitter(enabled=True)
        handler = MagicMock()
        emitter.on(EventType.COMPLETED, handler)

        emitter.completed("a.txt", "a.txt.kor")

        event = handler.call_args[0][0]
        assert event.data["labels"] == []

    def test_error(self):
        """error() emits an ERROR event."""
        emitter = EventEmitter(enabled=True)
        handler = MagicMock()
        emitter.on(EventType.ERROR, handler)

        emitter.error("b.txt", "something failed")

        event = handler.call_args[0][0]
        assert event.type == EventType.ERROR
        assert event.data["file_path"] == "b.txt"
        assert event.data["error"] == "something failed"

    def test_finished(self):
        """finished() emits a FINISHED event."""
        emitter = EventEmitter(enabled=True)
        handler = MagicMock()
        emitter.on(EventType.FINISHED, handler)

        emitter.finished(10, 8, 2)

        event = handler.call_args[0][0]
        assert event.type == EventType.FINISHED
        assert event.data["total"] == 10
        assert event.data["successful"] == 8
        assert event.data["failed"] == 2

    def test_status(self):
        """status() emits a STATUS event."""
        emitter = EventEmitter(enabled=True)
        handler = MagicMock()
        emitter.on(EventType.STATUS, handler)

        emitter.status("/tmp", ["a.txt"], ["a.txt.kor"])

        event = handler.call_args[0][0]
        assert event.type == EventType.STATUS
        assert event.data["directory"] == "/tmp"
        assert event.data["total_files"] == 1
        assert event.data["kor_files"] == 1
        assert event.data["files"] == ["a.txt"]
        assert event.data["kor_file_paths"] == ["a.txt.kor"]


class TestCreateEmitter:
    def test_watch_true(self):
        """create_emitter(watch=True) enables the emitter."""
        emitter = create_emitter(watch=True)

        assert emitter.enabled is True
        assert emitter.output_file is None

    def test_watch_false(self):
        """create_emitter(watch=False) disables the emitter."""
        emitter = create_emitter(watch=False)

        assert emitter.enabled is False

    def test_with_output_file(self, tmp_path):
        """create_emitter with output_file sets it as a Path."""
        out = str(tmp_path / "events.jsonl")
        emitter = create_emitter(watch=True, output_file=out)

        assert emitter.output_file == Path(out)

    def test_without_output_file(self):
        """create_emitter without output_file leaves it None."""
        emitter = create_emitter(watch=True)

        assert emitter.output_file is None
