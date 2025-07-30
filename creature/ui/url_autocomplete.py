"""
URL autocomplete component for Creature Browser.
Provides history-based suggestions with theme-aware styling.
"""

import logging
from PyQt6.QtWidgets import (
    QCompleter, QLineEdit, QListView, QStyledItemDelegate,
    QStyleOptionViewItem
)
from PyQt6.QtCore import (
    Qt, QAbstractListModel, QModelIndex, QVariant, pyqtSignal,
    QTimer, QThread, pyqtSlot
)
from PyQt6.QtGui import QPainter, QPen, QColor

logger = logging.getLogger(__name__)


class HistorySearchWorker(QThread):
    """Background worker for history search to avoid blocking UI."""

    searchCompleted = pyqtSignal(list)  # Emits list of results

    def __init__(self, history_manager, query: str):
        super().__init__()
        self.history_manager = history_manager
        self.query = query
        self._cancelled = False

    def run(self):
        """Run search in background thread."""
        if self._cancelled or not self.history_manager:
            return

        try:
            results = self.history_manager.search_history(self.query)
            if not self._cancelled:
                self.searchCompleted.emit(results)
        except Exception as e:
            logger.error(f"Error in history search worker: {e}")

    def cancel(self):
        """Cancel the current search."""
        self._cancelled = True


class HistoryCompleterModel(QAbstractListModel):
    """Model for history autocomplete suggestions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._results)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> QVariant:
        if not index.isValid() or index.row() >= len(self._results):
            return QVariant()

        entry = self._results[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return entry.get('display', entry.get('url', ''))
        elif role == Qt.ItemDataRole.EditRole:
            return entry.get('text', entry.get('url', ''))
        elif role == Qt.ItemDataRole.ToolTipRole:
            return f"Visited {entry.get('visit_count', 1)} times"
        elif role == Qt.ItemDataRole.UserRole:
            return entry  # Store full entry data

        return QVariant()

    def update_results(self, results: list[dict]):
        """Update the model with new search results."""
        self.beginResetModel()
        self._results = results[:10]  # Limit to 10 results
        self.endResetModel()

    def clear_results(self):
        """Clear all results."""
        self.beginResetModel()
        self._results = []
        self.endResetModel()


class HistoryCompleterDelegate(QStyledItemDelegate):
    """Custom delegate for styling autocomplete items."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        """Custom paint method for history items."""
        painter.save()

        # Get entry data
        entry = index.data(Qt.ItemDataRole.UserRole)
        if not entry:
            super().paint(painter, option, index)
            painter.restore()
            return

        # Set up colors based on selection state
        if option.state & option.State.Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            text_color = option.palette.highlightedText().color()
        else:
            painter.fillRect(option.rect, option.palette.base())
            text_color = option.palette.text().color()

        painter.setPen(QPen(text_color))

        # Calculate layout
        margin = 8
        title_rect = option.rect.adjusted(margin, 2, -margin, -option.rect.height() // 2)
        url_rect = option.rect.adjusted(margin, option.rect.height() // 2, -margin, -2)

        # Draw title (bold)
        title = entry.get('title', 'Untitled')
        if len(title) > 60:
            title = title[:57] + "..."

        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

        # Draw URL (smaller, lighter)
        url = entry.get('url', '')
        if len(url) > 80:
            url = url[:77] + "..."

        font.setBold(False)
        font.setPointSize(max(8, font.pointSize() - 1))
        painter.setFont(font)

        # Make URL color lighter
        url_color = QColor(text_color)
        url_color.setAlpha(160)
        painter.setPen(QPen(url_color))
        painter.drawText(url_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, url)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        """Return the size hint for items."""
        return option.rect.size().expandedTo(option.widget.size() if option.widget else option.rect.size())


class HistoryCompleter(QCompleter):
    """Custom completer for history-based URL suggestions."""

    urlSelected = pyqtSignal(str)  # Emitted when user selects a URL

    def __init__(self, history_manager, parent=None):
        super().__init__(parent)

        self.history_manager = history_manager
        self._search_worker: HistorySearchWorker | None = None
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._perform_search)

        # Set up model and view
        self.model = HistoryCompleterModel(self)
        self.setModel(self.model)

        # Configure completer behavior
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setMaxVisibleItems(10)

        # Set up custom popup view
        popup = QListView()
        popup.setItemDelegate(HistoryCompleterDelegate(popup))
        self.setPopup(popup)

        # Connect signals
        self.activated.connect(self._on_completion_selected)

        logger.debug("HistoryCompleter initialized")

    def update_for_query(self, query: str):
        """Update completions for a query with debounced search."""
        if len(query) < 2:  # Don't search for very short queries
            self.model.clear_results()
            return

        # Cancel any existing search
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.cancel()
            self._search_worker.wait(100)  # Wait briefly for cancellation

        # Store query and start debounced search
        self._current_query = query
        self._search_timer.start(150)  # 150ms debounce

    def _perform_search(self):
        """Perform the actual search in background thread."""
        if not hasattr(self, '_current_query') or not self.history_manager:
            return

        query = self._current_query

        # Start background search
        self._search_worker = HistorySearchWorker(self.history_manager, query)
        self._search_worker.searchCompleted.connect(self._on_search_completed)
        self._search_worker.start()

    @pyqtSlot(list)
    def _on_search_completed(self, results: list[dict]):
        """Handle search completion."""
        try:
            self.model.update_results(results)

            # Show popup if we have results and widget is focused
            if results and self.widget() and self.widget().hasFocus():
                self.complete()

        except Exception as e:
            logger.error(f"Error handling search completion: {e}")

    def _on_completion_selected(self, completion: str):
        """Handle when user selects a completion."""
        try:
            # Find the selected entry
            for i in range(self.model.rowCount()):
                index = self.model.index(i, 0)
                entry = self.model.data(index, Qt.ItemDataRole.UserRole)
                if entry and entry.get('text') == completion:
                    url = entry.get('url', completion)
                    self.urlSelected.emit(url)
                    break

        except Exception as e:
            logger.error(f"Error handling completion selection: {e}")

    def clear_results(self):
        """Clear all autocomplete results."""
        self.model.clear_results()

    def cleanup(self):
        """Clean up resources."""
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.cancel()
            self._search_worker.wait(500)

        if self._search_timer.isActive():
            self._search_timer.stop()


class HistoryURLLineEdit(QLineEdit):
    """Enhanced QLineEdit with history-based autocomplete."""

    navigationRequested = pyqtSignal(str)  # Emitted when user wants to navigate

    def __init__(self, history_manager, parent=None):
        super().__init__(parent)

        self.history_manager = history_manager
        self._completer = HistoryCompleter(history_manager, self)
        self.setCompleter(self._completer)

        # Connect signals
        self.textChanged.connect(self._on_text_changed)
        self.returnPressed.connect(self._on_return_pressed)
        self._completer.urlSelected.connect(self._on_url_selected)

        # Apply theme-aware styling
        self._apply_theme_styling()

        logger.debug("HistoryURLLineEdit initialized")

    def _on_text_changed(self, text: str):
        """Handle text changes for autocomplete."""
        if self.history_manager and self.history_manager.is_enabled():
            self._completer.update_for_query(text)

    def _on_return_pressed(self):
        """Handle return key press."""
        text = self.text().strip()
        if text:
            self.navigationRequested.emit(text)

    def _on_url_selected(self, url: str):
        """Handle URL selection from autocomplete."""
        self.setText(url)
        self.navigationRequested.emit(url)

    def _apply_theme_styling(self):
        """Apply theme-aware styling to the URL bar."""
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

            # Apply URL bar styling
            style = f"""
                QLineEdit {{
                    padding: 8px 12px;
                    font-size: 14px;
                    border: 2px solid {colors.get('border_color', '#ccc')};
                    border-radius: 6px;
                    background-color: {colors.get('url_bar_bg', '#ffffff')};
                    color: {colors.get('text_color', '#000000')};
                    selection-background-color: {colors.get('accent', '#0078d4')};
                }}
                QLineEdit:focus {{
                    border-color: {colors.get('accent', '#0078d4')};
                }}
            """
            self.setStyleSheet(style)

        except Exception as e:
            logger.debug(f"Failed to apply theme styling: {e}")

    def refresh_theme(self):
        """Refresh theme styling (called when theme changes)."""
        self._apply_theme_styling()

    def cleanup(self):
        """Clean up resources."""
        if self._completer:
            self._completer.cleanup()

    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.cleanup()
        except Exception:
            pass
