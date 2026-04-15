"""Database module for filekor SQLite storage.

This module provides a singleton Database class for managing SQLite connections,
schema initialization, and CRUD operations for file metadata and labels.

Example usage:
    >>> from filekor.db import get_db, sync_file, query_by_label
    >>> db = get_db()
    >>> sync_file("/path/to/file.kor")
    >>> files = query_by_label("finance")
"""

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from filekor.models import DBFile, DBLabel

logger = logging.getLogger(__name__)

# Default database path
DB_PATH = Path.home() / ".filekor" / "index.db"

# Schema version for migrations
SCHEMA_VERSION = 1

# SQL Schema definitions
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kor_path TEXT UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    name TEXT NOT NULL,
    extension TEXT,
    size_bytes INTEGER,
    modified_at TIMESTAMP,
    hash_sha256 TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    confidence REAL,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_labels_label ON labels(label);
CREATE INDEX IF NOT EXISTS idx_labels_file_id ON labels(file_id);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path);
"""


class Database:
    """Thread-safe singleton database manager for SQLite.

    This class uses the double-checked locking pattern to ensure
    thread-safe singleton initialization while maintaining performance.

    Attributes:
        _instance: The singleton instance (class attribute).
        _lock: Threading lock for singleton creation (class attribute).
        _initialized: Whether this instance has been initialized.
        _path: Path to the SQLite database file.
        _local: Thread-local storage for connections.
    """

    _instance: Optional["Database"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, path: Optional[Path] = None) -> "Database":
        """Create or return the singleton instance.

        Uses double-checked locking for thread-safe singleton creation.

        Args:
            path: Optional custom database path.

        Returns:
            The singleton Database instance.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check after acquiring lock
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, path: Optional[Path] = None) -> None:
        """Initialize the database instance.

        This is idempotent - if already initialized, it does nothing.

        Args:
            path: Optional custom database path (default: ~/.filekor/index.db).
        """
        if self._initialized:
            return

        self._path = path or DB_PATH
        self._local = threading.local()
        self._connection_lock = threading.Lock()

        # Ensure directory exists
        self._ensure_directory()

        # Initialize schema
        self._init_schema()

        self._initialized = True
        logger.debug(f"Database initialized at {self._path}")

    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _init_schema(self) -> None:
        """Initialize the database schema.

        Creates tables and indexes if they don't exist.
        Also sets up schema version tracking.
        """
        with self._get_connection() as conn:
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")

            # Create schema
            conn.executescript(SCHEMA_SQL)

            # Set schema version if not set
            cursor = conn.execute(
                "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get a database connection (context manager).

        Uses thread-local storage to ensure each thread has its own
        connection while maintaining thread safety.

        Yields:
            sqlite3.Connection: A SQLite connection object.

        Raises:
            sqlite3.Error: If connection fails.
        """
        # Check if this thread already has a connection
        if not hasattr(self._local, "connection") or self._local.connection is None:
            # Create new connection for this thread
            self._local.connection = sqlite3.connect(
                str(self._path),
                check_same_thread=False,  # We handle thread safety ourselves
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            # Return rows as sqlite3.Row for dict-like access
            self._local.connection.row_factory = sqlite3.Row
            # Enable foreign keys for this connection
            self._local.connection.execute("PRAGMA foreign_keys = ON")

        try:
            yield self._local.connection
        except Exception:
            self._local.connection.rollback()
            raise

    def close(self) -> None:
        """Close the database connection.

        This closes the connection for the current thread.
        Should be called when done using the database.
        """
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
            logger.debug("Database connection closed")

    def close_all(self) -> None:
        """Close all database connections.

        Note: This only affects the current thread's connection.
        For true multi-threaded cleanup, each thread should call close().
        """
        self.close()

    def sync_file(self, kor_path: str) -> int:
        """Synchronize a .kor file into the database.

        This performs an atomic upsert operation:
        1. Parse the .kor file
        2. Insert or update the file record
        3. Delete old labels for this file
        4. Insert new labels

        Args:
            kor_path: Path to the .kor sidecar file.

        Returns:
            file_id: The ID of the inserted/updated file record.

        Raises:
            FileNotFoundError: If the .kor file doesn't exist.
            ValueError: If the .kor file is invalid.
            sqlite3.Error: If database operation fails.
        """
        from filekor.sidecar import Sidecar

        kor_file = Path(kor_path)
        if not kor_file.exists():
            raise FileNotFoundError(f"Sidecar file not found: {kor_path}")

        # Parse the .kor file
        sidecar = Sidecar.load(kor_path)

        with self._get_connection() as conn:
            try:
                # Begin transaction
                conn.execute("BEGIN")

                # Prepare metadata JSON
                metadata_dict = {}
                if sidecar.metadata:
                    metadata_dict = {
                        "author": sidecar.metadata.author,
                        "created": sidecar.metadata.created.isoformat()
                        if sidecar.metadata.created
                        else None,
                        "pages": sidecar.metadata.pages,
                    }

                # Insert or replace file record
                cursor = conn.execute(
                    """
                    INSERT OR REPLACE INTO files 
                    (kor_path, file_path, name, extension, size_bytes, modified_at, hash_sha256, metadata_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(kor_file.resolve()),
                        sidecar.file.path,
                        sidecar.file.name,
                        sidecar.file.extension,
                        sidecar.file.size_bytes,
                        sidecar.file.modified_at,
                        sidecar.file.hash_sha256,
                        json.dumps(metadata_dict) if metadata_dict else None,
                        datetime.now(timezone.utc),
                    ),
                )

                # Get the file_id
                file_id = cursor.lastrowid

                # If it was an UPDATE, lastrowid might be None, so query for it
                if file_id is None:
                    cursor = conn.execute(
                        "SELECT id FROM files WHERE kor_path = ?",
                        (str(kor_file.resolve()),),
                    )
                    row = cursor.fetchone()
                    if row:
                        file_id = row["id"]

                # Delete old labels for this file
                conn.execute("DELETE FROM labels WHERE file_id = ?", (file_id,))

                # Insert new labels
                if sidecar.labels and sidecar.labels.suggested:
                    for label in sidecar.labels.suggested:
                        conn.execute(
                            """
                            INSERT INTO labels (file_id, label, confidence, source)
                            VALUES (?, ?, ?, ?)
                            """,
                            (file_id, label, None, sidecar.labels.source),
                        )

                # Commit transaction
                conn.commit()

                logger.debug(f"Synced file {kor_path} with ID {file_id}")
                return file_id

            except Exception:
                conn.rollback()
                raise

    def query_by_label(self, label: str) -> List[str]:
        """Query file paths by label.

        Args:
            label: The label name to search for.

        Returns:
            List of file paths that have the specified label.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT f.file_path 
                FROM files f 
                JOIN labels l ON f.id = l.file_id 
                WHERE l.label = ?
                ORDER BY f.file_path
                """,
                (label,),
            )
            return [row["file_path"] for row in cursor.fetchall()]

    def query_all(self) -> List[Dict[str, Any]]:
        """Query all files with their labels.

        Returns:
            List of dictionaries containing file info and labels.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT f.*, GROUP_CONCAT(l.label, ',') as labels
                FROM files f
                LEFT JOIN labels l ON f.id = l.file_id
                GROUP BY f.id
                ORDER BY f.file_path
                """
            )

            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                # Parse labels
                labels_str = row_dict.pop("labels", None)
                row_dict["labels"] = labels_str.split(",") if labels_str else []
                results.append(row_dict)

            return results

    def get_file_by_path(self, file_path: str) -> Optional[DBFile]:
        """Get a file record by its path.

        Args:
            file_path: The file path to look up.

        Returns:
            DBFile instance if found, None otherwise.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM files WHERE file_path = ?", (file_path,)
            )
            row = cursor.fetchone()

            if row:
                return DBFile(**dict(row))
            return None

    def get_labels_for_file(self, file_id: int) -> List[DBLabel]:
        """Get all labels for a file.

        Args:
            file_id: The file ID.

        Returns:
            List of DBLabel instances.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM labels WHERE file_id = ?", (file_id,))
            return [DBLabel(**dict(row)) for row in cursor.fetchall()]

    def delete_file(self, file_path: str) -> bool:
        """Delete a file record and its labels.

        Args:
            file_path: The file path to delete.

        Returns:
            True if a record was deleted, False otherwise.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM files WHERE file_path = ?", (file_path,))
            conn.commit()
            return cursor.rowcount > 0


# Module-level singleton accessor
_db_instance: Optional[Database] = None
_db_lock = threading.Lock()


def get_db(path: Optional[Path] = None) -> Database:
    """Get the singleton Database instance.

    This function provides lazy initialization of the Database singleton.
    The first call creates and initializes the database, subsequent calls
    return the same instance.

    Args:
        path: Optional custom database path.

    Returns:
        The singleton Database instance.

    Example:
        >>> db = get_db()
        >>> db.sync_file("/path/to/file.kor")
    """
    global _db_instance

    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = Database(path)

    return _db_instance


def sync_file(kor_path: str, db: Optional[Database] = None) -> int:
    """Convenience function to sync a .kor file to the database.

    Args:
        kor_path: Path to the .kor sidecar file.
        db: Optional Database instance (uses singleton if not provided).

    Returns:
        file_id: The ID of the inserted/updated file record.

    Example:
        >>> from filekor.db import sync_file
        >>> sync_file("/path/to/document.kor")
    """
    if db is None:
        db = get_db()
    return db.sync_file(kor_path)


def query_by_label(label: str, db: Optional[Database] = None) -> List[str]:
    """Convenience function to query files by label.

    Args:
        label: The label name to search for.
        db: Optional Database instance (uses singleton if not provided).

    Returns:
        List of file paths matching the label.

    Example:
        >>> from filekor.db import query_by_label
        >>> files = query_by_label("finance")
        >>> print(files)
        ['/path/to/budget.pdf', '/path/to/invoice.pdf']
    """
    if db is None:
        db = get_db()
    return db.query_by_label(label)


def query_all(db: Optional[Database] = None) -> List[Dict[str, Any]]:
    """Convenience function to query all files.

    Args:
        db: Optional Database instance (uses singleton if not provided).

    Returns:
        List of dictionaries containing file info and labels.
    """
    if db is None:
        db = get_db()
    return db.query_all()


def close_db(db: Optional[Database] = None) -> None:
    """Convenience function to close the database.

    Args:
        db: Optional Database instance (uses singleton if not provided).
    """
    if db is None:
        db = get_db()
    db.close()
