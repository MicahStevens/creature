#!/usr/bin/env python3
import sys
import os
import argparse
from pathlib import Path
import importlib.resources
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QTabWidget,
    QMessageBox,
    QDialog,
    QListWidget,
    QDialogButtonBox,
    QLabel,
    QListWidgetItem,
    QSplashScreen,
    QTextBrowser,
    QMenu,
    QInputDialog,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineScript, QWebEnginePage
from PyQt6.QtCore import QUrl, QTimer, Qt, QSize
from PyQt6.QtGui import QColor, QShortcut, QKeySequence, QPixmap, QIcon, QAction
import subprocess
import logging

# Import refactored modules
from creature.config.manager import config as creature_config
from creature.security.keepassxc import keepass_manager, KeePassXCError
from creature.utils.helpers import process_url_or_search
from creature.security.ssl_handler import CertificateDetailsDialog
from creature.ui.bookmarks import BookmarkToolbar
from creature.ui.session_manager import BrowserSessionManager
from creature.config.profiles import ProfileManager
from creature.ui.themes import ThemeManager
from creature.browser.web_engine import SSLAwarePage
from creature.history import HistoryManager
from creature.ui.url_autocomplete import HistoryURLLineEdit
from creature.ui.history_editor import HistoryEditorWidget

# Application constants
from creature import CREATURE_VERSION, CREATURE_AUTHOR, CREATURE_LICENSE


# Configure logging
def setup_logging():
    """Configure logging based on config settings."""
    log_level = getattr(logging, creature_config.logging.level, logging.WARNING)
    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


# Set up logging early
setup_logging()

# Create module logger
logger = logging.getLogger(__name__)

# Utility functions have been moved to separate modules (utilities.py and ssl_handler.py)


# Resource loading utilities
def get_data_path(filename):
    """Get path to a data file using importlib.resources."""
    try:
        if "/" in filename:
            # Handle subdirectories in data/
            parts = filename.split("/")
            subdir = parts[0]
            file = "/".join(parts[1:])
            if subdir == "scripts":
                return importlib.resources.files("creature").parent / "data" / "scripts" / file
            elif subdir == "icons":
                return importlib.resources.files("creature").parent / "data" / "icons" / file
            elif subdir == "images":
                return importlib.resources.files("creature").parent / "data" / "images" / file
            else:
                return importlib.resources.files("creature").parent / "data" / filename
        else:
            # File in data root
            return importlib.resources.files("creature").parent / "data" / filename
    except Exception as e:
        logger.debug(f"Resource loading failed for {filename}: {e}")
        # Fallback to relative path from current file
        return Path(__file__).parent.parent.parent / "data" / filename


# Classes have been moved to separate modules:
# - BookmarkManager, FaviconManager, BookmarkToolbar -> bookmarks.py
# - ProfileManager -> profiles.py
# - ThemeManager -> themes.py
# - SSLAwarePage -> web_engine.py
# - CertificateDetailsDialog -> ssl_handler.py


class KeePassXCWebEngineView(QWebEngineView):
    """Custom QWebEngineView with KeePassXC integration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.master_password = None
        self._inject_bridge_script()

    def _inject_bridge_script(self):
        """Inject the KeePassXC bridge JavaScript into all pages."""
        if not keepass_manager.enabled:
            logger.debug("Bridge injection skipped - KeePassXC disabled")
            return

        # Read the bridge script
        bridge_script_path = get_data_path("scripts/keepassxc_bridge.js")
        logger.debug(f"Looking for bridge script at: {bridge_script_path}")
        if not bridge_script_path.exists():
            logger.debug("KeePassXC bridge script not found")
            return

        try:
            with open(bridge_script_path, encoding="utf-8") as f:
                bridge_code = f.read()
            logger.debug(f"Bridge script loaded, {len(bridge_code)} characters")
        except Exception as e:
            logger.error(f"Failed to read KeePassXC bridge script: {e}")
            return

        # Create and inject the script
        script = QWebEngineScript()
        script.setSourceCode(bridge_code)
        script.setName("KeePassXCBridge")
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)  # Use MainWorld instead of ApplicationWorld
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)  # Inject earlier
        script.setRunsOnSubFrames(True)

        self.page().scripts().insert(script)
        logger.debug("Bridge script injected successfully")

    def contextMenuEvent(self, event):
        """Override context menu to add custom options."""
        # Store the global position immediately to ensure accuracy
        global_pos = event.globalPos()
        pos = event.pos()
        
        # Get the standard context menu data
        context_data = self.page().contextMenuData()
        
        # Create custom menu
        menu = QMenu(self)
        
        # Get information about the clicked element (including links)
        js_code = f"""
        (function() {{
            var element = document.elementFromPoint({pos.x()}, {pos.y()});
            if (!element) return null;
            
            // Check if it's a link or inside a link
            var linkElement = element.closest('a');
            var linkUrl = linkElement ? linkElement.href : null;
            
            // Get selected text
            var selectedText = window.getSelection().toString();
            
            var result = {{
                linkUrl: linkUrl,
                selectedText: selectedText,
                isEditable: element.isContentEditable || ['input', 'textarea'].includes(element.tagName.toLowerCase())
            }};

            if (['input', 'textarea'].includes(element.tagName.toLowerCase())) {{
                result.isFormField = true;
                result.type = element.type || 'text';
                result.name = element.name || '';
                result.id = element.id || '';
                result.placeholder = element.placeholder || '';
                result.isPassword = element.type === 'password';
                result.isEmail = element.type === 'email' || element.name.toLowerCase().includes('email');
                result.isUsername = element.name.toLowerCase().includes('user') ||
                                   element.id.toLowerCase().includes('user') ||
                                   element.placeholder.toLowerCase().includes('user');
            }}
            return result;
        }})();
        """

        # Execute JavaScript to get element info, then build menu
        self.page().runJavaScript(js_code, lambda result: self._build_context_menu(menu, event, result, global_pos, context_data))

    def _build_context_menu(self, menu, event, element_info, global_pos, context_data):
        """Build context menu with all appropriate options."""
        # Navigation actions
        back_action = QAction("Back", self)
        back_action.setEnabled(self.page().history().canGoBack())
        back_action.triggered.connect(self.back)
        menu.addAction(back_action)

        forward_action = QAction("Forward", self)
        forward_action.setEnabled(self.page().history().canGoForward())
        forward_action.triggered.connect(self.forward)
        menu.addAction(forward_action)

        reload_action = QAction("Reload", self)
        reload_action.triggered.connect(self.reload)
        menu.addAction(reload_action)
        
        menu.addSeparator()
        
        # Link-specific actions
        if element_info and element_info.get("linkUrl"):
            # Copy link action
            copy_link_action = QAction("Copy Link", self)
            copy_link_action.triggered.connect(lambda: self._copy_link_to_clipboard(element_info.get("linkUrl")))
            menu.addAction(copy_link_action)
            
            # Open link in new tab (if tabs are enabled)
            parent_browser = self.parent()
            while parent_browser and not isinstance(parent_browser, QMainWindow):
                parent_browser = parent_browser.parent()
            
            if parent_browser and hasattr(parent_browser, "add_new_tab") and not parent_browser.force_new_window:
                open_link_tab_action = QAction("Open Link in New Tab", self)
                open_link_tab_action.triggered.connect(lambda: parent_browser.add_new_tab(element_info.get("linkUrl")))
                menu.addAction(open_link_tab_action)
            
            # Open link in new window
            if parent_browser:
                open_link_window_action = QAction("Open Link in New Window", self)
                open_link_window_action.triggered.connect(lambda: parent_browser.new_window(element_info.get("linkUrl")))
                menu.addAction(open_link_window_action)
            
            menu.addSeparator()
        
        # Copy action (for selected text or general copy)
        if element_info and element_info.get("selectedText"):
            copy_action = QAction("Copy", self)
            copy_action.triggered.connect(lambda: self.page().triggerAction(QWebEnginePage.WebAction.Copy))
            menu.addAction(copy_action)
        
        # Paste action (for editable fields)
        if element_info and element_info.get("isEditable"):
            paste_action = QAction("Paste", self)
            paste_action.triggered.connect(lambda: self.page().triggerAction(QWebEnginePage.WebAction.Paste))
            menu.addAction(paste_action)
            
            # Cut action for editable fields with selected text
            if element_info.get("selectedText"):
                cut_action = QAction("Cut", self)
                cut_action.triggered.connect(lambda: self.page().triggerAction(QWebEnginePage.WebAction.Cut))
                menu.addAction(cut_action)
        
        # Select All action
        select_all_action = QAction("Select All", self)
        select_all_action.triggered.connect(lambda: self.page().triggerAction(QWebEnginePage.WebAction.SelectAll))
        menu.addAction(select_all_action)
        
        # Add KeePassXC options if applicable
        if keepass_manager.enabled and keepass_manager.config.show_context_menu:
            if element_info and element_info.get("isFormField"):
                menu.addSeparator()

                # Add KeePassXC actions
                if element_info.get("isPassword"):
                    fill_password_action = QAction("Fill Password from KeePassXC", self)
                    fill_password_action.triggered.connect(lambda: self._fill_password(event.pos()))
                    menu.addAction(fill_password_action)
                elif element_info.get("isUsername") or element_info.get("isEmail"):
                    fill_username_action = QAction("Fill Username from KeePassXC", self)
                    fill_username_action.triggered.connect(lambda: self._fill_username(event.pos()))
                    menu.addAction(fill_username_action)
                else:
                    # Generic field
                    fill_field_action = QAction("Fill from KeePassXC", self)
                    fill_field_action.triggered.connect(lambda: self._fill_generic_field(event.pos()))
                    menu.addAction(fill_field_action)

                # Add fill form action
                fill_form_action = QAction("Fill Login Form from KeePassXC", self)
                fill_form_action.triggered.connect(self._fill_login_form)
                menu.addAction(fill_form_action)

                # Add search entries action
                search_action = QAction("Search KeePassXC Entries...", self)
                search_action.triggered.connect(self._search_entries)
                menu.addAction(search_action)

        # Show the menu at the stored global position
        menu.popup(global_pos)
    
    def _copy_link_to_clipboard(self, url):
        """Copy a URL to the clipboard."""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(url)

    def _get_master_password(self):
        """Get master password from user if not cached."""
        if self.master_password and keepass_manager.test_database_access(self.master_password):
            return self.master_password

        # Prompt for master password
        from PyQt6.QtWidgets import QLineEdit

        password, ok = QInputDialog.getText(self, "KeePassXC Master Password", "Enter your KeePassXC master password:", QLineEdit.EchoMode.Password)

        if ok and password:
            if keepass_manager.test_database_access(password):
                self.master_password = password
                return password
            else:
                QMessageBox.warning(self, "Error", "Invalid master password")

        return None

    def _fill_password(self, pos):
        """Fill password into the currently focused field."""
        password = self._get_master_password()
        if not password:
            return

        # Get entries for current domain
        current_url = self.url().toString()
        entries = keepass_manager.search_by_url(current_url, password)

        if not entries:
            QMessageBox.information(self, "KeePassXC", "No entries found for this domain")
            return

        # If multiple entries, show selection dialog
        if len(entries) > 1:
            entry = self._select_entry(entries)
            if not entry:
                return
        else:
            entry = entries[0]

        # Get full entry details
        full_entry = keepass_manager.get_entry_details(entry.title, password)
        if not full_entry or not full_entry.password:
            QMessageBox.warning(self, "Error", "Could not retrieve password")
            return

        # Fill password into focused field or find password field at click position
        js_code = f"""
        console.log('KeePassXC: Filling password for entry: {self._escape_js_string(entry.title)}');
        console.log('KeePassXC: Bridge available?', typeof window.KeePassXCBridge !== 'undefined');

        if (typeof window.KeePassXCBridge === 'undefined') {{
            console.log('KeePassXC: Bridge not available - filling directly');

            // Fallback: direct filling without bridge
            var targetElement = document.activeElement;
            if (!targetElement || targetElement.tagName !== 'INPUT') {{
                targetElement = document.elementFromPoint({pos.x()}, {pos.y()});
            }}

            if (targetElement && targetElement.tagName === 'INPUT') {{
                targetElement.focus();
                targetElement.value = '{self._escape_js_string(full_entry.password)}';

                // Trigger events manually
                ['input', 'change', 'blur'].forEach(function(eventType) {{
                    var event = new Event(eventType, {{ bubbles: true, cancelable: true }});
                    targetElement.dispatchEvent(event);
                }});

                console.log('KeePassXC: Password filled directly');
                'Password filled (direct)';
            }} else {{
                console.log('KeePassXC: No input field found');
                'No input field found';
            }}
        }} else {{
            // Use bridge if available
            var targetElement = document.activeElement;
            console.log('KeePassXC: Active element:', targetElement);

            if (!targetElement || targetElement.tagName !== 'INPUT') {{
                targetElement = document.elementFromPoint({pos.x()}, {pos.y()});
                console.log('KeePassXC: Element at click position:', targetElement);
            }}

            if (targetElement && targetElement.tagName === 'INPUT') {{
                var result = KeePassXCBridge.fillField(targetElement, '{self._escape_js_string(full_entry.password)}');
                console.log('KeePassXC: Password fill result:', result);
                result ? 'Password filled (bridge)' : 'Password fill failed';
            }} else {{
                console.log('KeePassXC: No valid input field found');
                'No input field found';
            }}
        }}
        """

        self.page().runJavaScript(js_code, lambda result: logger.debug(f"Password fill result: {result}"))

    def _fill_username(self, pos):
        """Fill username into the currently focused field."""
        password = self._get_master_password()
        if not password:
            return

        # Get entries for current domain
        current_url = self.url().toString()
        entries = keepass_manager.search_by_url(current_url, password)

        if not entries:
            QMessageBox.information(self, "KeePassXC", "No entries found for this domain")
            return

        # If multiple entries, show selection dialog
        if len(entries) > 1:
            entry = self._select_entry(entries)
            if not entry:
                return
        else:
            entry = entries[0]

        # Get full entry details
        full_entry = keepass_manager.get_entry_details(entry.title, password)
        if not full_entry or not full_entry.username:
            QMessageBox.warning(self, "Error", "Could not retrieve username")
            return

        # Fill username into focused field or find field at click position
        js_code = f"""
        console.log('KeePassXC: Filling username for entry: {self._escape_js_string(entry.title)}');
        console.log('KeePassXC: Bridge available?', typeof window.KeePassXCBridge !== 'undefined');

        if (typeof window.KeePassXCBridge === 'undefined') {{
            console.log('KeePassXC: Bridge not available - filling directly');

            // Fallback: direct filling without bridge
            var targetElement = document.activeElement;
            if (!targetElement || targetElement.tagName !== 'INPUT') {{
                targetElement = document.elementFromPoint({pos.x()}, {pos.y()});
            }}

            if (targetElement && targetElement.tagName === 'INPUT') {{
                targetElement.focus();
                targetElement.value = '{self._escape_js_string(full_entry.username)}';

                // Trigger events manually
                ['input', 'change', 'blur'].forEach(function(eventType) {{
                    var event = new Event(eventType, {{ bubbles: true, cancelable: true }});
                    targetElement.dispatchEvent(event);
                }});

                console.log('KeePassXC: Username filled directly');
                'Username filled (direct)';
            }} else {{
                console.log('KeePassXC: No input field found');
                'No input field found';
            }}
        }} else {{
            // Use bridge if available
            var targetElement = document.activeElement;
            console.log('KeePassXC: Active element:', targetElement);

            if (!targetElement || targetElement.tagName !== 'INPUT') {{
                targetElement = document.elementFromPoint({pos.x()}, {pos.y()});
                console.log('KeePassXC: Element at click position:', targetElement);
            }}

            if (targetElement && targetElement.tagName === 'INPUT') {{
                var result = KeePassXCBridge.fillField(targetElement, '{self._escape_js_string(full_entry.username)}');
                console.log('KeePassXC: Username fill result:', result);
                result ? 'Username filled (bridge)' : 'Username fill failed';
            }} else {{
                console.log('KeePassXC: No valid input field found');
                'No input field found';
            }}
        }}
        """

        self.page().runJavaScript(js_code, lambda result: logger.debug(f"Username fill result: {result}"))

    def _fill_generic_field(self, pos):
        """Fill generic field - let user choose what to fill."""
        password = self._get_master_password()
        if not password:
            return

        # Show dialog to choose what to fill
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Fill Field")
        layout = QVBoxLayout(dialog)

        username_radio = QRadioButton("Username")
        password_radio = QRadioButton("Password")
        username_radio.setChecked(True)

        layout.addWidget(QLabel("What would you like to fill?"))
        layout.addWidget(username_radio)
        layout.addWidget(password_radio)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        fill_username = username_radio.isChecked()

        if fill_username:
            self._fill_username(pos)
        else:
            self._fill_password(pos)

    def _fill_login_form(self):
        """Fill entire login form."""
        password = self._get_master_password()
        if not password:
            return

        # Get entries for current domain
        current_url = self.url().toString()
        entries = keepass_manager.search_by_url(current_url, password)

        if not entries:
            QMessageBox.information(self, "KeePassXC", "No entries found for this domain")
            return

        # If multiple entries, show selection dialog
        if len(entries) > 1:
            entry = self._select_entry(entries)
            if not entry:
                return
        else:
            entry = entries[0]

        # Get full entry details
        full_entry = keepass_manager.get_entry_details(entry.title, password)
        if not full_entry:
            QMessageBox.warning(self, "Error", "Could not retrieve entry details")
            return

        # Fill the login form
        username = self._escape_js_string(full_entry.username) if full_entry.username else ""
        password_str = self._escape_js_string(full_entry.password) if full_entry.password else ""

        js_code = f"""
        if (window.KeePassXCBridge) {{
            var result = KeePassXCBridge.fillLoginForm('{username}', '{password_str}', false);
            result;
        }} else {{
            'Bridge not available';
        }}
        """

        self.page().runJavaScript(js_code, self._fill_form_callback)

    def _fill_form_callback(self, result):
        """Callback for form filling result."""
        if isinstance(result, dict):
            if result.get("success"):
                message = "Login form filled successfully"
                if result.get("errors"):
                    message += f"\nWarnings: {', '.join(result['errors'])}"
                QMessageBox.information(self, "KeePassXC", message)
            else:
                error_msg = "Failed to fill login form"
                if result.get("errors"):
                    error_msg += f"\nErrors: {', '.join(result['errors'])}"
                QMessageBox.warning(self, "Error", error_msg)
        else:
            logger.debug(f"Form fill result: {result}")

    def _search_entries(self):
        """Show dialog to search and select entries."""
        password = self._get_master_password()
        if not password:
            return

        # Show entry selection dialog with all entries
        try:
            all_entries = keepass_manager.get_all_entries(password)
            if not all_entries:
                QMessageBox.information(self, "KeePassXC", "No entries found in database")
                return

            # Create entries list for selection
            entries = [keepass_manager.get_entry_details(title, password) for title in all_entries[:20]]  # Limit to first 20
            entries = [e for e in entries if e]  # Filter out None entries

            selected_entry = self._select_entry(entries)
            if selected_entry:
                # Fill form with selected entry
                self._fill_selected_entry(selected_entry)

        except KeePassXCError as e:
            QMessageBox.warning(self, "KeePassXC Error", str(e))

    def _fill_selected_entry(self, entry):
        """Fill form with a selected entry."""
        username = self._escape_js_string(entry.username) if entry.username else ""
        password_str = self._escape_js_string(entry.password) if entry.password else ""

        js_code = f"""
        if (window.KeePassXCBridge) {{
            KeePassXCBridge.fillLoginForm('{username}', '{password_str}', false);
        }}
        """

        self.page().runJavaScript(js_code)

    def _select_entry(self, entries):
        """Show dialog to select from multiple entries."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QListWidgetItem

        dialog = QDialog(self)
        dialog.setWindowTitle("Select KeePassXC Entry")
        dialog.resize(400, 300)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Select an entry:"))

        entry_list = QListWidget()
        for entry in entries:
            item_text = f"{entry.title}"
            if entry.username:
                item_text += f" ({entry.username})"
            if entry.url:
                item_text += f" - {entry.url[:50]}..."

            item = QListWidgetItem(item_text)
            item.setData(256, entry)  # Store entry object
            entry_list.addItem(item)

        if entry_list.count() > 0:
            entry_list.setCurrentRow(0)

        layout.addWidget(entry_list)

        # Connect double-click
        entry_list.itemDoubleClicked.connect(dialog.accept)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            current_item = entry_list.currentItem()
            if current_item:
                return current_item.data(256)

        return None

    def _escape_js_string(self, value):
        """Escape string for safe JavaScript injection."""
        if not value:
            return ""
        return value.replace("'", "\\'").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


class SplashScreen(QSplashScreen):
    """Custom splash screen with Creature branding."""

    def __init__(self):
        # Load splash image
        splash_path = Path(__file__).parent / "img" / "splash.png"
        if splash_path.exists():
            pixmap = QPixmap(str(splash_path))
            # Scale to reasonable size if too large
            if pixmap.width() > 800 or pixmap.height() > 600:
                pixmap = pixmap.scaled(800, 600, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        else:
            # Create a simple colored splash if image not found
            pixmap = QPixmap(500, 350)
            pixmap.fill(QColor(45, 55, 65))

        super().__init__(pixmap)

        # Set window flags to ensure visibility and floating behavior
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)

        # Set window class for Wayland/Hyprland recognition
        self.setProperty("_q_wayland_window_type", "splash")

        # Set window class name for window managers
        if hasattr(self, "setWindowClassName"):
            self.setWindowClassName("creature-splash")

        # Center the splash screen on the screen
        from PyQt6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2, (screen.height() - size.height()) // 2)

        # Show loading message with better styling
        self.showMessage(f"Starting Creature Browser v{CREATURE_VERSION}...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor(255, 255, 255))

        # Set up timer for loading messages
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_message)
        self.message_index = 0
        self.messages = [f"Starting Creature Browser v{CREATURE_VERSION}...", "Loading configuration...", "Initializing browser engine...", "Setting up profiles...", "Applying theme...", "Ready!"]
        self.timer.start(300)  # Update every 300ms

        # Additional Wayland/Hyprland compatibility
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

    def update_message(self):
        """Update the loading message."""
        if self.message_index < len(self.messages):
            self.showMessage(self.messages[self.message_index], Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor(255, 255, 255))
            self.message_index += 1
        else:
            self.timer.stop()


class AboutDialog(QDialog):
    """About dialog showing version, author, and license information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Creature Browser")
        self.setFixedSize(500, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Logo
        logo_path = get_data_path("icons/logo.png")
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path))
            # Scale logo to reasonable size
            if pixmap.width() > 128 or pixmap.height() > 128:
                pixmap = pixmap.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo_label)

        # Title
        title_label = QLabel("Creature Browser")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        # Version
        version_label = QLabel(f"Version {CREATURE_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("font-size: 14px; margin: 5px;")
        layout.addWidget(version_label)

        # Description
        desc_label = QLabel("A privacy-focused web browser with profile isolation,\ncustom themes, and KeePassXC integration.")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("margin: 10px;")
        layout.addWidget(desc_label)

        # Author
        author_label = QLabel(f"Developed by: {CREATURE_AUTHOR}")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author_label.setStyleSheet("margin: 5px;")
        layout.addWidget(author_label)

        # License
        license_label = QLabel(f"License: {CREATURE_LICENSE}")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_label.setStyleSheet("margin: 5px;")
        layout.addWidget(license_label)

        # Configuration file info
        config_info_label = QLabel("Configuration:")
        config_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        config_info_label.setStyleSheet("margin-top: 15px; margin-bottom: 5px; font-weight: bold;")
        layout.addWidget(config_info_label)

        # Configuration file path (clickable)
        self.config_path_label = QLabel()
        self.setup_config_path_display()
        self.config_path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.config_path_label.setStyleSheet("margin: 5px; color: #0078d4; text-decoration: underline; cursor: pointer;")
        self.config_path_label.setWordWrap(True)
        self.config_path_label.mousePressEvent = self.open_config_folder
        layout.addWidget(self.config_path_label)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)
        layout.addWidget(close_button)
        layout.setAlignment(close_button, Qt.AlignmentFlag.AlignCenter)

    def setup_config_path_display(self):
        """Set up the configuration file path display."""
        config_path = creature_config.config_file_path
        # Show just the filename and parent directory for readability
        display_path = f"{config_path.parent.name}/{config_path.name}"
        self.config_path_label.setText(f"{display_path}\n(Click to open folder)")
        self.config_path = config_path

    def open_config_folder(self, event):
        """Open the configuration file folder in system file manager."""
        import sys

        try:
            config_folder = self.config_path.parent

            if sys.platform == "win32":
                # Windows
                subprocess.run(["explorer", str(config_folder)], check=True)
            elif sys.platform == "darwin":
                # macOS
                subprocess.run(["open", str(config_folder)], check=True)
            else:
                # Linux and other Unix-like systems
                subprocess.run(["xdg-open", str(config_folder)], check=True)

        except Exception as e:
            # Fallback: show message box with path
            QMessageBox.information(self, "Configuration Path", f"Configuration file location:\n{self.config_path}\n\nUnable to open folder: {e}")


class HelpDialog(QDialog):
    """Help dialog displaying documentation from markdown files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Creature Browser Help")
        self.resize(800, 600)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Create text browser for displaying help content
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        layout.addWidget(self.text_browser)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        # Load help content
        self._load_help_content()

    def _load_help_content(self):
        """Load help content from markdown files."""
        docs_dir = Path(__file__).parent / "docs"

        help_content = f"""
        <h1>Creature Browser Help</h1>
        <p><strong>Version:</strong> {CREATURE_VERSION}</p>
        <p><strong>Author:</strong> {CREATURE_AUTHOR}</p>
        <hr>

        <h2>Quick Start</h2>
        <p>Creature Browser is a privacy-focused web browser with advanced features:</p>
        <ul>
            <li><strong>Profile Isolation:</strong> Complete separation between different browsing contexts</li>
            <li><strong>Custom Themes:</strong> 8 built-in themes with custom theme support</li>
            <li><strong>KeePassXC Integration:</strong> Secure password manager integration</li>
            <li><strong>Smart URL Bar:</strong> Intelligent URL/search detection</li>
            <li><strong>Wayland Support:</strong> Optimized for modern Linux desktops</li>
        </ul>

        <h2>Keyboard Shortcuts</h2>
        <table border="1" cellpadding="5">
            <tr><th>Shortcut</th><th>Action</th></tr>
            <tr><td>Ctrl+G</td><td>Focus URL bar</td></tr>
            <tr><td>Ctrl+N</td><td>New window</td></tr>
            <tr><td>Ctrl+T</td><td>New tab</td></tr>
            <tr><td>Ctrl+W</td><td>Close tab</td></tr>
            <tr><td>Ctrl+Shift+Left/Right</td><td>Switch tabs</td></tr>
            <tr><td>F5</td><td>Refresh page</td></tr>
            <tr><td>Alt+Left/Right</td><td>Back/Forward</td></tr>
        </table>

        <h2>Configuration</h2>
        <p>Configuration files are located at:</p>
        <ul>
            <li><code>~/.config/creature/config.ini</code> - Main configuration</li>
            <li><code>~/.config/creature/profile_&lt;name&gt;/</code> - Profile data</li>
        </ul>

        <h2>Available Documentation</h2>
        <p>For detailed information, see the documentation files:</p>
        <ul>
        """

        # Add links to available documentation files
        if docs_dir.exists():
            for doc_file in sorted(docs_dir.glob("*.md")):
                doc_name = doc_file.stem.replace("-", " ").title()
                help_content += f"<li>{doc_name} - <code>{doc_file.name}</code></li>\n"

        help_content += """
        </ul>

        <h2>Support</h2>
        <p>For issues and support:</p>
        <ul>
            <li>Check the documentation files in the <code>docs/</code> directory</li>
            <li>Review configuration options in <code>config.ini</code></li>
            <li>Ensure all dependencies are properly installed</li>
        </ul>

        <h2>License</h2>
        <p>Creature Browser is released under the <strong>MIT License</strong>.</p>
        """

        self.text_browser.setHtml(help_content)


class ProfileSelectionDialog(QDialog):
    """Dialog for selecting a browser profile."""

    def __init__(self, profile_manager, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.selected_profile = None

        self.setWindowTitle("Select Profile")
        self.setModal(True)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        # Label
        label = QLabel("Choose a profile for the new window:")
        layout.addWidget(label)

        # Profile list
        self.profile_list = QListWidget()
        profiles = self.profile_manager.list_profiles()

        for profile in profiles:
            item = QListWidgetItem(profile)
            self.profile_list.addItem(item)

        # Select first item by default
        if self.profile_list.count() > 0:
            self.profile_list.setCurrentRow(0)

        layout.addWidget(self.profile_list)

        # New profile section
        new_profile_layout = QHBoxLayout()
        self.new_profile_input = QLineEdit()
        self.new_profile_input.setPlaceholderText("Enter new profile name...")
        new_profile_btn = QPushButton("Create New")
        new_profile_btn.clicked.connect(self.create_new_profile)
        new_profile_layout.addWidget(self.new_profile_input)
        new_profile_layout.addWidget(new_profile_btn)
        layout.addLayout(new_profile_layout)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Connect double-click
        self.profile_list.itemDoubleClicked.connect(self.accept)

    def create_new_profile(self):
        """Create a new profile and add it to the list."""
        profile_name = self.new_profile_input.text().strip()
        if not profile_name:
            return

        # Add to list and select it
        item = QListWidgetItem(profile_name)
        self.profile_list.addItem(item)
        self.profile_list.setCurrentItem(item)
        self.new_profile_input.clear()

    def accept(self):
        """Set selected profile and close dialog."""
        current_item = self.profile_list.currentItem()
        if current_item:
            self.selected_profile = current_item.text()
        super().accept()


class BrowserTab(QWidget):
    def __init__(self, profile, url=None, profile_name=None, minimal_mode=False, history_manager=None):
        super().__init__()
        if url is None:
            url = creature_config.general.home_page
        self.profile = profile
        self.profile_name = profile_name or "default"
        self.minimal_mode = minimal_mode
        self.history_manager = history_manager
        layout = QVBoxLayout(self)

        # Navigation bar (skip in minimal mode)
        if not self.minimal_mode:
            nav_layout = QHBoxLayout()
            self.back_btn = QPushButton("←")
            self.forward_btn = QPushButton("→")
            self.refresh_btn = QPushButton("⟳")

            # Get theme colors for navigation buttons
            parent_browser = self.parent()
            while parent_browser and not hasattr(parent_browser, "theme_manager"):
                parent_browser = parent_browser.parent()

            if parent_browser and hasattr(parent_browser, "theme_manager"):
                current_theme = getattr(parent_browser, "current_theme", "light")
                theme = parent_browser.theme_manager.themes.get(current_theme, {})
                colors = theme.get("colors", {}) if theme else {}
            else:
                colors = {}

            # Style navigation buttons with theme colors
            nav_button_style = f"""
                QPushButton {{
                    border: 1px solid {colors.get("border_color", "#ccc")};
                    border-radius: 4px;
                    background-color: {colors.get("icon_button_bg", colors.get("button_bg", "transparent"))};
                    color: {colors.get("text_color", "#666")};
                    font-size: 18px;
                    padding: 2px 8px;
                    min-height: 28px;
                    min-width: 32px;
                }}
                QPushButton:hover {{
                    background-color: {colors.get("icon_button_hover_bg", colors.get("tab_hover_bg", "rgba(0, 0, 0, 0.1)"))};
                }}
                QPushButton:pressed {{
                    background-color: {colors.get("accent", "rgba(0, 0, 0, 0.2)")};
                }}
            """
            self.back_btn.setStyleSheet(nav_button_style)
            self.forward_btn.setStyleSheet(nav_button_style)
            self.refresh_btn.setStyleSheet(nav_button_style)

            # SSL indicator (make it a button to match other navigation buttons)
            self.ssl_indicator = QPushButton("🔓")
            self.ssl_indicator.setToolTip("Click for SSL certificate details")
            self.ssl_indicator.clicked.connect(self.show_certificate_details)
            # Get theme colors for consistent styling
            parent_browser = self.parent()
            while parent_browser and not hasattr(parent_browser, "theme_manager"):
                parent_browser = parent_browser.parent()

            if parent_browser and hasattr(parent_browser, "theme_manager"):
                current_theme = getattr(parent_browser, "current_theme", "light")
                theme = parent_browser.theme_manager.themes.get(current_theme, {})
                colors = theme.get("colors", {}) if theme else {}
            else:
                colors = {}

            self.ssl_indicator.setStyleSheet(f"""
                QPushButton {{
                    border: 1px solid {colors.get("border_color", "#ccc")};
                    border-radius: 4px;
                    background-color: {colors.get("icon_button_bg", colors.get("button_bg", "transparent"))};
                    color: {colors.get("text_color", "#666")};
                    font-size: 18px;
                    padding: 2px 4px;
                    min-height: 28px;
                    min-width: 32px;
                }}
                QPushButton:hover {{
                    background-color: {colors.get("icon_button_hover_bg", colors.get("tab_hover_bg", "rgba(0, 0, 0, 0.1)"))};
                }}
            """)

            # Create URL bar with history autocomplete
            if self.history_manager:
                self.url_bar = HistoryURLLineEdit(self.history_manager, self)
                self.url_bar.navigationRequested.connect(self.navigate_to_url)
            else:
                self.url_bar = QLineEdit()
                self.url_bar.returnPressed.connect(self.navigate)

            nav_layout.addWidget(self.back_btn)
            nav_layout.addWidget(self.forward_btn)
            nav_layout.addWidget(self.refresh_btn)
            nav_layout.addWidget(self.ssl_indicator)
            nav_layout.addWidget(self.url_bar)
            layout.addLayout(nav_layout)

        # Web view with custom profile and KeePassXC support
        self.web_view = KeePassXCWebEngineView()

        # Create SSL-aware page with the profile
        self.ssl_page = SSLAwarePage(self.profile, self.web_view)
        self.web_view.setPage(self.ssl_page)

        # Initialize SSL status
        self.ssl_status = {"is_secure": False, "certificate_valid": True, "certificate_info": None, "errors": [], "revocation_checked": False, "revocation_status": None}

        # Create horizontal layout for bookmark toolbar and web view
        content_layout = QHBoxLayout()

        # Add bookmark toolbar on the left
        self.bookmark_toolbar = BookmarkToolbar(self.profile_name, self)
        content_layout.addWidget(self.bookmark_toolbar)

        # Add web view on the right
        content_layout.addWidget(self.web_view)

        # Add the content layout to the main layout
        layout.addLayout(content_layout)

        # Connect signals (only if navigation elements exist)
        if not self.minimal_mode:
            self.back_btn.clicked.connect(self.web_view.back)
            self.forward_btn.clicked.connect(self.web_view.forward)
            self.refresh_btn.clicked.connect(self.web_view.reload)
            # URL bar signals are already connected in constructor
        self.web_view.urlChanged.connect(self.on_url_changed)

        # Connect page load finished signal for history recording
        self.web_view.loadFinished.connect(self.on_load_finished)

        # Connect SSL status signals
        self.ssl_page.sslStatusChanged.connect(self.on_ssl_status_changed)

        # Load initial page
        self.web_view.load(QUrl(url))

        # Set up keyboard shortcuts
        self.setup_shortcuts()

    def refresh_navigation_theme(self):
        """Refresh the theme styling for navigation buttons."""
        if self.minimal_mode:
            return  # No navigation buttons in minimal mode

        # Get theme colors
        parent_browser = self.parent()
        while parent_browser and not hasattr(parent_browser, "theme_manager"):
            parent_browser = parent_browser.parent()

        if parent_browser and hasattr(parent_browser, "theme_manager"):
            current_theme = getattr(parent_browser, "current_theme", "light")
            theme = parent_browser.theme_manager.themes.get(current_theme, {})
            colors = theme.get("colors", {}) if theme else {}
        else:
            colors = {}

        # Update navigation button styles
        nav_button_style = f"""
            QPushButton {{
                border: 1px solid {colors.get("border_color", "#ccc")};
                border-radius: 4px;
                background-color: {colors.get("icon_button_bg", colors.get("button_bg", "transparent"))};
                color: {colors.get("text_color", "#666")};
                font-size: 18px;
                padding: 2px 8px;
                min-height: 28px;
                min-width: 32px;
            }}
            QPushButton:hover {{
                background-color: {colors.get("icon_button_hover_bg", colors.get("tab_hover_bg", "rgba(0, 0, 0, 0.1)"))};
            }}
            QPushButton:pressed {{
                background-color: {colors.get("accent", "rgba(0, 0, 0, 0.2)")};
            }}
        """

        if hasattr(self, "back_btn"):
            self.back_btn.setStyleSheet(nav_button_style)
        if hasattr(self, "forward_btn"):
            self.forward_btn.setStyleSheet(nav_button_style)
        if hasattr(self, "refresh_btn"):
            self.refresh_btn.setStyleSheet(nav_button_style)

        # Update SSL indicator style
        if hasattr(self, "ssl_indicator"):
            self.ssl_indicator.setStyleSheet(f"""
                QPushButton {{
                    border: 1px solid {colors.get("border_color", "#ccc")};
                    border-radius: 4px;
                    background-color: {colors.get("icon_button_bg", colors.get("button_bg", "transparent"))};
                    color: {colors.get("text_color", "#666")};
                    font-size: 18px;
                    padding: 2px 4px;
                    min-height: 28px;
                    min-width: 32px;
                }}
                QPushButton:hover {{
                    background-color: {colors.get("icon_button_hover_bg", colors.get("tab_hover_bg", "rgba(0, 0, 0, 0.1)"))};
                }}
            """)
            # Update SSL indicator based on current status after styling
            self.update_ssl_indicator()

        # Update URL bar theme if it's a HistoryURLLineEdit
        if hasattr(self, "url_bar") and hasattr(self.url_bar, "refresh_theme"):
            self.url_bar.refresh_theme()

    def navigate(self):
        if self.minimal_mode:
            return  # No navigation in minimal mode
        user_input = self.url_bar.text().strip()
        if not user_input:
            return

        final_url, is_search = process_url_or_search(user_input)
        self.navigate_to(final_url)

    def navigate_to(self, url):
        """Navigate to a specific URL (should already be processed)."""
        self.web_view.load(QUrl(url))

    def navigate_to_url(self, user_input):
        """Navigate to URL from history autocomplete or manual input."""
        if not user_input:
            return

        final_url, is_search = process_url_or_search(user_input)
        self.navigate_to(final_url)

    def navigate_home(self):
        """Navigate to the home page."""
        home_url = creature_config.general.home_page
        self.navigate_to(home_url)

    def reload_bypass_cache(self):
        """Reload the current page bypassing cache (equivalent to Ctrl+F5)."""
        self.web_view.page().triggerAction(QWebEnginePage.WebAction.ReloadAndBypassCache)

    def exit_browser(self):
        """Exit the browser application."""
        # Find the parent browser window and close it
        parent_browser = self.parent()
        while parent_browser and not isinstance(parent_browser, QMainWindow):
            parent_browser = parent_browser.parent()

        if parent_browser:
            parent_browser.close()
        else:
            # Fallback: quit the application
            from PyQt6.QtWidgets import QApplication

            QApplication.instance().quit()

    def setup_shortcuts(self):
        """Set up keyboard shortcuts for this tab."""
        # Ctrl+G to focus URL bar
        focus_url_shortcut = QShortcut(QKeySequence("Ctrl+G"), self)
        focus_url_shortcut.activated.connect(self.focus_url_bar)

        # Alt+Home to navigate to home page
        home_shortcut = QShortcut(QKeySequence("Alt+Home"), self)
        home_shortcut.activated.connect(self.navigate_home)

        # F5 to reload page
        reload_shortcut = QShortcut(QKeySequence("F5"), self)
        reload_shortcut.activated.connect(self.web_view.reload)

        # Ctrl+F5 to reload page bypassing cache
        reload_bypass_cache_shortcut = QShortcut(QKeySequence("Ctrl+F5"), self)
        reload_bypass_cache_shortcut.activated.connect(self.reload_bypass_cache)

    def focus_url_bar(self):
        """Focus the URL bar and select all text, or show modal URL bar in minimal mode."""
        if self.minimal_mode:
            self.show_modal_url_bar()
        elif hasattr(self, "url_bar"):
            self.url_bar.setFocus()
            self.url_bar.selectAll()

    def show_modal_url_bar(self):
        """Show modal URL bar dialog for minimal mode."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("Navigate to URL")
        dialog.setModal(True)
        dialog.setFixedSize(600, 120)

        # Get current theme colors for dialog styling
        parent_browser = self.parent()
        while parent_browser and not hasattr(parent_browser, "theme_manager"):
            parent_browser = parent_browser.parent()

        if parent_browser and hasattr(parent_browser, "theme_manager"):
            current_theme = getattr(parent_browser, "current_theme", "light")
            theme = parent_browser.theme_manager.themes.get(current_theme, {})
            colors = theme.get("colors", {}) if theme else {}
        else:
            colors = {}

        # Apply theme to dialog
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.get("window_bg", "#ffffff")};
                color: {colors.get("text_color", "#000000")};
            }}
        """)

        # Center the dialog on the browser window
        parent_geometry = self.parent().geometry() if self.parent() else self.geometry()
        dialog.move(parent_geometry.x() + (parent_geometry.width() - dialog.width()) // 2, parent_geometry.y() + (parent_geometry.height() - dialog.height()) // 2)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        # Current URL label
        current_url = self.web_view.url().toString()
        current_label = QLabel(f"Current: {current_url}")
        current_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(current_label)

        # URL input with history autocomplete
        if self.history_manager:
            url_input = HistoryURLLineEdit(self.history_manager, dialog)
            url_input.setPlaceholderText("Enter URL or search term...")
            url_input.setText(current_url)  # Pre-fill with current URL
            url_input.selectAll()  # Select all text for easy replacement
        else:
            url_input = QLineEdit()
            url_input.setPlaceholderText("Enter URL or search term...")
            url_input.setText(current_url)  # Pre-fill with current URL
            url_input.selectAll()  # Select all text for easy replacement
        url_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px 12px;
                font-size: 14px;
                border: 2px solid {colors.get("accent", "#0078d4")};
                border-radius: 6px;
                background-color: {colors.get("url_bar_bg", "#ffffff")};
                color: {colors.get("text_color", "#000000")};
            }}
        """)
        layout.addWidget(url_input)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        go_btn = QPushButton("Go")
        go_btn.setDefault(True)  # Make this the default button for Enter key
        go_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors.get("accent", "#0078d4")};
                color: white;
                padding: 6px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors.get("tab_hover_bg", "#106ebe")};
            }}
        """)
        button_layout.addWidget(go_btn)

        layout.addLayout(button_layout)

        # Connect events
        def navigate_to_url():
            user_input = url_input.text().strip()
            if user_input:
                # Use the same URL processing as the regular navigation
                final_url, is_search = process_url_or_search(user_input)
                self.navigate_to(final_url)
            dialog.accept()

        go_btn.clicked.connect(navigate_to_url)
        url_input.returnPressed.connect(navigate_to_url)  # Enter key support

        # Connect navigation signal for HistoryURLLineEdit
        if hasattr(url_input, "navigationRequested"):

            def handle_autocomplete_navigation(url):
                self.navigate_to(url)
                dialog.accept()

            url_input.navigationRequested.connect(handle_autocomplete_navigation)

        # Show dialog and focus on input
        dialog.show()
        url_input.setFocus()

    def on_url_changed(self, url):
        """Handle URL changes to detect HTTPS vs HTTP and update SSL indicator."""
        # Update URL bar (if it exists)
        if not self.minimal_mode:
            self.url_bar.setText(url.toString())

        # Check if connection is secure
        is_secure = url.scheme().lower() == "https"
        self.ssl_status["is_secure"] = is_secure

        logger.debug(f"URL changed to: {url.toString()}, is_secure: {is_secure}")

        # Update SSL indicator for URL scheme changes
        self.update_ssl_indicator()

    def on_ssl_status_changed(self, ssl_info):
        """Handle SSL status changes from the SSL-aware page."""
        logger.debug(f"SSL status changed: {ssl_info}")
        self.ssl_status.update(ssl_info)
        self.update_ssl_indicator()

    def on_load_finished(self, success):
        """Handle page load completion for history recording."""
        if not success or not self.history_manager:
            return

        try:
            url = self.web_view.url().toString()
            title = self.web_view.title()

            # Skip internal URLs and invalid URLs
            if not url or url.startswith("about:") or url.startswith("data:"):
                return

            # Record the visit in history
            self.history_manager.record_visit(url, title)
            logger.debug(f"Recorded history visit: {url[:50]}{'...' if len(url) > 50 else ''}")

        except Exception as e:
            logger.error(f"Failed to record history visit: {e}")

    def update_ssl_indicator(self):
        """Update SSL indicator based on current status."""
        if self.minimal_mode:
            return  # No SSL indicator in minimal mode

        if self.ssl_status["is_secure"]:
            if self.ssl_status["certificate_valid"]:
                self.ssl_indicator.setText("🔒")
                self.ssl_indicator.setStyleSheet("""
                    QPushButton {
                        border: 1px solid #4CAF50;
                        border-radius: 4px;
                        background-color: #E8F5E8;
                        font-size: 18px;
                        color: #4CAF50;
                        padding: 2px 4px;
                        min-height: 28px;
                        min-width: 32px;
                    }
                    QPushButton:hover {
                        background-color: #C8E6C9;
                    }
                """)
                self.ssl_indicator.setToolTip("Secure HTTPS connection - Click for certificate details")
            else:
                self.ssl_indicator.setText("⚠️")
                self.ssl_indicator.setStyleSheet("""
                    QPushButton {
                        border: 1px solid #FF9800;
                        border-radius: 4px;
                        background-color: #FFF3E0;
                        font-size: 18px;
                        color: #FF9800;
                        padding: 2px 4px;
                        min-height: 28px;
                        min-width: 32px;
                    }
                    QPushButton:hover {
                        background-color: #FFE0B2;
                    }
                """)
                self.ssl_indicator.setToolTip("HTTPS with certificate issues - Click for details")
        else:
            self.ssl_indicator.setText("🔓")
            self.ssl_indicator.setStyleSheet("""
                QPushButton {
                    border: 1px solid #F44336;
                    border-radius: 4px;
                    background-color: #FFEBEE;
                    font-size: 18px;
                    color: #F44336;
                    padding: 2px 4px;
                    min-height: 28px;
                    min-width: 32px;
                }
                QPushButton:hover {
                    background-color: #FFCDD2;
                }
            """)
            self.ssl_indicator.setToolTip("Insecure HTTP connection - Click for details")

    def show_certificate_details(self):
        """Show certificate details dialog when SSL indicator is clicked."""
        logger.debug(f"Current SSL status: {self.ssl_status}")
        dialog = CertificateDetailsDialog(self.ssl_status, self)
        dialog.exec()

    def __del__(self):
        """Cleanup BrowserTab to prevent memory leaks."""
        try:
            # Disconnect SSL page signals
            if hasattr(self, "ssl_page"):
                self.ssl_page.sslStatusChanged.disconnect()
                # Clear page reference before deletion
                self.ssl_page = None

            # Clear web view page
            if hasattr(self, "web_view") and self.web_view:
                self.web_view.setPage(None)

            logger.debug(f"BrowserTab cleanup completed for profile: {self.profile_name}")
        except Exception as e:
            logger.debug(f"BrowserTab cleanup error (normal during shutdown): {e}")


class CreatureBrowser(QMainWindow):
    def __init__(self, profile_name=None, force_new_window=None, theme=None, minimal_mode=False, session_name=None):
        super().__init__()

        # Use config values if not overridden by arguments
        self.force_new_window = force_new_window if force_new_window is not None else creature_config.general.force_new_window
        self.minimal_mode = minimal_mode
        self.profile_name = profile_name or creature_config.general.default_profile
        self.session_name = session_name

        # Get profile-specific theme if configured
        profile_theme = ""
        if hasattr(creature_config, "profiles") and self.profile_name in creature_config.profiles:
            profile_config = creature_config.profiles[self.profile_name]
            profile_theme = profile_config.get("theme", "")

        # Use profile theme, then command line theme, then general theme
        theme = theme or profile_theme or creature_config.general.theme
        self.current_theme = theme

        # Set up profile
        profile_dir = creature_config.general.profile_directory
        if not profile_dir.startswith("/"):
            profile_dir = Path.home() / profile_dir
        self.profile_manager = ProfileManager(profile_dir)
        self.profile = self.profile_manager.create_profile(self.profile_name)

        # Initialize session manager for this profile
        self.browser_session_manager = BrowserSessionManager(self)

        # Initialize history manager for this profile
        self.history_manager = HistoryManager(self.profile_name, self.profile_manager.base_dir)

        # Configure history manager with settings
        if hasattr(creature_config, "history"):
            history_config = {
                "enabled": creature_config.history.enabled,
                "retention_days": creature_config.history.retention_days,
                "max_entries": creature_config.history.max_entries,
                "autocomplete_max_results": creature_config.history.autocomplete_max_results,
                "cleanup_interval_minutes": creature_config.history.cleanup_interval_minutes,
                "ordering": creature_config.history.ordering,
            }
            self.history_manager.update_config(history_config)

        # Get profile-specific title suffix
        title_suffix = ""
        if hasattr(creature_config, "profiles") and self.profile_name in creature_config.profiles:
            profile_config = creature_config.profiles[self.profile_name]
            title_suffix = profile_config.get("title_suffix", "")

        # Build window title
        if title_suffix:
            self.setWindowTitle(f"Creature Browser - {self.profile_name} ({title_suffix})")
        else:
            self.setWindowTitle(f"Creature Browser - {self.profile_name}")

        # Set application icon
        logo_path = Path(__file__).parent / "img" / "icon.png"
        print("logo", logo_path)
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        self.setGeometry(creature_config.window.x, creature_config.window.y, creature_config.window.width, creature_config.window.height)

        # Apply theme
        self.theme_manager = ThemeManager()

        if self.minimal_mode:
            # Minimal mode: single tab, no navigation bar, no menu
            self.single_tab = BrowserTab(self.profile, profile_name=self.profile_name, minimal_mode=True, history_manager=self.history_manager)
            self.setCentralWidget(self.single_tab)
        elif not self.force_new_window:
            # Tab widget for normal mode
            self.tabs = QTabWidget()
            self.tabs.setTabsClosable(True)
            self.tabs.tabCloseRequested.connect(self.close_tab)
            self.setCentralWidget(self.tabs)

            # Initial tab will be added by main() with proper URL

            # Set up tab cycling shortcuts
            self.setup_tab_shortcuts()
        else:
            # Single tab mode for window manager
            self.single_tab = BrowserTab(self.profile, profile_name=self.profile_name, history_manager=self.history_manager)
            self.setCentralWidget(self.single_tab)

        # Set up hamburger menu (replaces traditional menu bar) - skip in minimal mode
        if not self.minimal_mode:
            self.setup_hamburger_menu()

    def setup_hamburger_menu(self):
        """Set up hamburger menu button in tab bar (replaces traditional menu bar)."""
        from PyQt6.QtWidgets import QPushButton
        from PyQt6.QtGui import QIcon
        from PyQt6.QtCore import Qt
        from pathlib import Path

        # Create hamburger menu button
        self.hamburger_button = QPushButton(self)

        # Load logo.png as the button icon
        logo_path = Path(__file__).parent / "img" / "icon.png"
        if logo_path.exists():
            icon = QIcon(str(logo_path))
            self.hamburger_button.setIcon(icon)
            # Let Qt handle scaling by setting the desired icon size
            self.hamburger_button.setIconSize(QSize(32, 32))
        else:
            # Fallback to text if logo not found
            self.hamburger_button.setText("☰")

        self.hamburger_button.setFixedSize(40, 36)
        self.hamburger_button.setToolTip("Menu")
        self.hamburger_button.clicked.connect(self.show_hamburger_menu)

        # Remove border and background styling with minimal padding
        self.hamburger_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                padding: 2px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)

        # Create close window button
        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(32, 32)
        self.close_button.setToolTip("Close Window")
        self.close_button.clicked.connect(self.close)

        # Style the close button similar to hamburger button
        self.close_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                padding: 2px;
                font-size: 16px;
                font-weight: bold;
                color: #999;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 0.2);
                border-radius: 3px;
                color: #fff;
            }
            QPushButton:pressed {
                background-color: rgba(255, 0, 0, 0.3);
            }
        """)

        if not self.force_new_window and hasattr(self, "tabs"):
            # Create a container widget for both buttons
            from PyQt6.QtWidgets import QWidget, QHBoxLayout
            from PyQt6.QtCore import Qt

            button_container = QWidget()
            layout = QHBoxLayout(button_container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.addWidget(self.hamburger_button)
            layout.addWidget(self.close_button)

            # Add button container to tab bar corner (right side)
            self.tabs.setCornerWidget(button_container, Qt.Corner.TopRightCorner)
        else:
            # For single tab mode, create a minimal toolbar with hamburger and close buttons
            from PyQt6.QtWidgets import QToolBar, QWidget
            from PyQt6.QtCore import Qt

            toolbar = QToolBar(self)
            toolbar.setMovable(False)
            toolbar.setFloatable(False)

            # Add spacer to push buttons to the right
            spacer = QWidget()
            spacer.setSizePolicy(spacer.sizePolicy().Expanding, spacer.sizePolicy().Expanding)
            toolbar.addWidget(spacer)
            toolbar.addWidget(self.hamburger_button)
            toolbar.addWidget(self.close_button)

            # Add toolbar to top
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # Hide the traditional menu bar to save vertical space
        self.menuBar().setVisible(False)
        
        # Create global actions that work across all widgets
        self._create_global_actions()

    def _create_global_actions(self):
        """Create global actions that work across all widgets in the application."""
        # Quit action - global application-wide
        self.quit_action = QAction("Quit", self)
        self.quit_action.setShortcut("Ctrl+Q")
        self.quit_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.quit_action.triggered.connect(self.quit_application)
        self.addAction(self.quit_action)
        
        # Close tab action - only if tabs are supported
        if not self.force_new_window and not self.minimal_mode:
            self.close_tab_action = QAction("Close Tab", self)
            self.close_tab_action.setShortcut("Ctrl+W")
            self.close_tab_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.close_tab_action.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()) if hasattr(self, "tabs") else None)
            self.addAction(self.close_tab_action)
            
            # New tab action
            self.new_tab_action = QAction("New Tab", self)
            self.new_tab_action.setShortcut("Ctrl+T")
            self.new_tab_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.new_tab_action.triggered.connect(self.add_new_tab)
            self.addAction(self.new_tab_action)
        
        # New window action
        self.new_window_action = QAction("New Window", self)
        self.new_window_action.setShortcut("Ctrl+N")
        self.new_window_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.new_window_action.triggered.connect(self.new_window)
        self.addAction(self.new_window_action)
        
        # History action
        self.history_action = QAction("Browsing History...", self)
        self.history_action.setShortcut("Ctrl+H")
        self.history_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.history_action.triggered.connect(self.open_history_editor)
        self.addAction(self.history_action)
        
        # Session actions (only in normal mode)
        if not self.force_new_window:
            # Save session
            self.save_session_action = QAction("Save Current Session...", self)
            self.save_session_action.setShortcut("Ctrl+Shift+S")
            self.save_session_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.save_session_action.triggered.connect(self.save_current_session_dialog)
            self.addAction(self.save_session_action)
            
            # Manage sessions
            self.manage_sessions_action = QAction("Manage Sessions...", self)
            self.manage_sessions_action.setShortcut("Ctrl+Shift+O")
            self.manage_sessions_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.manage_sessions_action.triggered.connect(self.show_session_manager_dialog)
            self.addAction(self.manage_sessions_action)
            
            # Load last session
            self.load_last_session_action = QAction("Load Last Session", self)
            self.load_last_session_action.setShortcut("Ctrl+Shift+L")
            self.load_last_session_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.load_last_session_action.triggered.connect(lambda: self.load_session_by_name("last") if self.browser_session_manager.has_last_session() else None)
            self.addAction(self.load_last_session_action)
        
        # Help action
        self.help_action = QAction("Help...", self)
        self.help_action.setShortcut("F1")
        self.help_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.help_action.triggered.connect(self.show_help)
        self.addAction(self.help_action)
    
    def show_hamburger_menu(self):
        """Show the hamburger menu with all menu options."""

        menu = QMenu(self)

        # File section
        if not self.force_new_window:
            menu.addAction(self.new_tab_action)
            menu.addSeparator()

        menu.addAction(self.new_window_action)

        # Sessions section - only in normal mode (not minimal mode)
        if not self.force_new_window:
            sessions_submenu = menu.addMenu("Sessions")

            # Save current session
            sessions_submenu.addAction(self.save_session_action)

            sessions_submenu.addSeparator()

            # Load session submenu
            available_sessions = self.browser_session_manager.get_available_sessions()
            if available_sessions:
                for session_name in available_sessions:
                    display_name = f"{session_name} (auto-saved)" if session_name == "last" else session_name
                    load_action = QAction(f"Load '{display_name}'", self)
                    load_action.triggered.connect(lambda checked, name=session_name: self.load_session_by_name(name))
                    sessions_submenu.addAction(load_action)

                sessions_submenu.addSeparator()

            # Manage sessions
            sessions_submenu.addAction(self.manage_sessions_action)

        menu.addSeparator()

        # History section
        menu.addAction(self.history_action)

        menu.addSeparator()

        # Profile section
        profile_info_action = QAction(f"Profile: {self.profile_name.capitalize()} - Info", self)
        profile_info_action.triggered.connect(self.show_profile_info)
        menu.addAction(profile_info_action)

        menu.addSeparator()

        # Theme section
        theme_submenu = menu.addMenu("Themes")
        for theme_name in self.theme_manager.themes.keys():
            theme_action = QAction(theme_name.capitalize(), self)
            theme_action.setCheckable(True)
            theme_action.setChecked(theme_name == self.current_theme)
            theme_action.triggered.connect(lambda checked, t=theme_name: self.change_theme(t))
            theme_submenu.addAction(theme_action)

        menu.addSeparator()

        # Help section
        menu.addAction(self.help_action)

        about_action = QAction("About Creature Browser", self)
        about_action.triggered.connect(self.show_about)
        menu.addAction(about_action)

        menu.addSeparator()

        # Quit action at bottom
        menu.addAction(self.quit_action)

        # Show menu below the hamburger button
        button_pos = self.hamburger_button.mapToGlobal(self.hamburger_button.rect().bottomLeft())
        menu.popup(button_pos)

    def add_new_tab(self, url=None):
        if url is None or isinstance(url, bool):
            url = creature_config.general.home_page

        if self.force_new_window:
            self.new_window(url)
            return

        tab = BrowserTab(self.profile, url, profile_name=self.profile_name, history_manager=self.history_manager)
        index = self.tabs.addTab(tab, "New Tab")
        self.tabs.setCurrentIndex(index)

        # Apply current theme to the new tab
        if hasattr(tab, "bookmark_toolbar"):
            tab.bookmark_toolbar.refresh_theme()
        if hasattr(tab, "refresh_navigation_theme"):
            tab.refresh_navigation_theme()

        # Update tab title when page title changes
        tab.web_view.titleChanged.connect(lambda title, idx=index: self.update_tab_title(idx, title))

        # Update tab favicon when page icon changes (if enabled)
        if creature_config.browser.show_tab_favicons:
            tab.web_view.iconChanged.connect(lambda icon, idx=index: self.update_tab_icon(idx, icon))

    def update_tab_title(self, index, title):
        try:
            if hasattr(self, "tabs") and self.tabs and index < self.tabs.count():
                short_title = title[:20] + "..." if len(title) > 20 else title
                self.tabs.setTabText(index, short_title)
        except (RuntimeError, AttributeError) as e:
            # Widget has been deleted or is being destroyed - ignore
            logger.debug(f"Tab title update skipped (widget deleted): {e}")
            pass

    def update_tab_icon(self, index, icon):
        try:
            if hasattr(self, "tabs") and self.tabs and index < self.tabs.count():
                # Set the favicon for the tab
                self.tabs.setTabIcon(index, icon)
        except (RuntimeError, AttributeError) as e:
            # Widget has been deleted or is being destroyed - ignore
            logger.debug(f"Tab icon update skipped (widget deleted): {e}")
            pass

    def close_tab(self, index):
        if hasattr(self, "tabs"):
            try:
                # Get the tab widget before removing it
                tab_widget = self.tabs.widget(index)
                if tab_widget and hasattr(tab_widget, "web_view"):
                    # Disconnect signals to prevent late updates
                    tab_widget.web_view.titleChanged.disconnect()
                    if creature_config.browser.show_tab_favicons:
                        tab_widget.web_view.iconChanged.disconnect()

                if self.tabs.count() > 1:
                    self.tabs.removeTab(index)
                else:
                    if creature_config.browser.tab_close_behavior == "close_window":
                        self.close()
                    else:
                        # Keep window open with last tab
                        pass
            except (RuntimeError, AttributeError) as e:
                logger.debug(f"Tab close error (normal during shutdown): {e}")
                pass

    def new_window(self, url=None):
        if url is None or isinstance(url, bool):
            url = creature_config.general.home_page

        # Create new window with same profile
        new_browser = CreatureBrowser(self.profile_name, self.force_new_window)
        new_browser.show()

        if hasattr(new_browser, "single_tab"):
            new_browser.single_tab.navigate_to(url)
        else:
            new_browser.add_new_tab(url)

    def show_profile_info(self):
        profile_path = self.profile_manager.get_profile_path(self.profile_name)

        msg = QMessageBox()
        msg.setWindowTitle("Profile Information")
        msg.setText(f"Profile: {self.profile_name}\nPath: {profile_path}")
        msg.exec()

    def quit_application(self):
        """Quit the application gracefully."""
        # Get the QApplication instance
        app = QApplication.instance()
        if app:
            # Close all windows
            app.closeAllWindows()
            # Quit the application
            app.quit()

    def change_theme(self, theme_name):
        app = QApplication.instance()
        self.theme_manager.apply_theme(app, theme_name)
        self.current_theme = theme_name

        # Refresh bookmark toolbar theme if it exists
        if hasattr(self, "single_tab") and hasattr(self.single_tab, "bookmark_toolbar"):
            self.single_tab.bookmark_toolbar.refresh_theme()
            self.single_tab.refresh_navigation_theme()
        elif hasattr(self, "tabs"):
            # Refresh theme for all tabs
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                if hasattr(tab, "bookmark_toolbar"):
                    tab.bookmark_toolbar.refresh_theme()
                if hasattr(tab, "refresh_navigation_theme"):
                    tab.refresh_navigation_theme()

        # Theme menu checkmarks are now handled dynamically in show_hamburger_menu()

    def show_help(self):
        """Show help dialog."""
        help_dialog = HelpDialog(self)
        help_dialog.exec()

    def show_about(self):
        """Show about dialog."""
        about_dialog = AboutDialog(self)
        about_dialog.exec()

    def setup_tab_shortcuts(self):
        """Set up keyboard shortcuts for tab cycling.
        
        Note: Most shortcuts are now defined as global QActions in _create_global_actions().
        This function only sets up tab navigation shortcuts that aren't global actions.
        """
        if not hasattr(self, "tabs"):
            return

        # Ctrl+Shift+Right - Next tab
        next_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Right"), self)
        next_tab_shortcut.activated.connect(self.next_tab)

        # Ctrl+Shift+Left - Previous tab
        prev_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Left"), self)
        prev_tab_shortcut.activated.connect(self.previous_tab)

    def next_tab(self):
        """Switch to the next tab."""
        if not hasattr(self, "tabs") or self.tabs.count() <= 1:
            return

        current_index = self.tabs.currentIndex()
        next_index = (current_index + 1) % self.tabs.count()
        self.tabs.setCurrentIndex(next_index)

    def previous_tab(self):
        """Switch to the previous tab."""
        if not hasattr(self, "tabs") or self.tabs.count() <= 1:
            return

        current_index = self.tabs.currentIndex()
        prev_index = (current_index - 1) % self.tabs.count()
        self.tabs.setCurrentIndex(prev_index)

    def closeEvent(self, event):
        """Handle window close event - auto-save session before closing."""
        try:
            # Auto-save current session as "last"
            self.browser_session_manager.save_last_session()
            logger.debug("Auto-saved session before closing")
        except Exception as e:
            logger.error(f"Failed to auto-save session on close: {e}")

        try:
            # Shutdown history manager
            if hasattr(self, "history_manager"):
                self.history_manager.shutdown()
                logger.debug("History manager shutdown completed")
        except Exception as e:
            logger.error(f"Failed to shutdown history manager: {e}")

        # Continue with normal close
        super().closeEvent(event)

    def __del__(self):
        """Cleanup CreatureBrowser to prevent race conditions during shutdown."""
        try:
            # Disconnect all tab title change signals
            if hasattr(self, "tabs") and self.tabs:
                for i in range(self.tabs.count()):
                    tab_widget = self.tabs.widget(i)
                    if tab_widget and hasattr(tab_widget, "web_view"):
                        try:
                            tab_widget.web_view.titleChanged.disconnect()
                        except (RuntimeError, TypeError):
                            pass

            logger.debug("CreatureBrowser cleanup completed")
        except Exception as e:
            logger.debug(f"CreatureBrowser cleanup error (normal during shutdown): {e}")

    def load_session_by_name(self, session_name: str) -> bool:
        """Load a session by name - delegates to session manager."""
        return self.browser_session_manager.load_session_by_name(session_name)

    def save_current_session_dialog(self):
        """Show dialog to save current session."""
        from creature.ui.session_dialogs import SaveSessionDialog

        dialog = SaveSessionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            session_name = dialog.get_session_name()
            if session_name:
                self.browser_session_manager.save_current_session(session_name)

    def show_session_manager_dialog(self):
        """Show the session management dialog."""
        from creature.ui.session_dialogs import SessionManagerDialog

        dialog = SessionManagerDialog(self.browser_session_manager, self)
        dialog.exec()

    def open_history_editor(self):
        """Open the history editor in a new tab."""
        if self.minimal_mode or self.force_new_window:
            # In minimal mode or force new window mode, show as dialog
            self._show_history_editor_dialog()
            return

        # Create history editor widget
        history_editor = HistoryEditorWidget(self.history_manager, self)

        # Connect navigation signal to open URLs in new tabs
        history_editor.navigationRequested.connect(self.add_new_tab)

        # Add as tab
        if hasattr(self, "tabs"):
            index = self.tabs.addTab(history_editor, "History")
            self.tabs.setCurrentIndex(index)

            # Apply current theme
            history_editor.refresh_theme()

    def _show_history_editor_dialog(self):
        """Show history editor as a dialog for minimal/force new window modes."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("Browsing History")
        dialog.setModal(False)  # Allow interaction with main window
        dialog.resize(900, 600)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create history editor
        history_editor = HistoryEditorWidget(self.history_manager, dialog)

        # Connect navigation to close dialog and open URL
        def handle_navigation(url):
            dialog.accept()
            if hasattr(self, "single_tab"):
                self.single_tab.navigate_to(url)
            else:
                self.add_new_tab(url)

        history_editor.navigationRequested.connect(handle_navigation)
        layout.addWidget(history_editor)

        dialog.show()


def setup_wayland_compatibility():
    """Ensure Wayland compatibility and fix graphics issues"""
    # Detect if we're running on Wayland
    is_wayland = "WAYLAND_DISPLAY" in os.environ

    # Only set Wayland platform if explicitly on Wayland and not already set
    if is_wayland and "QT_QPA_PLATFORM" not in os.environ:
        # Try wayland first, fallback to xcb if wayland fails
        os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"

    # UI scaling configuration
    ui_config = creature_config.ui

    # Enable high DPI scaling if configured
    if ui_config.enable_high_dpi_scaling:
        os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    # Set scale factor if specified
    if ui_config.scale_factor != 1.0:
        os.environ.setdefault("QT_SCALE_FACTOR", str(ui_config.scale_factor))

    # Force specific DPI if configured
    if ui_config.force_dpi > 0:
        os.environ.setdefault("QT_FONT_DPI", str(ui_config.force_dpi))

    # Enable Wayland-specific features from config (only if on Wayland)
    if is_wayland:
        os.environ.setdefault("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1" if creature_config.wayland.disable_window_decoration else "0")

    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1" if creature_config.wayland.auto_screen_scale_factor else "0")

    # Fix graphics rendering issues
    chromium_flags = []
    if creature_config.wayland.disable_gpu_sandbox:
        chromium_flags.append("--disable-gpu-sandbox")
    if creature_config.wayland.disable_software_rasterizer:
        chromium_flags.append("--disable-software-rasterizer")
    if creature_config.wayland.enable_vaapi_video_decoder:
        chromium_flags.append("--enable-features=VaapiVideoDecoder")

    # Graphics acceleration and WebGL fixes - more conservative for media stability
    if creature_config.wayland.disable_hardware_acceleration:
        # Complete hardware acceleration disable for maximum stability
        chromium_flags.extend(["--disable-gpu", "--disable-gpu-compositing", "--disable-accelerated-2d-canvas", "--disable-accelerated-video-decode", "--disable-gpu-rasterization", "--disable-features=VizDisplayCompositor"])
    else:
        # Partial acceleration with media stability focus
        chromium_flags.extend(
            [
                "--ignore-gpu-blocklist",
                "--disable-gpu-rasterization",  # Disable GPU raster to avoid conflicts with media
                "--enable-webgl",
                "--disable-accelerated-2d-canvas",  # Disable 2D canvas acceleration to prevent black screens
                "--disable-gpu-compositing",  # Prevent GPU compositing issues during media device changes
                "--disable-features=VizDisplayCompositor",  # Use software compositor for stability
            ]
        )

    # Only add Wayland-specific Chromium flags if we're actually on Wayland
    if is_wayland and ui_config.enable_high_dpi_scaling:
        # Use more conservative approach - don't force ozone platform
        chromium_flags.append("--enable-features=UseOzonePlatform")
        # Let Chromium auto-detect the platform instead of forcing wayland

    # Add general compatibility flags
    chromium_flags.append("--no-sandbox")  # Often needed for Chromium
    chromium_flags.append("--disable-dev-shm-usage")  # Helps with shared memory issues

    # Media stability flags to prevent black screen during device changes
    chromium_flags.extend(
        [
            "--disable-background-media-suspend",  # Prevent media suspension
            "--disable-renderer-backgrounding",  # Keep renderer active
            "--disable-backgrounding-occluded-windows",  # Prevent window backgrounding
            "--disable-ipc-flooding-protection",  # Prevent IPC issues during media changes
            "--enable-experimental-web-platform-features",  # Enable latest WebRTC features
            "--allow-running-insecure-content",  # Allow mixed content for media
            "--enable-features=NetworkService,CookiesWithoutSameSiteMustBeSecure",  # Enable modern network and cookies
            "--enable-javascript-harmony",  # Enable modern JavaScript features
            "--enable-blink-features=WebAssembly",  # Enable WebAssembly for complex apps
            "--disable-blink-features=BlockCredentialedSubresources",  # Allow credentialed requests
            "--disable-site-isolation-trials",  # Allow cross-site cookies for Google auth
            "--enable-dom-distiller",  # Enable content processing
        ]
    )

    if chromium_flags:
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", " ".join(chromium_flags))

    # Additional Chromium flags for better compatibility
    if creature_config.wayland.disable_sandbox:
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")


def main():
    parser = argparse.ArgumentParser(description="Creature Browser with Profile Support")
    parser.add_argument("--profile", "-p", default=None, help="Profile name for sandboxing (default: from config)")
    parser.add_argument("--theme", "-t", default=None, choices=["light", "dark", "nord", "slate", "earthy", "violet", "forest", "autumn"], help="Theme to use (default: from config)")
    parser.add_argument("url", nargs="?", default=None, help="URL to open (optional)")
    parser.add_argument("--profile-dir", default=None, help="Custom directory for profiles")
    parser.add_argument("--config", "-c", default=None, help="Path to configuration file")
    parser.add_argument("--no-profile-prompt", action="store_true", help="Don't prompt for profile selection")
    parser.add_argument("--minimal", "-m", action="store_true", help="Minimal mode: no tabs, no menu, no navigation bar")
    parser.add_argument("--session", "-s", default=None, help="Load a saved session by name")

    args = parser.parse_args()

    # Set config path if provided
    if args.config:
        os.environ["CREATURE_CONFIG"] = args.config

    # Setup Wayland compatibility and fix graphics issues
    setup_wayland_compatibility()

    app = QApplication(sys.argv)

    # Set application icon
    logo_path = get_data_path("icons/logo.png")
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    # Show splash screen if enabled
    splash = None
    if creature_config.general.show_splash_screen:
        splash = SplashScreen()
        splash.show()
        app.processEvents()  # Process events to show splash screen

        # Ensure splash screen shows for minimum 2 seconds
        import time

        start_time = time.time()
        while time.time() - start_time < 2.0:
            app.processEvents()
            time.sleep(0.05)  # Small sleep to prevent high CPU usage

    # Determine profile to use
    profile_name = args.profile

    # If URL provided and no profile specified, show profile selection dialog
    if args.url and not profile_name and not args.no_profile_prompt:
        profile_dir = creature_config.general.profile_directory
        if not profile_dir.startswith("/"):
            profile_dir = Path.home() / profile_dir
        profile_manager = ProfileManager(profile_dir)

        dialog = ProfileSelectionDialog(profile_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            profile_name = dialog.selected_profile
        else:
            # User cancelled
            sys.exit(0)

    # Use default profile if still not set
    if not profile_name:
        profile_name = creature_config.general.default_profile

    # Create browser with command line overrides
    browser = CreatureBrowser(profile_name=profile_name, force_new_window=None, theme=args.theme, minimal_mode=args.minimal, session_name=args.session)

    # Apply theme (browser already determined the correct theme based on profile)
    theme_manager = ThemeManager()
    theme_manager.apply_theme(app, browser.current_theme)

    # Refresh bookmark toolbar and navigation theme after initial theme application
    if hasattr(browser, "single_tab") and hasattr(browser.single_tab, "bookmark_toolbar"):
        browser.single_tab.bookmark_toolbar.refresh_theme()
        browser.single_tab.refresh_navigation_theme()
    elif hasattr(browser, "tabs"):
        for i in range(browser.tabs.count()):
            tab = browser.tabs.widget(i)
            if hasattr(tab, "bookmark_toolbar"):
                tab.bookmark_toolbar.refresh_theme()
            if hasattr(tab, "refresh_navigation_theme"):
                tab.refresh_navigation_theme()

    browser.show()

    # Close splash screen after browser is shown
    if splash:
        splash.finish(browser)

    # Load initial content - either a session or a single URL
    if args.session:
        # Load the specified session
        browser.load_session_by_name(args.session)
    else:
        # Load initial URL as normal
        initial_url = args.url or creature_config.general.home_page
        if hasattr(browser, "single_tab"):
            browser.single_tab.navigate_to(initial_url)
        else:
            browser.add_new_tab(initial_url)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
