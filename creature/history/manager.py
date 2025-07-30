"""
History manager for Creature Browser.
Provides high-level history operations with profile isolation and automatic cleanup.
"""

import logging
import threading
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from .database import HistoryDatabase

logger = logging.getLogger(__name__)


class HistoryManager(QObject):
    """Profile-specific history management with automatic cleanup."""

    # Signals for UI updates
    historyUpdated = pyqtSignal()  # Emitted when history changes
    cleanupCompleted = pyqtSignal(int)  # Emitted after cleanup (entries removed)

    def __init__(self, profile_name: str, profile_base_dir: Path = None):
        """Initialize history manager for a profile.
        
        Args:
            profile_name: Name of the profile
            profile_base_dir: Base directory for profiles (defaults to ~/.config/creature)
        """
        super().__init__()

        self.profile_name = profile_name
        self._lock = threading.RLock()

        if profile_base_dir is None:
            self.profile_base_dir = Path.home() / ".config" / "creature"
        else:
            self.profile_base_dir = Path(profile_base_dir)

        # History database path
        profile_dir = self.profile_base_dir / f"profile_{profile_name}"
        profile_dir.mkdir(parents=True, exist_ok=True)
        db_path = profile_dir / "history.db"

        self.database = HistoryDatabase(db_path)

        # Default configuration (will be overridden by config manager)
        self.config = {
            'enabled': True,
            'retention_days': 30,
            'max_entries': 10000,
            'autocomplete_max_results': 10,
            'cleanup_interval_minutes': 60,
            'ordering': 'visits'
        }

        # Setup automatic cleanup timer
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._periodic_cleanup)
        self._start_cleanup_timer()

        logger.debug(f"HistoryManager initialized for profile '{profile_name}' at {db_path}")

    def update_config(self, config: dict):
        """Update configuration settings.
        
        Args:
            config: Dictionary with configuration values
        """
        with self._lock:
            self.config.update(config)

            # Restart cleanup timer if interval changed
            if 'cleanup_interval_minutes' in config:
                self._start_cleanup_timer()

            logger.debug(f"History config updated: {self.config}")

    def _start_cleanup_timer(self):
        """Start or restart the periodic cleanup timer."""
        if self._cleanup_timer.isActive():
            self._cleanup_timer.stop()

        if self.config['enabled']:
            interval_ms = self.config['cleanup_interval_minutes'] * 60 * 1000
            self._cleanup_timer.start(interval_ms)
            logger.debug(f"Started cleanup timer with {self.config['cleanup_interval_minutes']} minute interval")

    def record_visit(self, url: str, title: str = None, session_data: dict = None) -> bool:
        """Record a page visit in history.
        
        Args:
            url: The visited URL
            title: Page title (optional)
            session_data: Session storage data (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.config['enabled']:
            return False

        if not url or url.startswith('about:') or url.startswith('data:'):
            return False  # Skip internal URLs

        try:
            with self._lock:
                success = self.database.add_or_update_entry(url, title, session_data)
                if success:
                    self.historyUpdated.emit()
                    logger.debug(f"Recorded visit: {url[:50]}{'...' if len(url) > 50 else ''}")
                return success

        except Exception as e:
            logger.error(f"Failed to record visit for {url}: {e}")
            return False

    def search_history(self, query: str) -> list[dict]:
        """Search history for autocomplete suggestions.
        
        Args:
            query: Search query (prefix matching)
            
        Returns:
            List of matching entries for autocomplete
        """
        if not self.config['enabled'] or not query:
            return []

        try:
            with self._lock:
                max_results = self.config['autocomplete_max_results']
                ordering = self.config['ordering']
                results = self.database.search_entries(query, max_results, ordering)

                # Format results for autocomplete
                formatted_results = []
                for entry in results:
                    formatted_results.append({
                        'text': entry['url'],
                        'display': f"{entry['title']} - {entry['url']}",
                        'url': entry['url'],
                        'title': entry['title'],
                        'visit_count': entry['visit_count'],
                        'last_visited': entry['last_visited']
                    })

                return formatted_results

        except Exception as e:
            logger.error(f"Failed to search history for '{query}': {e}")
            return []

    def get_recent_visits(self, limit: int = 20) -> list[dict]:
        """Get recently visited pages.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of recent visits
        """
        if not self.config['enabled']:
            return []

        try:
            with self._lock:
                return self.database.get_recent_entries(limit)

        except Exception as e:
            logger.error(f"Failed to get recent visits: {e}")
            return []

    def cleanup_history(self, force: bool = False) -> int:
        """Clean up old history entries.
        
        Args:
            force: Force cleanup even if not enabled
            
        Returns:
            Number of entries removed
        """
        if not self.config['enabled'] and not force:
            return 0

        try:
            with self._lock:
                removed_count = 0

                # Clean up by age
                if self.config['retention_days'] > 0:
                    removed_count += self.database.cleanup_old_entries(self.config['retention_days'])

                # Limit total entries
                if self.config['max_entries'] > 0:
                    removed_count += self.database.limit_entries(self.config['max_entries'])

                if removed_count > 0:
                    self.historyUpdated.emit()
                    self.cleanupCompleted.emit(removed_count)
                    logger.info(f"History cleanup completed: {removed_count} entries removed")

                return removed_count

        except Exception as e:
            logger.error(f"Failed to cleanup history: {e}")
            return 0

    def _periodic_cleanup(self):
        """Periodic cleanup triggered by timer."""
        logger.debug("Running periodic history cleanup")
        self.cleanup_history()

    def clear_all_history(self) -> bool:
        """Clear all history entries.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self._lock:
                success = self.database.clear_all()
                if success:
                    self.historyUpdated.emit()
                    logger.info("Cleared all history entries")
                return success

        except Exception as e:
            logger.error(f"Failed to clear all history: {e}")
            return False

    def get_statistics(self) -> dict:
        """Get history statistics.
        
        Returns:
            Dictionary with history statistics
        """
        try:
            with self._lock:
                stats = self.database.get_stats()
                stats['profile_name'] = self.profile_name
                stats['enabled'] = self.config['enabled']
                return stats

        except Exception as e:
            logger.error(f"Failed to get history statistics: {e}")
            return {
                'profile_name': self.profile_name,
                'enabled': self.config['enabled'],
                'total_entries': 0,
                'unique_hosts': 0,
                'oldest_entry': 0,
                'newest_entry': 0,
                'database_size': 0
            }

    def is_enabled(self) -> bool:
        """Check if history is enabled.
        
        Returns:
            True if history is enabled
        """
        return self.config['enabled']

    def set_enabled(self, enabled: bool):
        """Enable or disable history recording.
        
        Args:
            enabled: Whether to enable history recording
        """
        with self._lock:
            self.config['enabled'] = enabled

            if enabled:
                self._start_cleanup_timer()
            else:
                if self._cleanup_timer.isActive():
                    self._cleanup_timer.stop()

            logger.info(f"History {'enabled' if enabled else 'disabled'} for profile '{self.profile_name}'")

    def shutdown(self):
        """Clean shutdown of history manager."""
        try:
            if self._cleanup_timer.isActive():
                self._cleanup_timer.stop()

            # Final cleanup if enabled
            if self.config['enabled']:
                self.cleanup_history(force=True)

            logger.debug(f"HistoryManager shutdown for profile '{self.profile_name}'")

        except Exception as e:
            logger.error(f"Error during history manager shutdown: {e}")

    def __del__(self):
        """Ensure cleanup on deletion."""
        try:
            self.shutdown()
        except Exception:
            pass  # Ignore errors during deletion
