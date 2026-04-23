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

from filekor.constants import FILEKOR_DIR
from filekor.core.models.db_models import DBFile, DBLabel

logger = logging.getLogger(__name__)

# Default database path
DB_PATH = Path.home() / FILEKOR_DIR / "index.db"

# Schema version for migrations
SCHEMA_VERSION = 3

# SQL Schema definitions
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kor_path TEXT NOT NULL,
    file_path TEXT NOT NULL,
    name TEXT NOT NULL,
    extension TEXT,
    size_bytes INTEGER,
    modified_at TIMESTAMP,
    hash_sha256 TEXT UNIQUE NOT NULL,
    metadata_json TEXT,
    summary_short TEXT,
    summary_long TEXT,
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

-- FTS5 Virtual Table for full-text search (filename + metadata)
CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
    name,
    metadata_json,
    summary_short,
    summary_long,
    content='files',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Trigger: Insert into FTS5 when file is inserted
CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
    INSERT INTO files_fts(rowid, name, metadata_json, summary_short, summary_long)
    VALUES (new.id, new.name, new.metadata_json, new.summary_short, new.summary_long);
END;

-- Trigger: Delete from FTS5 when file is deleted
CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
    INSERT INTO files_fts(files_fts, rowid, name, metadata_json, summary_short, summary_long)
    VALUES ('delete', old.id, old.name, old.metadata_json, old.summary_short, old.summary_long);
END;

-- Trigger: Update FTS5 when file is updated
CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
    INSERT INTO files_fts(files_fts, rowid, name, metadata_json, summary_short, summary_long)
    VALUES ('delete', old.id, old.name, old.metadata_json, old.summary_short, old.summary_long);
    INSERT INTO files_fts(rowid, name, metadata_json, summary_short, summary_long)
    VALUES (new.id, new.name, new.metadata_json, new.summary_short, new.summary_long);
END;
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
            path: Optional custom database path. If None, reads from
                  config.yaml (filekor.db.path) or falls back to
                  ~/.filekor/index.db.
        """
        if self._initialized:
            return

        if path is None:
            from filekor.core.config import FilekorConfig

            config = FilekorConfig.load()
            self._path = config.db_path
        else:
            self._path = path
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
        Also sets up schema version tracking and runs migrations.
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

        # Run migrations for existing databases
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Run database migrations for schema updates.

        Checks the current schema version and applies migrations
        incrementally to bring the database up to date.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            row = cursor.fetchone()
            current_version = row["version"] if row else 0

            if current_version < 2:
                # Migration v2: Add summary columns to files table
                try:
                    conn.execute("ALTER TABLE files ADD COLUMN summary_short TEXT")
                except Exception:
                    pass  # Column already exists

                try:
                    conn.execute("ALTER TABLE files ADD COLUMN summary_long TEXT")
                except Exception:
                    pass  # Column already exists

                # Rebuild FTS index with new columns
                try:
                    conn.executescript("""
                        DROP TRIGGER IF EXISTS files_ai;
                        DROP TRIGGER IF EXISTS files_ad;
                        DROP TRIGGER IF EXISTS files_au;
                        DROP TABLE IF EXISTS files_fts;

                        CREATE VIRTUAL TABLE files_fts USING fts5(
                            name,
                            metadata_json,
                            summary_short,
                            summary_long,
                            content='files',
                            content_rowid='id',
                            tokenize='porter unicode61'
                        );

                        INSERT INTO files_fts(rowid, name, metadata_json, summary_short, summary_long)
                        SELECT id, name, metadata_json, summary_short, summary_long FROM files;

                        CREATE TRIGGER files_ai AFTER INSERT ON files BEGIN
                            INSERT INTO files_fts(rowid, name, metadata_json, summary_short, summary_long)
                            VALUES (new.id, new.name, new.metadata_json, new.summary_short, new.summary_long);
                        END;

                        CREATE TRIGGER files_ad AFTER DELETE ON files BEGIN
                            INSERT INTO files_fts(files_fts, rowid, name, metadata_json, summary_short, summary_long)
                            VALUES ('delete', old.id, old.name, old.metadata_json, old.summary_short, old.summary_long);
                        END;

                        CREATE TRIGGER files_au AFTER UPDATE ON files BEGIN
                            INSERT INTO files_fts(files_fts, rowid, name, metadata_json, summary_short, summary_long)
                            VALUES ('delete', old.id, old.name, old.metadata_json, old.summary_short, old.summary_long);
                            INSERT INTO files_fts(rowid, name, metadata_json, summary_short, summary_long)
                            VALUES (new.id, new.name, new.metadata_json, new.summary_short, new.summary_long);
                        END;
                    """)
                except Exception:
                    pass

                # Update schema version
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                    (2,),
                )

            if current_version < 3:
                # Migration v3: Change unique constraint from kor_path to hash_sha256
                # and enable multi-document .kor (merged.kor) support
                try:
                    conn.executescript("""
                        DROP TRIGGER IF EXISTS files_ai;
                        DROP TRIGGER IF EXISTS files_ad;
                        DROP TRIGGER IF EXISTS files_au;

                        CREATE TABLE files_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            kor_path TEXT NOT NULL,
                            file_path TEXT NOT NULL,
                            name TEXT NOT NULL,
                            extension TEXT,
                            size_bytes INTEGER,
                            modified_at TIMESTAMP,
                            hash_sha256 TEXT UNIQUE NOT NULL,
                            metadata_json TEXT,
                            summary_short TEXT,
                            summary_long TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );

                        INSERT INTO files_new (
                            id, kor_path, file_path, name, extension, size_bytes,
                            modified_at, hash_sha256, metadata_json, summary_short,
                            summary_long, created_at, updated_at
                        )
                        SELECT
                            id, kor_path, file_path, name, extension, size_bytes,
                            modified_at, COALESCE(hash_sha256, ''), metadata_json,
                            summary_short, summary_long, created_at, updated_at
                        FROM files;

                        DROP TABLE files;
                        ALTER TABLE files_new RENAME TO files;

                        CREATE INDEX idx_files_path ON files(file_path);

                        DROP TABLE IF EXISTS files_fts;
                        CREATE VIRTUAL TABLE files_fts USING fts5(
                            name,
                            metadata_json,
                            summary_short,
                            summary_long,
                            content='files',
                            content_rowid='id',
                            tokenize='porter unicode61'
                        );

                        INSERT INTO files_fts(rowid, name, metadata_json, summary_short, summary_long)
                        SELECT id, name, metadata_json, summary_short, summary_long FROM files;

                        CREATE TRIGGER files_ai AFTER INSERT ON files BEGIN
                            INSERT INTO files_fts(rowid, name, metadata_json, summary_short, summary_long)
                            VALUES (new.id, new.name, new.metadata_json, new.summary_short, new.summary_long);
                        END;

                        CREATE TRIGGER files_ad AFTER DELETE ON files BEGIN
                            INSERT INTO files_fts(files_fts, rowid, name, metadata_json, summary_short, summary_long)
                            VALUES ('delete', old.id, old.name, old.metadata_json, old.summary_short, old.summary_long);
                        END;

                        CREATE TRIGGER files_au AFTER UPDATE ON files BEGIN
                            INSERT INTO files_fts(files_fts, rowid, name, metadata_json, summary_short, summary_long)
                            VALUES ('delete', old.id, old.name, old.metadata_json, old.summary_short, old.summary_long);
                            INSERT INTO files_fts(rowid, name, metadata_json, summary_short, summary_long)
                            VALUES (new.id, new.name, new.metadata_json, new.summary_short, new.summary_long);
                        END;
                    """)
                except Exception:
                    pass

                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                    (3,),
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

    def sync_file(self, kor_path: str) -> List[int]:
        """Synchronize a .kor file into the database.

        Supports both single-document .kor files and multi-document
        merged.kor files. Each document is upserted individually using
        hash_sha256 as the unique key.

        Args:
            kor_path: Path to the .kor sidecar file.

        Returns:
            List of file IDs for each inserted/updated file record.

        Raises:
            FileNotFoundError: If the .kor file doesn't exist.
            ValueError: If the .kor file is invalid.
            sqlite3.Error: If database operation fails.
        """
        import yaml
        from filekor.sidecar import Sidecar

        kor_file = Path(kor_path)
        if not kor_file.exists():
            raise FileNotFoundError(f"Sidecar file not found: {kor_path}")

        # Parse the .kor file (supports multi-document merged.kor)
        content = kor_file.read_text(encoding="utf-8")

        with self._get_connection() as conn:
            try:
                conn.execute("BEGIN")

                file_ids: List[int] = []

                for data in yaml.safe_load_all(content):
                    if not data:
                        continue

                    sidecar = Sidecar.from_dict(data)

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

                    # Upsert using hash_sha256 as conflict target
                    cursor = conn.execute(
                        """
                        INSERT INTO files
                        (kor_path, file_path, name, extension, size_bytes, modified_at, hash_sha256, metadata_json, summary_short, summary_long, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(hash_sha256) DO UPDATE SET
                            kor_path = excluded.kor_path,
                            file_path = excluded.file_path,
                            name = excluded.name,
                            extension = excluded.extension,
                            size_bytes = excluded.size_bytes,
                            modified_at = excluded.modified_at,
                            metadata_json = excluded.metadata_json,
                            summary_short = excluded.summary_short,
                            summary_long = excluded.summary_long,
                            updated_at = excluded.updated_at
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
                            sidecar.summary.short if sidecar.summary else None,
                            sidecar.summary.long if sidecar.summary else None,
                            datetime.now(timezone.utc),
                        ),
                    )

                    # Always query for the file_id after upsert - lastrowid
                    # is unreliable with ON CONFLICT DO UPDATE
                    cursor = conn.execute(
                        "SELECT id FROM files WHERE hash_sha256 = ?",
                        (sidecar.file.hash_sha256,),
                    )
                    row = cursor.fetchone()
                    file_id = row["id"] if row else None

                    # Delete old labels and insert new ones
                    conn.execute("DELETE FROM labels WHERE file_id = ?", (file_id,))

                    if sidecar.labels and sidecar.labels.suggested:
                        for label in sidecar.labels.suggested:
                            conn.execute(
                                """
                                INSERT INTO labels (file_id, label, confidence, source)
                                VALUES (?, ?, ?, ?)
                                """,
                                (file_id, label, None, sidecar.labels.source),
                            )

                    file_ids.append(file_id)

                conn.commit()

                logger.debug(f"Synced file {kor_path} with IDs {file_ids}")
                return file_ids

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

    def query_labels_with_counts(self) -> List[Dict[str, Any]]:
        """Query all labels with their file counts.

        Returns:
            List of dicts with 'label' and 'file_count' keys,
            ordered by file count descending.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT l.label, COUNT(DISTINCT l.file_id) as file_count
                FROM labels l
                GROUP BY l.label
                ORDER BY file_count DESC, l.label ASC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

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

    def get_file_by_hash(self, hash_sha256: str) -> Optional[Dict[str, Any]]:
        """Get file metadata from database by SHA256 hash.

        Args:
            hash_sha256: The SHA256 hash of the file.

        Returns:
            Dictionary with file metadata or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM files WHERE hash_sha256 = ?", (hash_sha256,)
            )
            row = cursor.fetchone()
            if row:
                row_dict = dict(row)
                # Get labels for this file
                labels_cursor = conn.execute(
                    "SELECT label FROM labels WHERE file_id = ?", (row["id"],)
                )
                labels = [r["label"] for r in labels_cursor.fetchall()]
                row_dict["labels"] = labels
                return row_dict
            return None

    def delete_file_by_hash(self, hash_sha256: str) -> int:
        """Delete file from database by SHA256 hash.

        Args:
            hash_sha256: The SHA256 hash of the file to delete.

        Returns:
            Number of records deleted.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM files WHERE hash_sha256 = ?", (hash_sha256,)
            )
            conn.commit()
            return cursor.rowcount

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

    def query_by_labels(self, labels: List[str]) -> List[Dict[str, Any]]:
        """Query files that have ANY of the specified labels (OR logic).

        Args:
            labels: List of labels to search for.

        Returns:
            List of dictionaries containing file info and labels.
        """
        if not labels:
            return self.query_all()

        with self._get_connection() as conn:
            # Build placeholder for IN clause
            placeholders = ",".join("?" * len(labels))
            cursor = conn.execute(
                f"""
                SELECT f.*, GROUP_CONCAT(DISTINCT l.label, ',') as labels
                FROM files f
                JOIN labels l ON f.id = l.file_id
                WHERE l.label IN ({placeholders})
                GROUP BY f.id
                ORDER BY f.file_path
                """,
                tuple(labels),
            )

            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                labels_str = row_dict.pop("labels", None)
                row_dict["labels"] = labels_str.split(",") if labels_str else []
                results.append(row_dict)

            return results

    def search_content(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Full-text search in filename and metadata.

        Uses FTS5 for fast full-text search across filename and .kor content.

        Args:
            query: Search query text.
            limit: Maximum number of results to return.

        Returns:
            List of dictionaries with file info, labels, and relevance score.
        """
        with self._get_connection() as conn:
            # First check if FTS5 table exists and has data
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='files_fts'"
            )
            if not cursor.fetchone():
                # FTS5 not available, fall back to LIKE search
                return self._search_content_fallback(query, limit)

            # FTS5 search with ranking
            cursor = conn.execute(
                """
                SELECT f.*, GROUP_CONCAT(DISTINCT l.label, ',') as labels,
                       rank as fts_rank
                FROM files_fts
                JOIN files f ON files_fts.rowid = f.id
                LEFT JOIN labels l ON f.id = l.file_id
                WHERE files_fts MATCH ?
                GROUP BY f.id
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )

            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                labels_str = row_dict.pop("labels", None)
                row_dict["labels"] = labels_str.split(",") if labels_str else []
                row_dict["fts_rank"] = row_dict.pop("fts_rank", 0.0)
                results.append(row_dict)

            return results

    def _search_content_fallback(
        self, query: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fallback search using LIKE when FTS5 is not available.

        Args:
            query: Search query text.
            limit: Maximum number of results to return.

        Returns:
            List of dictionaries with file info and labels.
        """
        search_pattern = f"%{query}%"
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT f.*, GROUP_CONCAT(DISTINCT l.label, ',') as labels
                FROM files f
                LEFT JOIN labels l ON f.id = l.file_id
                WHERE f.name LIKE ? OR f.metadata_json LIKE ?
                GROUP BY f.id
                ORDER BY f.file_path
                LIMIT ?
                """,
                (search_pattern, search_pattern, limit),
            )

            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                labels_str = row_dict.pop("labels", None)
                row_dict["labels"] = labels_str.split(",") if labels_str else []
                row_dict["fts_rank"] = 0.0  # No ranking available
                results.append(row_dict)

            return results

    def search_files(
        self,
        labels: Optional[List[str]] = None,
        query: Optional[str] = None,
        limit: int = 50,
        weights: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Combined search by labels and/or content.

        Args:
            labels: Labels to filter by (OR logic).
            query: Search query text.
            limit: Maximum number of results to return.
            weights: Scoring weights for different match types.
                Defaults: {"label_match": 0.50, "filename_match": 0.30,
                          "kor_content_match": 0.20}

        Returns:
            List of dictionaries with file info, labels, and calculated score.
        """
        # Default weights
        default_weights = {
            "label_match": 0.50,
            "filename_match": 0.30,
            "kor_content_match": 0.20,
        }
        weights = weights or default_weights

        # Get candidates based on labels
        if labels:
            label_results = self.query_by_labels(labels)
            label_files = {r["id"]: r for r in label_results}
        else:
            label_files = {}

        # Get candidates based on content search
        if query:
            content_results = self.search_content(query, limit=limit * 2)
            content_files = {r["id"]: r for r in content_results}
        else:
            content_files = {}

        # Combine results
        all_ids = set(label_files.keys()) | set(content_files.keys())

        if not all_ids:
            return []

        # Calculate scores for each file
        results = []
        query_lower = query.lower() if query else ""

        for file_id in all_ids:
            file_data = content_files.get(file_id, label_files.get(file_id, {}))
            if not file_data:
                continue

            score = 0.0
            score_breakdown = {}

            # Label match score
            if labels and file_id in label_files:
                file_labels = set(file_data.get("labels", []))
                matched_labels = file_labels & set(labels)
                label_score = len(matched_labels) / max(len(labels), 1)
                score += label_score * weights.get("label_match", 0.50)
                score_breakdown["label_match"] = label_score

            # Filename match score
            if query:
                filename = file_data.get("name", "").lower()
                if query_lower in filename:
                    filename_score = 1.0
                else:
                    # Check individual words
                    query_words = query_lower.split()
                    matches = sum(1 for word in query_words if word in filename)
                    filename_score = matches / max(len(query_words), 1)
                score += filename_score * weights.get("filename_match", 0.30)
                score_breakdown["filename_match"] = filename_score

            # Content match score (from FTS rank or fallback)
            if query and file_id in content_files:
                content_score = 1.0 - min(
                    abs(content_files[file_id].get("fts_rank", 0)), 1.0
                )
                score += content_score * weights.get("kor_content_match", 0.20)
                score_breakdown["kor_content_match"] = content_score

            file_data["score"] = round(score, 4)
            file_data["score_breakdown"] = score_breakdown
            results.append(file_data)

        # Sort by score descending
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return results[:limit]


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


def sync_file(kor_path: str, db: Optional[Database] = None) -> List[int]:
    """Convenience function to sync a .kor file to the database.

    Args:
        kor_path: Path to the .kor sidecar file.
        db: Optional Database instance (uses singleton if not provided).

    Returns:
        List of file IDs for each inserted/updated file record.

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


def query_labels_with_counts(
    db: Optional[Database] = None,
) -> List[Dict[str, Any]]:
    """Convenience function to query labels with file counts.

    Args:
        db: Optional Database instance (uses singleton if not provided).

    Returns:
        List of dicts with 'label' and 'file_count' keys.
    """
    if db is None:
        db = get_db()
    return db.query_labels_with_counts()


def query_by_labels(
    labels: List[str], db: Optional[Database] = None
) -> List[Dict[str, Any]]:
    """Convenience function to query files by multiple labels (OR logic).

    Args:
        labels: List of labels to search for.
        db: Optional Database instance (uses singleton if not provided).

    Returns:
        List of dictionaries containing file info and labels.

    Example:
        >>> from filekor.db import query_by_labels
        >>> files = query_by_labels(["finance", "2026"])
        >>> print(files[0]["file_path"])
        '/path/to/report.pdf'
    """
    if db is None:
        db = get_db()
    return db.query_by_labels(labels)


def search_content(
    query: str, limit: int = 50, db: Optional[Database] = None
) -> List[Dict[str, Any]]:
    """Convenience function for full-text search.

    Args:
        query: Search query text.
        limit: Maximum number of results to return.
        db: Optional Database instance (uses singleton if not provided).

    Returns:
        List of dictionaries with file info, labels, and relevance rank.

    Example:
        >>> from filekor.db import search_content
        >>> results = search_content("budget report")
        >>> print(results[0]["name"])
        'budget-report.pdf'
    """
    if db is None:
        db = get_db()
    return db.search_content(query, limit)


def search_files(
    labels: Optional[List[str]] = None,
    query: Optional[str] = None,
    limit: int = 50,
    weights: Optional[Dict[str, float]] = None,
    db: Optional[Database] = None,
) -> List[Dict[str, Any]]:
    """Convenience function for combined search by labels and/or content.

    Args:
        labels: Labels to filter by (OR logic).
        query: Search query text.
        limit: Maximum number of results to return.
        weights: Scoring weights for different match types.
        db: Optional Database instance (uses singleton if not provided).

    Returns:
        List of dictionaries with file info, labels, and calculated score.

    Example:
        >>> from filekor.db import search_files
        >>> results = search_files(
        ...     labels=["finance", "2026"],
        ...     query="provider costs"
        ... )
        >>> print(f"{results[0]['name']}: {results[0]['score']}")
        'report.pdf: 0.85'
    """
    if db is None:
        db = get_db()
    return db.search_files(labels, query, limit, weights)


def close_db(db: Optional[Database] = None) -> None:
    """Convenience function to close the database.

    Args:
        db: Optional Database instance (uses singleton if not provided).
    """
    if db is None:
        db = get_db()
    db.close()


def get_file_by_hash(
    hash_sha256: str, db: Optional[Database] = None
) -> Optional[Dict[str, Any]]:
    """Get file metadata from database by SHA256 hash.

    Args:
        hash_sha256: The SHA256 hash of the file.
        db: Optional Database instance (uses singleton if not provided).

    Returns:
        Dictionary with file metadata or None if not found.
    """
    if db is None:
        db = get_db()
    return db.get_file_by_hash(hash_sha256)


def get_all_files(db: Optional[Database] = None) -> List[Dict[str, Any]]:
    """Get all files from database.

    Args:
        db: Optional Database instance (uses singleton if not provided).

    Returns:
        List of dictionaries with file info and labels.
    """
    if db is None:
        db = get_db()
    return db.query_all()


def delete_file_by_hash(hash_sha256: str, db: Optional[Database] = None) -> int:
    """Delete file from database by SHA256 hash.

    Args:
        hash_sha256: The SHA256 hash of the file to delete.
        db: Optional Database instance (uses singleton if not provided).

    Returns:
        Number of records deleted.
    """
    if db is None:
        db = get_db()
    return db.delete_file_by_hash(hash_sha256)
