"""
History editor UI for Creature Browser.
Provides interface for viewing, searching, and managing browsing history.
"""

import logging
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QListWidget, QListWidgetItem, QLabel, QMessageBox, QMenu, QAbstractItemView, QSplitter, QTextEdit, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QAction, QKeySequence, QShortcut

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
        self._setup_shortcuts()
        self._apply_theme_styling()
        self._load_initial_data()

        logger.debug("HistoryEditorWidget initialized")
    
    def _get_base_font_size(self):
        """Get the base font size from global settings."""
        base_font = QApplication.instance().font()
        return base_font.pointSize()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header - single row with everything
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(12)

        # Title (very compact)
        title_label = QLabel("History")
        title_font = QApplication.instance().font()
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        # Search field (in header to save space)
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search history...")
        self.search_field.textChanged.connect(self._on_search_text_changed)
        header_layout.addWidget(self.search_field)

        self.clear_search_btn = QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self._clear_search)
        header_layout.addWidget(self.clear_search_btn)

        # Clear all button (compact)
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.clicked.connect(self._clear_all_history)
        header_layout.addWidget(self.clear_all_btn)

        # Statistics (compact)
        self.stats_label = QLabel("Loading...")
        self.stats_label.setStyleSheet("color: gray;")
        header_layout.addWidget(self.stats_label)

        # Add header with NO stretch factor (minimal space)
        layout.addWidget(header_widget, 0)

        # Add list controls above splitter so they're always visible
        controls_widget = QWidget()
        list_controls = QHBoxLayout(controls_widget)
        list_controls.setContentsMargins(8, 5, 8, 5)
        list_controls.setSpacing(8)

        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.clicked.connect(self._delete_selected_entries)
        list_controls.addWidget(self.delete_selected_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_data)
        list_controls.addWidget(self.refresh_btn)

        list_controls.addStretch()
        layout.addWidget(controls_widget, 0)  # No stretch - minimal space

        # Main content area with splitter - this gets ALL remaining space
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # History list (simplified - just the list widget)
        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.history_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._show_context_menu)
        splitter.addWidget(self.history_list)

        # Compact details panel
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(5, 5, 0, 0)
        details_layout.setSpacing(3)

        # Small details label
        details_label = QLabel("Details")
        details_label.setStyleSheet("font-weight: bold;")
        details_layout.addWidget(details_label)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMinimumWidth(200)  # Minimum width, but can expand
        details_layout.addWidget(self.details_text)

        splitter.addWidget(details_widget)

        # Set stretch factors: history list gets more priority but details can expand
        splitter.setStretchFactor(0, 3)  # History list gets 3 parts
        splitter.setStretchFactor(1, 1)  # Details gets 1 part

        # Set reasonable initial sizes - will adapt to window width
        # These are just initial hints, the stretch factors control resizing
        splitter.setSizes([600, 200])

        # Add splitter with HIGH stretch factor - this takes ALL remaining space
        layout.addWidget(splitter, 1)

        # Connect selection change to update details
        self.history_list.itemSelectionChanged.connect(self._update_details)

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts for the history editor."""
        # Ctrl+F - Focus search field
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(lambda: self.search_field.setFocus())

        # Ctrl+A - Select all items in history list
        select_all_shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        select_all_shortcut.activated.connect(self.history_list.selectAll)

        # Delete key - Delete selected entries
        delete_shortcut = QShortcut(QKeySequence("Delete"), self)
        delete_shortcut.activated.connect(self._delete_selected_entries)

        # Ctrl+R or F5 - Refresh
        refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        refresh_shortcut.activated.connect(self._refresh_data)

        f5_shortcut = QShortcut(QKeySequence("F5"), self)
        f5_shortcut.activated.connect(self._refresh_data)

        # Ctrl+C - Copy selected entries URLs to clipboard
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self._copy_selected_entries)

        # Escape - Clear search
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self._clear_search)

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

            # Get proper theme colors with better contrast
            text_color = colors.get("text_color", "#000000")
            border_color = colors.get("border_color", "#ccc")
            accent_color = colors.get("accent", "#0078d4")

            # Use theme colors properly - try multiple fallbacks
            list_text_color = colors.get("text_color", "#000000")
            list_bg = colors.get("window_bg", colors.get("background", "#ffffff"))
            list_alt_bg = colors.get("url_bar_bg", colors.get("tab_bg", colors.get("card_bg", "#f8f9fa")))

            # Ensure we have proper input background
            input_bg = colors.get("url_bar_bg", colors.get("input_bg", list_bg))

            # Apply styling with improved contrast
            widget_style = f"""
                QLineEdit {{
                    padding: 6px 10px;
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    background-color: {input_bg};
                    color: {text_color};
                }}
                QListWidget {{
                    border: 1px solid {border_color};
                    background-color: {list_bg};
                    color: {list_text_color};
                    alternate-background-color: {list_alt_bg};
                }}
                QListWidget::item {{
                    padding: 8px;
                    border-bottom: 1px solid {border_color};
                    color: {list_text_color};
                }}
                QListWidget::item:selected {{
                    background-color: {accent_color};
                    color: white;
                }}
                QListWidget::item:hover {{
                    background-color: {list_alt_bg};
                }}
                QTextEdit {{
                    border: 1px solid {border_color};
                    background-color: {input_bg};
                    color: {text_color};
                }}
            """

            # Apply button styling to match theme
            button_style = """
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    padding: 6px 12px;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
            """

            self.search_field.setStyleSheet(widget_style)
            self.history_list.setStyleSheet(widget_style)
            self.details_text.setStyleSheet(widget_style)
            self.clear_all_btn.setStyleSheet(button_style)

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

                # Get theme colors for HTML styling
                parent_browser = self.parent()
                while parent_browser and not hasattr(parent_browser, "theme_manager"):
                    parent_browser = parent_browser.parent()

                if parent_browser and hasattr(parent_browser, "theme_manager"):
                    current_theme = getattr(parent_browser, "current_theme", "light")
                    theme = parent_browser.theme_manager.themes.get(current_theme, {})
                    colors = theme.get("colors", {}) if theme else {}
                else:
                    colors = {}

                text_color = colors.get("text_color", "#000000")
                accent_color = colors.get("accent", "#0078d4")
                base_font_size = self._get_base_font_size()

                details_html = f"""
                <div style="color: {text_color}; font-family: system-ui, -apple-system, sans-serif; font-size: {base_font_size}px;">
                    <h3 style="color: {text_color}; margin-top: 0;">Entry Details</h3>
                    <p style="margin: 8px 0;"><strong>Title:</strong><br/>
                       <span>{title}</span></p>
                    <p style="margin: 8px 0;"><strong>URL:</strong><br/>
                       <a href="{url}" style="color: {accent_color}; word-break: break-all;">{url}</a></p>
                    <p style="margin: 8px 0;"><strong>Host:</strong>
                       <span>{host}</span></p>
                    <p style="margin: 8px 0;"><strong>Visit Count:</strong>
                       <span>{visit_count}</span></p>
                    <p style="margin: 8px 0;"><strong>Last Visited:</strong><br/>
                       <span>{last_date}</span></p>
                </div>
                """

                self.details_text.setHtml(details_html)
            else:
                # Multiple items selected - theme-aware HTML
                parent_browser = self.parent()
                while parent_browser and not hasattr(parent_browser, "theme_manager"):
                    parent_browser = parent_browser.parent()

                if parent_browser and hasattr(parent_browser, "theme_manager"):
                    current_theme = getattr(parent_browser, "current_theme", "light")
                    theme = parent_browser.theme_manager.themes.get(current_theme, {})
                    colors = theme.get("colors", {}) if theme else {}
                else:
                    colors = {}

                text_color = colors.get("text_color", "#000000")
                base_font_size = self._get_base_font_size()

                count = len(selected_items)
                multi_html = f"""
                <div style="color: {text_color}; font-family: system-ui, -apple-system, sans-serif; font-size: {base_font_size}px;">
                    <h3 style="color: {text_color}; margin-top: 0;">Multiple Selection</h3>
                    <p>{count} entries selected</p>
                </div>
                """
                self.details_text.setHtml(multi_html)

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

    def _copy_selected_entries(self):
        """Copy selected entries URLs to clipboard."""
        try:
            selected_items = self.history_list.selectedItems()
            if not selected_items:
                return

            urls = []
            for item in selected_items:
                entry = item.data(Qt.ItemDataRole.UserRole)
                url = entry.get("url", "")
                if url:
                    urls.append(url)

            if urls:
                from PyQt6.QtWidgets import QApplication

                clipboard = QApplication.clipboard()
                clipboard.setText("\n".join(urls))
                logger.info(f"Copied {len(urls)} URLs to clipboard")

        except Exception as e:
            logger.error(f"Error copying entries: {e}")

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
