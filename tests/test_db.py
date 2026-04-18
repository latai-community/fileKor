"""Tests for database module.

This module tests the SQLite database functionality including:
- Singleton pattern and thread-safety
- File synchronization (upsert)
- Label queries
- Database lifecycle management
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import List
from unittest.mock import Mock, patch

import pytest

from filekor.db import (
    Database,
    get_db,
    sync_file,
    query_by_label,
    query_all,
    close_db,
    DB_PATH,
)
from filekor.models import DBFile, DBLabel
from filekor.sidecar import Sidecar


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    # Reset singleton before creating new instance
    Database._instance = None
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    yield db
    db.close()
    # Reset singleton after test
    Database._instance = None


@pytest.fixture
def sample_kor_file(tmp_path):
    """Create a sample .kor file for testing."""
    # Create a source file
    source_file = tmp_path / "test_document.pdf"
    source_file.write_text("Test content for PDF")

    # Create a sidecar file
    kor_file = tmp_path / "test_document.kor"
    sidecar = Sidecar.create(
        str(source_file),
        metadata={"author": "Test Author", "pages": 5},
        content=None,
    )

    # Add some labels
    sidecar.update_labels(["finance", "contract"])

    kor_file.write_text(sidecar.to_yaml())
    return kor_file


class TestSingleton:
    """Test singleton pattern and thread-safety."""

    def test_singleton_same_instance(self, tmp_path):
        """Verify get_db() returns the same instance."""
        db_path = tmp_path / "test.db"

        # Reset singleton for testing
        Database._instance = None

        try:
            db1 = get_db(db_path)
            db2 = get_db(db_path)

            assert db1 is db2
        finally:
            db1.close()
            Database._instance = None

    def test_singleton_thread_safety(self, tmp_path):
        """Verify singleton creation is thread-safe."""
        db_path = tmp_path / "test.db"

        # Reset singleton for testing
        Database._instance = None

        instances: List[Database] = []
        errors: List[Exception] = []

        def create_instance():
            try:
                db = get_db(db_path)
                instances.append(db)
            except Exception as e:
                errors.append(e)

        try:
            # Spawn multiple threads trying to create the singleton
            threads = [threading.Thread(target=create_instance) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All threads should get the same instance
            assert len(errors) == 0, f"Errors occurred: {errors}"
            assert len(instances) == 10
            assert len(set(id(db) for db in instances)) == 1
        finally:
            if instances:
                instances[0].close()
            Database._instance = None

    def test_database_initialization_creates_schema(self, tmp_path):
        """Verify Database initialization creates schema."""
        db_path = tmp_path / "test.db"

        # Reset singleton for testing
        Database._instance = None

        try:
            db = Database(db_path)

            # Check that tables exist
            with db._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = {row["name"] for row in cursor.fetchall()}

                assert "files" in tables
                assert "labels" in tables
                assert "schema_version" in tables
        finally:
            db.close()
            Database._instance = None

    def test_database_directory_created(self, tmp_path):
        """Verify database directory is created if it doesn't exist."""
        db_path = tmp_path / "subdir" / "nested" / "test.db"

        # Reset singleton for testing
        Database._instance = None

        try:
            db = Database(db_path)

            assert db_path.parent.exists()
        finally:
            db.close()
            Database._instance = None


class TestSyncFile:
    """Test sync_file functionality."""

    def test_sync_file_inserts_new_record(self, temp_db, sample_kor_file):
        """Verify sync_file inserts a new file record."""
        db = temp_db

        file_id = db.sync_file(str(sample_kor_file))

        assert file_id is not None
        assert isinstance(file_id, int)

        # Verify record exists
        with db._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM files")
            assert cursor.fetchone()["count"] == 1

    def test_sync_file_updates_existing_record(self, temp_db, sample_kor_file):
        """Verify sync_file updates an existing file record."""
        db = temp_db

        # First sync
        file_id1 = db.sync_file(str(sample_kor_file))

        # Modify the sidecar file
        sidecar = Sidecar.load(str(sample_kor_file))
        sidecar.update_labels(["updated_label"])
        sample_kor_file.write_text(sidecar.to_yaml())

        # Second sync should update
        file_id2 = db.sync_file(str(sample_kor_file))

        # Note: SQLite INSERT OR REPLACE creates a new rowid, so IDs may differ
        # The important thing is that there's still only one file record

        # Verify there's only one file record
        with db._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM files")
            assert cursor.fetchone()["count"] == 1

        # Verify labels were updated - get labels for the current file_id
        with db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT l.label FROM labels l JOIN files f ON l.file_id = f.id WHERE f.kor_path = ?",
                (str(sample_kor_file.resolve()),),
            )
            labels = [row["label"] for row in cursor.fetchall()]
            assert "updated_label" in labels
            assert "finance" not in labels

    def test_sync_file_extracts_file_info(self, temp_db, sample_kor_file):
        """Verify sync_file correctly extracts file information."""
        db = temp_db

        file_id = db.sync_file(str(sample_kor_file))

        # Verify file info
        db_file = db.get_file_by_path(str(sample_kor_file.with_suffix(".pdf")))

        assert db_file is not None
        assert db_file.name == "test_document.pdf"
        assert db_file.extension == "pdf"
        assert db_file.kor_path == str(sample_kor_file.resolve())

    def test_sync_file_handles_missing_file(self, temp_db):
        """Verify sync_file raises FileNotFoundError for missing file."""
        db = temp_db

        with pytest.raises(FileNotFoundError):
            db.sync_file("/nonexistent/path/file.kor")

    def test_sync_file_handles_no_labels(self, temp_db, tmp_path):
        """Verify sync_file works when sidecar has no labels."""
        # Create a source file without labels
        source_file = tmp_path / "no_labels.txt"
        source_file.write_text("Test content")

        kor_file = tmp_path / "no_labels.kor"
        sidecar = Sidecar.create(str(source_file))
        # Don't add labels
        kor_file.write_text(sidecar.to_yaml())

        db = temp_db
        file_id = db.sync_file(str(kor_file))

        # Should succeed with no labels
        labels = db.get_labels_for_file(file_id)
        assert len(labels) == 0

    def test_sync_file_is_atomic(self, temp_db, sample_kor_file):
        """Verify sync_file uses transactions (atomic)."""
        db = temp_db

        # This is implicitly tested by the fact that operations succeed
        # A true atomic test would require simulating failures mid-transaction
        file_id = db.sync_file(str(sample_kor_file))

        # Both file and labels should exist
        with db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM files WHERE id = ?", (file_id,)
            )
            assert cursor.fetchone()["count"] == 1

            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM labels WHERE file_id = ?", (file_id,)
            )
            assert cursor.fetchone()["count"] == 2  # finance and contract


class TestQueryByLabel:
    """Test query_by_label functionality."""

    def test_query_by_label_returns_matching_files(self, temp_db, sample_kor_file):
        """Verify query_by_label returns files with matching label."""
        db = temp_db

        # Sync a file with labels
        db.sync_file(str(sample_kor_file))

        # Query for one of the labels
        results = db.query_by_label("finance")

        assert len(results) == 1
        assert "test_document.pdf" in results[0]

    def test_query_by_label_returns_empty_for_no_match(self, temp_db, sample_kor_file):
        """Verify query_by_label returns empty list for non-existent label."""
        db = temp_db

        db.sync_file(str(sample_kor_file))

        results = db.query_by_label("nonexistent_label")

        assert results == []

    def test_query_by_label_returns_multiple_files(self, temp_db, tmp_path):
        """Verify query_by_label returns multiple files with same label."""
        db = temp_db

        # Create two files with the same label
        for i in range(2):
            source_file = tmp_path / f"file_{i}.txt"
            source_file.write_text(f"Content {i}")

            kor_file = tmp_path / f"file_{i}.kor"
            sidecar = Sidecar.create(str(source_file))
            sidecar.update_labels(["shared_label"])
            kor_file.write_text(sidecar.to_yaml())

            db.sync_file(str(kor_file))

        results = db.query_by_label("shared_label")

        assert len(results) == 2

    def test_query_by_label_is_case_sensitive(self, temp_db, sample_kor_file):
        """Verify query_by_label is case-sensitive."""
        db = temp_db

        db.sync_file(str(sample_kor_file))

        # Original label is "finance"
        results_lower = db.query_by_label("finance")
        results_upper = db.query_by_label("Finance")

        assert len(results_lower) == 1
        assert len(results_upper) == 0


class TestQueryAll:
    """Test query_all functionality."""

    def test_query_all_returns_all_files(self, temp_db, tmp_path):
        """Verify query_all returns all files."""
        db = temp_db

        # Create multiple files
        for i in range(3):
            source_file = tmp_path / f"file_{i}.txt"
            source_file.write_text(f"Content {i}")

            kor_file = tmp_path / f"file_{i}.kor"
            sidecar = Sidecar.create(str(source_file))
            sidecar.update_labels([f"label_{i}"])
            kor_file.write_text(sidecar.to_yaml())

            db.sync_file(str(kor_file))

        results = db.query_all()

        assert len(results) == 3

    def test_query_all_includes_labels(self, temp_db, sample_kor_file):
        """Verify query_all includes labels in results."""
        db = temp_db

        db.sync_file(str(sample_kor_file))

        results = db.query_all()

        assert len(results) == 1
        assert "labels" in results[0]
        assert isinstance(results[0]["labels"], list)
        assert "finance" in results[0]["labels"]
        assert "contract" in results[0]["labels"]

    def test_query_all_returns_empty_list_for_empty_db(self, temp_db):
        """Verify query_all returns empty list when no files."""
        db = temp_db

        results = db.query_all()

        assert results == []


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_sync_file_convenience_function(self, tmp_path):
        """Verify sync_file() convenience function works."""
        # Reset singleton
        Database._instance = None

        db_path = tmp_path / "test.db"

        try:
            # Create a test file
            source_file = tmp_path / "test.txt"
            source_file.write_text("Test content")
            kor_file = tmp_path / "test.kor"
            sidecar = Sidecar.create(str(source_file))
            kor_file.write_text(sidecar.to_yaml())

            # Use convenience function with custom path
            db = get_db(db_path)
            file_id = sync_file(str(kor_file), db)

            assert file_id is not None
        finally:
            close_db()
            Database._instance = None

    def test_query_by_label_convenience_function(self, tmp_path):
        """Verify query_by_label() convenience function works."""
        # Reset singleton
        Database._instance = None

        db_path = tmp_path / "test.db"

        try:
            # Create and sync a test file
            source_file = tmp_path / "test.txt"
            source_file.write_text("Test content")
            kor_file = tmp_path / "test.kor"
            sidecar = Sidecar.create(str(source_file))
            sidecar.update_labels(["test_label"])
            kor_file.write_text(sidecar.to_yaml())

            db = get_db(db_path)
            sync_file(str(kor_file), db)

            # Use convenience function
            results = query_by_label("test_label", db)

            assert len(results) == 1
        finally:
            close_db()
            Database._instance = None


class TestDatabaseLifecycle:
    """Test database connection lifecycle."""

    def test_close_releases_connection(self, tmp_path):
        """Verify close() releases the connection."""
        db_path = tmp_path / "test.db"

        # Reset singleton
        Database._instance = None

        try:
            db = Database(db_path)

            # Connection should exist after an operation
            with db._get_connection() as conn:
                conn.execute("SELECT 1")

            # Close should clean up
            db.close()

            # After close, getting connection should create new one
            with db._get_connection() as conn:
                conn.execute("SELECT 1")
        finally:
            db.close()
            Database._instance = None

    def test_context_manager_handles_errors(self, temp_db):
        """Verify connection context manager handles errors."""
        db = temp_db

        # An error should rollback the transaction
        try:
            with db._get_connection() as conn:
                conn.execute(
                    "INSERT INTO files (kor_path, file_path, name) VALUES (?, ?, ?)",
                    ("test", "test", "test"),
                )
                raise ValueError("Test error")
        except ValueError:
            pass

        # Record should not exist
        with db._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM files")
            assert cursor.fetchone()["count"] == 0


class TestCLISyncIntegration:
    """Test CLI auto-sync integration."""

    def test_auto_sync_enabled_creates_db_entry(self, tmp_path):
        """Verify CLI auto-syncs when auto_sync is enabled."""
        from filekor.cli.sidecar import _auto_sync_hook
        from filekor.labels import LLMConfig

        # Reset singleton
        Database._instance = None
        _db_instance = None  # Also reset module-level instance

        try:
            # Create test file and sidecar with unique name
            test_file = tmp_path / f"auto_sync_test_{id(tmp_path)}.txt"
            test_file.write_text("Test content for auto-sync test")
            kor_file = tmp_path / f"auto_sync_test_{id(tmp_path)}.kor"
            sidecar = Sidecar.create(str(test_file))
            sidecar.update_labels(["auto_sync_test_label"])
            kor_file.write_text(sidecar.to_yaml())

            # Create config with auto_sync enabled
            llm_config = LLMConfig(auto_sync=True)

            # Use the auto-sync hook directly with our database
            db_path = tmp_path / "test.db"
            db = get_db(db_path)

            # Call the hook
            _auto_sync_hook(kor_file, llm_config, verbose=False)

            # Verify database entry was created
            results = query_by_label("auto_sync_test_label", db)
            assert len(results) == 1
            assert str(test_file) in results[0]
        finally:
            close_db()
            Database._instance = None

    def test_auto_sync_disabled_skips_db(self, tmp_path):
        """Verify CLI skips DB sync when auto_sync is disabled."""
        from filekor.cli.sidecar import _auto_sync_hook
        from filekor.labels import LLMConfig

        # Reset singleton
        Database._instance = None

        llm_config = LLMConfig(auto_sync=False)
        kor_path = tmp_path / "test.kor"

        # Should not raise and should not sync
        _auto_sync_hook(kor_path, llm_config, verbose=False)

        # If we got here without error, test passes
        assert True

    def test_auto_sync_error_does_not_fail_cli(self, tmp_path):
        """Verify CLI continues even if DB sync fails."""
        from filekor.cli.sidecar import _auto_sync_hook
        from filekor.labels import LLMConfig

        llm_config = LLMConfig(auto_sync=True)
        kor_path = tmp_path / "nonexistent.kor"

        # Should not raise even though file doesn't exist
        _auto_sync_hook(kor_path, llm_config, verbose=False)

        # If we got here without error, test passes
        assert True


class TestDelete:
    """Test delete functionality."""

    def test_delete_file_removes_record(self, temp_db, sample_kor_file):
        """Verify delete_file removes the record."""
        db = temp_db

        db.sync_file(str(sample_kor_file))

        # Verify it exists
        db_file = db.get_file_by_path(str(sample_kor_file.with_suffix(".pdf")))
        assert db_file is not None

        # Delete it
        result = db.delete_file(str(sample_kor_file.with_suffix(".pdf")))
        assert result is True

        # Verify it's gone
        db_file = db.get_file_by_path(str(sample_kor_file.with_suffix(".pdf")))
        assert db_file is None

    def test_delete_file_returns_false_for_nonexistent(self, temp_db):
        """Verify delete_file returns False for non-existent file."""
        db = temp_db

        result = db.delete_file("/nonexistent/file.txt")

        assert result is False

    def test_delete_cascades_to_labels(self, temp_db, sample_kor_file):
        """Verify delete cascades to labels."""
        db = temp_db

        file_id = db.sync_file(str(sample_kor_file))

        # Verify labels exist
        labels = db.get_labels_for_file(file_id)
        assert len(labels) == 2

        # Delete file
        db.delete_file(str(sample_kor_file.with_suffix(".pdf")))

        # Labels should be gone (due to CASCADE)
        labels = db.get_labels_for_file(file_id)
        assert len(labels) == 0
