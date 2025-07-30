"""
SQLite database operations for browser history.
Handles schema creation, indexing, and core queries.
"""

import sqlite3
import logging
import json
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import urlparse
import time

logger = logging.getLogger(__name__)


class HistoryDatabase:
    """SQLite database for browser history with optimized search."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Path):
        """Initialize history database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _initialize_database(self):
        """Create database schema and indexes if needed."""
        with self._get_connection() as conn:
            # Check if database needs initialization
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='history_entries'")
            if not cursor.fetchone():
                self._create_schema(conn)
                logger.info(f"Created history database: {self.db_path}")

            # Ensure indexes exist (idempotent)
            self._create_indexes(conn)

    def _create_schema(self, conn: sqlite3.Connection):
        """Create database tables."""
        conn.execute("""
            CREATE TABLE history_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT,
                visit_count INTEGER DEFAULT 1,
                last_visited INTEGER NOT NULL,
                first_visited INTEGER NOT NULL,
                session_data TEXT,
                host TEXT NOT NULL,
                UNIQUE(url) ON CONFLICT REPLACE
            )
        """)

        conn.execute("""
            CREATE TABLE schema_info (
                version INTEGER NOT NULL
            )
        """)

        conn.execute("INSERT INTO schema_info (version) VALUES (?)", (self.SCHEMA_VERSION,))
        conn.commit()

    def _create_indexes(self, conn: sqlite3.Connection):
        """Create database indexes for fast searching."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_url_prefix ON history_entries(url)",
            "CREATE INDEX IF NOT EXISTS idx_title_prefix ON history_entries(title)",
            "CREATE INDEX IF NOT EXISTS idx_last_visited ON history_entries(last_visited)",
            "CREATE INDEX IF NOT EXISTS idx_host ON history_entries(host)",
            "CREATE INDEX IF NOT EXISTS idx_visit_count ON history_entries(visit_count)",
        ]

        for index_sql in indexes:
            conn.execute(index_sql)

        conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def add_or_update_entry(self, url: str, title: str = None, session_data: dict = None) -> bool:
        """Add new history entry or update existing one.

        Args:
            url: The visited URL
            title: Page title (optional)
            session_data: Session storage data (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            host = urlparse(url).netloc or url
            current_time = int(time.time())
            session_json = json.dumps(session_data) if session_data else None

            with self._get_connection() as conn:
                # Check if entry exists
                cursor = conn.execute("SELECT id, visit_count, first_visited FROM history_entries WHERE url = ?", (url,))
                existing_row = cursor.fetchone()

                if existing_row:
                    # Update existing entry
                    new_visit_count = existing_row["visit_count"] + 1
                    conn.execute(
                        """
                        UPDATE history_entries
                        SET title = COALESCE(?, title),
                            visit_count = ?,
                            last_visited = ?,
                            session_data = COALESCE(?, session_data),
                            host = ?
                        WHERE url = ?
                    """,
                        (title, new_visit_count, current_time, session_json, host, url),
                    )
                else:
                    # Insert new entry
                    conn.execute(
                        """
                        INSERT INTO history_entries
                        (url, title, visit_count, last_visited, first_visited, session_data, host)
                        VALUES (?, ?, 1, ?, ?, ?, ?)
                    """,
                        (url, title, current_time, current_time, session_json, host),
                    )

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to add/update history entry: {e}")
            return False

    def search_entries(self, query: str, limit: int = 10, ordering: str = "visits") -> list[dict]:
        """Search history entries by URL or title.

        Args:
            query: Search query (prefix matching)
            limit: Maximum number of results
            ordering: Sort order - 'visits' for visit count, 'recent' for last visited

        Returns:
            List of matching entries ordered by preference
        """
        if not query:
            return []

        try:
            with self._get_connection() as conn:
                # Choose ordering based on preference
                if ordering == "recent":
                    order_clause = "ORDER BY last_visited DESC, visit_count DESC"
                else:  # Default to 'visits'
                    order_clause = "ORDER BY visit_count DESC, last_visited DESC"

                # Search with substring matching and configurable ordering
                cursor = conn.execute(
                    f"""
                    SELECT url, title, visit_count, last_visited, host
                    FROM history_entries
                    WHERE url LIKE ? OR title LIKE ?
                    {order_clause}
                    LIMIT ?
                """,
                    (f"%{query}%", f"%{query}%", limit),
                )

                results = []
                for row in cursor:
                    results.append({"url": row["url"], "title": row["title"] or row["url"], "visit_count": row["visit_count"], "last_visited": row["last_visited"], "host": row["host"]})

                return results

        except Exception as e:
            logger.error(f"Failed to search history entries: {e}")
            return []

    def get_recent_entries(self, limit: int = 20) -> list[dict]:
        """Get most recently visited entries.

        Args:
            limit: Maximum number of results

        Returns:
            List of recent entries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT url, title, visit_count, last_visited, host
                    FROM history_entries
                    ORDER BY last_visited DESC
                    LIMIT ?
                """,
                    (limit,),
                )

                results = []
                for row in cursor:
                    results.append({"url": row["url"], "title": row["title"] or row["url"], "visit_count": row["visit_count"], "last_visited": row["last_visited"], "host": row["host"]})

                return results

        except Exception as e:
            logger.error(f"Failed to get recent entries: {e}")
            return []

    def cleanup_old_entries(self, retention_days: int) -> int:
        """Remove entries older than specified days.

        Args:
            retention_days: Number of days to retain history

        Returns:
            Number of entries removed
        """
        try:
            cutoff_time = int(time.time()) - (retention_days * 24 * 60 * 60)

            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM history_entries WHERE last_visited < ?", (cutoff_time,))
                count_before = cursor.fetchone()[0]

                conn.execute("DELETE FROM history_entries WHERE last_visited < ?", (cutoff_time,))

                cursor = conn.execute("SELECT COUNT(*) FROM history_entries WHERE last_visited < ?", (cutoff_time,))
                count_after = cursor.fetchone()[0]

                # Optimize database after cleanup
                conn.execute("VACUUM")
                conn.commit()

                removed_count = count_before - count_after
                if removed_count > 0:
                    logger.info(f"Cleaned up {removed_count} old history entries")

                return removed_count

        except Exception as e:
            logger.error(f"Failed to cleanup old entries: {e}")
            return 0

    def limit_entries(self, max_entries: int) -> int:
        """Limit total number of entries, removing oldest first.

        Args:
            max_entries: Maximum number of entries to keep

        Returns:
            Number of entries removed
        """
        try:
            with self._get_connection() as conn:
                # Count current entries
                cursor = conn.execute("SELECT COUNT(*) FROM history_entries")
                current_count = cursor.fetchone()[0]

                if current_count <= max_entries:
                    return 0

                # Remove oldest entries beyond limit
                entries_to_remove = current_count - max_entries
                conn.execute(
                    """
                    DELETE FROM history_entries
                    WHERE id IN (
                        SELECT id FROM history_entries
                        ORDER BY last_visited ASC
                        LIMIT ?
                    )
                """,
                    (entries_to_remove,),
                )

                # Optimize database
                conn.execute("VACUUM")
                conn.commit()

                logger.info(f"Limited history to {max_entries} entries, removed {entries_to_remove}")
                return entries_to_remove

        except Exception as e:
            logger.error(f"Failed to limit entries: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get database statistics.

        Returns:
            Dictionary with database stats
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM history_entries")
                total_entries = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(DISTINCT host) FROM history_entries")
                unique_hosts = cursor.fetchone()[0]

                cursor = conn.execute("SELECT MIN(first_visited), MAX(last_visited) FROM history_entries")
                row = cursor.fetchone()
                oldest_entry = row[0] if row[0] else 0
                newest_entry = row[1] if row[1] else 0

                return {"total_entries": total_entries, "unique_hosts": unique_hosts, "oldest_entry": oldest_entry, "newest_entry": newest_entry, "database_size": self.db_path.stat().st_size if self.db_path.exists() else 0}

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {"total_entries": 0, "unique_hosts": 0, "oldest_entry": 0, "newest_entry": 0, "database_size": 0}

    def clear_all(self) -> bool:
        """Clear all history entries.

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM history_entries")
                conn.execute("VACUUM")
                conn.commit()

                logger.info("Cleared all history entries")
                return True

        except Exception as e:
            logger.error(f"Failed to clear all entries: {e}")
            return False
