"""
History editor UI for Creature Browser.
Provides interface for viewing, searching, and managing browsing history.
"""

import logging
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QListWidget, QListWidgetItem, QLabel, QMessageBox, QMenu, QAbstractItemView, QSplitter, QTextEdit, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QAction

logger = logging.getLogger(__name__)


class HistorySearchWorker(QThread):
    """Background worker for history search to avoid blocking UI."""

    searchCompleted = pyqtSignal(list)  # Emits list of results

    def __init__(self, history_manager, query: str = ""):
        super().__init__()
        self.history_manager = history_manager
        self.query = query
        self._cancelled = False

    def run(self):
        """Run search in background thread."""
        if self._cancelled or not self.history_manager:
            return

        try:
            if self.query:
                # Search for specific query
                results = self.history_manager.database.search_entries(self.query, limit=1000, ordering="recent")
            else:
                # Get all recent entries
                results = self.history_manager.database.get_recent_entries(1000)

            if not self._cancelled:
                self.searchCompleted.emit(results)
        except Exception as e:
            logger.error(f"Error in history search worker: {e}")

    def cancel(self):
        """Cancel the current search."""
        self._cancelled = True


class HistoryListItem(QListWidgetItem):
    """Custom list item for history entries with additional data."""

    def __init__(self, entry_data: dict):
        self.entry_data = entry_data

        # Format display text
        title = entry_data.get("title", "Untitled")
        url = entry_data.get("url", "")
        visit_count = entry_data.get("visit_count", 1)
        last_visited = entry_data.get("last_visited", 0)

        # Format timestamp
        if last_visited:
            try:
                timestamp = datetime.fromtimestamp(last_visited).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                timestamp = "Unknown date"
        else:
            timestamp = "Unknown date"

        # Create display text
        display_text = f"{title}\n{url}\nVisited {visit_count} times • Last: {timestamp}"

        super().__init__(display_text)

        # Store data for easy access
        self.setData(Qt.ItemDataRole.UserRole, entry_data)


class HistoryEditorWidget(QWidget):
    """History editor widget with search and management capabilities."""

    # Signal emitted when user wants to navigate to a URL
    navigationRequested = pyqtSignal(str)

    def __init__(self, history_manager, parent=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self._search_worker = None
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._perform_search)

        self._setup_ui()
        self._apply_theme_styling()
        self._load_initial_data()

        logger.debug("HistoryEditorWidget initialized")

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_label = QLabel("Browsing History")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Controls section
        controls_layout = QHBoxLayout()

        # Clear all button
        self.clear_all_btn = QPushButton("Clear All History")
        self.clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.clear_all_btn.clicked.connect(self._clear_all_history)
        controls_layout.addWidget(self.clear_all_btn)

        # Spacer
        controls_layout.addStretch()

        # Statistics
        self.stats_label = QLabel("Loading...")
        controls_layout.addWidget(self.stats_label)

        layout.addLayout(controls_layout)

        # Search field
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_layout.addWidget(search_label)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search history by URL or title...")
        self.search_field.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.search_field)

        self.clear_search_btn = QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self._clear_search)
        search_layout.addWidget(self.clear_search_btn)

        layout.addLayout(search_layout)

        # Main content area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # History list
        list_frame = QFrame()
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(0, 0, 0, 0)

        list_label = QLabel("History Entries:")
        list_layout.addWidget(list_label)

        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.history_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._show_context_menu)
        list_layout.addWidget(self.history_list)

        # List controls
        list_controls = QHBoxLayout()
        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.clicked.connect(self._delete_selected_entries)
        list_controls.addWidget(self.delete_selected_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_data)
        list_controls.addWidget(self.refresh_btn)

        list_controls.addStretch()
        list_layout.addLayout(list_controls)

        splitter.addWidget(list_frame)

        # Details panel
        details_frame = QFrame()
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(10, 0, 0, 0)

        details_label = QLabel("Entry Details:")
        details_layout.addWidget(details_label)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumWidth(300)
        details_layout.addWidget(self.details_text)

        splitter.addWidget(details_frame)
        splitter.setSizes([700, 300])  # 70% list, 30% details

        layout.addWidget(splitter)

        # Connect selection change to update details
        self.history_list.itemSelectionChanged.connect(self._update_details)

    def _apply_theme_styling(self):
        """Apply theme-aware styling."""
        try:
            # Get theme colors from parent browser
            parent_browser = self.parent()
            while parent_browser and not hasattr(parent_browser, "theme_manager"):
                parent_browser = parent_browser.parent()

            if parent_browser and hasattr(parent_browser, "theme_manager"):
                current_theme = getattr(parent_browser, "current_theme", "light")
                theme = parent_browser.theme_manager.themes.get(current_theme, {})
                colors = theme.get("colors", {}) if theme else {}
            else:
                colors = {}

            # Apply styling to search field and list
            widget_style = f"""
                QLineEdit {{
                    padding: 6px 10px;
                    border: 1px solid {colors.get("border_color", "#ccc")};
                    border-radius: 4px;
                    background-color: {colors.get("input_bg", "#ffffff")};
                    color: {colors.get("text_color", "#000000")};
                }}
                QListWidget {{
                    border: 1px solid {colors.get("border_color", "#ccc")};
                    background-color: {colors.get("list_bg", "#ffffff")};
                    color: {colors.get("text_color", "#000000")};
                    alternate-background-color: {colors.get("list_alt_bg", "#f8f9fa")};
                }}
                QListWidget::item {{
                    padding: 8px;
                    border-bottom: 1px solid {colors.get("border_color", "#eee")};
                }}
                QListWidget::item:selected {{
                    background-color: {colors.get("accent", "#0078d4")};
                    color: white;
                }}
                QTextEdit {{
                    border: 1px solid {colors.get("border_color", "#ccc")};
                    background-color: {colors.get("input_bg", "#ffffff")};
                    color: {colors.get("text_color", "#000000")};
                }}
            """

            self.search_field.setStyleSheet(widget_style)
            self.history_list.setStyleSheet(widget_style)
            self.details_text.setStyleSheet(widget_style)

        except Exception as e:
            logger.debug(f"Failed to apply theme styling: {e}")

    def _load_initial_data(self):
        """Load initial history data."""
        self._perform_search()
        self._update_statistics()

    def _on_search_text_changed(self, text: str):
        """Handle search text changes with debouncing."""
        # Cancel any existing search
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.cancel()
            self._search_worker.wait(100)

        # Start debounced search
        self._search_timer.start(300)  # 300ms debounce

    def _clear_search(self):
        """Clear the search field."""
        self.search_field.clear()

    def _perform_search(self):
        """Perform the actual search in background thread."""
        if not self.history_manager:
            return

        query = self.search_field.text().strip()

        # Start background search
        self._search_worker = HistorySearchWorker(self.history_manager, query)
        self._search_worker.searchCompleted.connect(self._on_search_completed)
        self._search_worker.start()

    @pyqtSlot(list)
    def _on_search_completed(self, results: list):
        """Handle search completion and update the list."""
        try:
            self.history_list.clear()

            for entry in results:
                item = HistoryListItem(entry)
                self.history_list.addItem(item)

            # Update count
            result_count = len(results)
            if self.search_field.text().strip():
                self.stats_label.setText(f"Found {result_count} matching entries")
            else:
                self._update_statistics()

        except Exception as e:
            logger.error(f"Error updating history list: {e}")

    def _update_statistics(self):
        """Update the statistics display."""
        try:
            if not self.history_manager:
                return

            stats = self.history_manager.get_statistics()
            total_entries = stats.get("total_entries", 0)
            unique_hosts = stats.get("unique_hosts", 0)

            self.stats_label.setText(f"{total_entries} entries from {unique_hosts} sites")

        except Exception as e:
            logger.error(f"Error updating statistics: {e}")

    def _update_details(self):
        """Update the details panel with selected entry information."""
        try:
            selected_items = self.history_list.selectedItems()
            if not selected_items:
                self.details_text.clear()
                return

            if len(selected_items) == 1:
                # Single item selected
                item = selected_items[0]
                entry = item.data(Qt.ItemDataRole.UserRole)

                title = entry.get("title", "Untitled")
                url = entry.get("url", "")
                visit_count = entry.get("visit_count", 1)
                last_visited = entry.get("last_visited", 0)
                host = entry.get("host", "")

                # Format timestamps
                if last_visited:
                    try:
                        last_date = datetime.fromtimestamp(last_visited).strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, OSError):
                        last_date = "Unknown"
                else:
                    last_date = "Unknown"

                details_html = f"""
                <h3>Entry Details</h3>
                <p><strong>Title:</strong><br/>{title}</p>
                <p><strong>URL:</strong><br/><a href="{url}">{url}</a></p>
                <p><strong>Host:</strong> {host}</p>
                <p><strong>Visit Count:</strong> {visit_count}</p>
                <p><strong>Last Visited:</strong><br/>{last_date}</p>
                """

                self.details_text.setHtml(details_html)
            else:
                # Multiple items selected
                count = len(selected_items)
                self.details_text.setHtml(f"<h3>Multiple Selection</h3><p>{count} entries selected</p>")

        except Exception as e:
            logger.error(f"Error updating details: {e}")

    def _on_item_double_clicked(self, item: HistoryListItem):
        """Handle double-click on history item."""
        try:
            entry = item.data(Qt.ItemDataRole.UserRole)
            url = entry.get("url", "")
            if url:
                self.navigationRequested.emit(url)
        except Exception as e:
            logger.error(f"Error handling item double-click: {e}")

    def _show_context_menu(self, position):
        """Show context menu for history items."""
        try:
            item = self.history_list.itemAt(position)
            if not item:
                return

            menu = QMenu(self)

            # Navigate to URL
            navigate_action = QAction("Open URL", self)
            navigate_action.triggered.connect(lambda: self._navigate_to_item(item))
            menu.addAction(navigate_action)

            menu.addSeparator()

            # Delete entry
            delete_action = QAction("Delete Entry", self)
            delete_action.triggered.connect(lambda: self._delete_item(item))
            menu.addAction(delete_action)

            # Show menu
            menu.exec(self.history_list.mapToGlobal(position))

        except Exception as e:
            logger.error(f"Error showing context menu: {e}")

    def _navigate_to_item(self, item: HistoryListItem):
        """Navigate to the URL of the given item."""
        try:
            entry = item.data(Qt.ItemDataRole.UserRole)
            url = entry.get("url", "")
            if url:
                self.navigationRequested.emit(url)
        except Exception as e:
            logger.error(f"Error navigating to item: {e}")

    def _delete_item(self, item: HistoryListItem):
        """Delete a single history item."""
        try:
            entry = item.data(Qt.ItemDataRole.UserRole)
            url = entry.get("url", "")

            if url and self.history_manager:
                # Delete from database
                with self.history_manager.database._get_connection() as conn:
                    conn.execute("DELETE FROM history_entries WHERE url = ?", (url,))
                    conn.commit()

                # Remove from list
                row = self.history_list.row(item)
                self.history_list.takeItem(row)

                # Update statistics
                self._update_statistics()

                logger.info(f"Deleted history entry: {url}")

        except Exception as e:
            logger.error(f"Error deleting history item: {e}")

    def _delete_selected_entries(self):
        """Delete all selected history entries."""
        try:
            selected_items = self.history_list.selectedItems()
            if not selected_items:
                return

            count = len(selected_items)
            reply = QMessageBox.question(self, "Delete Entries", f"Are you sure you want to delete {count} selected history entries?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                urls_to_delete = []
                for item in selected_items:
                    entry = item.data(Qt.ItemDataRole.UserRole)
                    url = entry.get("url", "")
                    if url:
                        urls_to_delete.append(url)

                # Delete from database
                if urls_to_delete and self.history_manager:
                    with self.history_manager.database._get_connection() as conn:
                        for url in urls_to_delete:
                            conn.execute("DELETE FROM history_entries WHERE url = ?", (url,))
                        conn.commit()

                    # Remove from UI
                    for item in selected_items:
                        row = self.history_list.row(item)
                        self.history_list.takeItem(row)

                    # Update statistics
                    self._update_statistics()

                    logger.info(f"Deleted {len(urls_to_delete)} history entries")

        except Exception as e:
            logger.error(f"Error deleting selected entries: {e}")

    def _clear_all_history(self):
        """Clear all history entries."""
        try:
            reply = QMessageBox.question(
                self, "Clear All History", "Are you sure you want to clear ALL browsing history?\n\nThis action cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                if self.history_manager:
                    success = self.history_manager.clear_all_history()
                    if success:
                        # Clear the list
                        self.history_list.clear()
                        self.details_text.clear()
                        self._update_statistics()

                        QMessageBox.information(self, "History Cleared", "All browsing history has been cleared.")
                        logger.info("All browsing history cleared")
                    else:
                        QMessageBox.warning(self, "Error", "Failed to clear browsing history.")

        except Exception as e:
            logger.error(f"Error clearing all history: {e}")

    def _refresh_data(self):
        """Refresh the history data."""
        self._perform_search()
        self._update_statistics()

    def refresh_theme(self):
        """Refresh theme styling (called when theme changes)."""
        self._apply_theme_styling()

    def cleanup(self):
        """Clean up resources."""
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.cancel()
            self._search_worker.wait(500)

        if self._search_timer.isActive():
            self._search_timer.stop()
