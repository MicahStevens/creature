#!/usr/bin/env python3
import sys
import os
import argparse
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                            QWidget, QLineEdit, QPushButton, QHBoxLayout,
                            QTabWidget, QToolBar, QStyleFactory, QMessageBox,
                            QDialog, QListWidget, QDialogButtonBox, QLabel,
                            QListWidgetItem)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
from PyQt6.QtCore import QUrl, QStandardPaths, QDir
from PyQt6.QtGui import QAction, QPalette, QColor, QShortcut, QKeySequence, QFont, QFontDatabase
import json
import re
import urllib.parse
from creature_config import config as creature_config
from configobj import ConfigObj
from validate import Validator

def process_url_or_search(input_text):
    """Process user input to determine if it's a URL or search query.
    
    Args:
        input_text: User input from URL bar
        
    Returns:
        tuple: (url, is_search) where url is the final URL and is_search indicates if it's a search
    """
    if not input_text or not input_text.strip():
        return creature_config.general.home_page, False
    
    input_text = input_text.strip()
    
    # Check if it's already a complete URL with protocol
    if re.match(r'^https?://', input_text):
        return input_text, False
    
    # Check if it looks like a URL (has dot and no spaces, or is localhost/IP)
    url_patterns = [
        r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$',  # domain.com/path
        r'^localhost(:[0-9]+)?(/.*)?$',           # localhost:port/path
        r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(:[0-9]+)?(/.*)?$',  # IP:port/path
        r'^[a-zA-Z0-9.-]+(:[0-9]+)(/.*)?$',       # hostname:port/path (local network)
    ]
    
    for pattern in url_patterns:
        if re.match(pattern, input_text):
            # Add https:// prefix for proper URLs
            return f"https://{input_text}", False
    
    # Check if it starts with http/https but isn't complete (support local DNS)
    if input_text.startswith(('http://', 'https://')):
        return input_text, False
    
    # Otherwise, treat as search query
    search_engine = creature_config.search.default_engine
    search_url_template = getattr(creature_config.search, search_engine)
    search_url = search_url_template.replace('%s', urllib.parse.quote_plus(input_text))
    
    return search_url, True

class ProfileManager:
    def __init__(self, base_dir=None):
        if base_dir is None:
            self.base_dir = Path.home() / ".config" / "creature"
        else:
            self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_profile_path(self, profile_name):
        profile_path = self.base_dir / f"profile_{profile_name}"
        profile_path.mkdir(exist_ok=True)
        return str(profile_path)
    
    def list_profiles(self):
        """List all existing profiles."""
        profiles = []
        for item in self.base_dir.iterdir():
            if item.is_dir() and item.name.startswith("profile_"):
                profile_name = item.name.replace("profile_", "")
                profiles.append(profile_name)
        return sorted(profiles) if profiles else ["default"]

    def create_profile(self, profile_name):
        profile_path = self.get_profile_path(profile_name)

        # Create profile with unique name
        profile = QWebEngineProfile(f"profile_{profile_name}")
        profile.setPersistentStoragePath(profile_path)
        profile.setCachePath(profile_path + "/cache")

        # Enable features from config
        settings = profile.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, 
                            creature_config.browser.javascript_enabled)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, 
                            creature_config.browser.local_storage_enabled)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, 
                            creature_config.browser.plugins_enabled)

        return profile

class ThemeManager:
    def __init__(self):
        self.themes_dir = Path(__file__).parent / "themes"
        self.theme_spec = self.themes_dir / "theme.spec"
        self.themes = {}
        self.load_themes()
    
    def load_themes(self):
        """Load all theme files from the themes directory."""
        if not self.themes_dir.exists():
            return
        
        for theme_file in self.themes_dir.glob("*.ini"):
            if theme_file.name == "theme.spec":
                continue
            
            try:
                # Load theme with validation
                theme_config = ConfigObj(str(theme_file), configspec=str(self.theme_spec))
                validator = Validator()
                theme_config.validate(validator, copy=True)
                
                theme_name = theme_file.stem
                self.themes[theme_name] = theme_config
            except Exception as e:
                print(f"Failed to load theme {theme_file}: {e}")
    
    def get_theme_names(self):
        """Get list of available theme names."""
        return list(self.themes.keys())

    def apply_theme(self, app, theme_name):
        if theme_name not in self.themes:
            return

        theme = self.themes[theme_name]
        colors = theme['colors']

        # Set application style
        app.setStyle(QStyleFactory.create("Fusion"))

        # Apply UI scaling and font adjustments
        self.apply_ui_scaling(app)

        # Create palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(colors['window_bg']))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(colors['text_color']))
        palette.setColor(QPalette.ColorRole.Base, QColor(colors['url_bar_bg']))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors['button_bg']))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors['window_bg']))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors['text_color']))
        palette.setColor(QPalette.ColorRole.Text, QColor(colors['text_color']))
        palette.setColor(QPalette.ColorRole.Button, QColor(colors['button_bg']))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors['text_color']))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff0000"))
        palette.setColor(QPalette.ColorRole.Link, QColor(colors['accent']))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(colors['accent']))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))

        app.setPalette(palette)
    
    def get_theme_color(self, theme_name, color_key):
        """Get a specific color from a theme."""
        if theme_name in self.themes:
            return self.themes[theme_name]['colors'].get(color_key, "")
        return ""
    
    def apply_ui_scaling(self, app):
        """Apply UI scaling, font selection, and font size adjustments."""
        ui_config = creature_config.ui
        
        # Apply font family, weight, and style
        font = self.get_configured_font(app)
        
        # Apply font size adjustment
        if ui_config.font_size_adjustment != 0:
            current_size = font.pointSize()
            if current_size == -1:  # If point size is not set, use pixel size
                current_size = font.pixelSize()
                font.setPixelSize(max(8, current_size + ui_config.font_size_adjustment))
            else:
                font.setPointSize(max(8, current_size + ui_config.font_size_adjustment))
        
        app.setFont(font)
        
        # Apply scale factor via stylesheet for better control
        if ui_config.scale_factor != 1.0:
            scale_factor = ui_config.scale_factor
            # Apply scaling through style sheet
            app.setStyleSheet(f"""
                QWidget {{
                    font-size: {int(12 * scale_factor)}px;
                }}
                QLineEdit {{
                    min-height: {int(24 * scale_factor)}px;
                    padding: {int(4 * scale_factor)}px;
                }}
                QPushButton {{
                    min-height: {int(28 * scale_factor)}px;
                    min-width: {int(60 * scale_factor)}px;
                    padding: {int(4 * scale_factor)}px {int(8 * scale_factor)}px;
                }}
                QTabWidget::pane {{
                    border: {int(1 * scale_factor)}px solid;
                }}
                QTabWidget::tab-bar {{
                    alignment: left;
                }}
                QTabBar::tab {{
                    min-height: {int(30 * scale_factor)}px;
                    min-width: {int(80 * scale_factor)}px;
                    padding: {int(4 * scale_factor)}px {int(8 * scale_factor)}px;
                }}
                QToolBar {{
                    spacing: {int(4 * scale_factor)}px;
                    padding: {int(2 * scale_factor)}px;
                }}
            """)
    
    def get_configured_font(self, app):
        """Get font based on configuration settings."""
        ui_config = creature_config.ui
        
        # Start with the application's default font
        font = QFont(app.font())
        
        # Set font family
        font_family = ui_config.font_family.lower()
        if font_family == 'system':
            # Use system default - keep current family
            pass
        elif font_family == 'serif':
            font.setStyleHint(QFont.StyleHint.Serif)
            font.setFamily("serif")
        elif font_family == 'sans-serif':
            font.setStyleHint(QFont.StyleHint.SansSerif)
            font.setFamily("sans-serif")
        elif font_family == 'monospace':
            font.setStyleHint(QFont.StyleHint.Monospace)
            font.setFamily("monospace")
        else:
            # Specific font name
            font.setFamily(ui_config.font_family)
        
        # Set font weight
        font_weight = ui_config.font_weight.lower()
        if font_weight == 'normal':
            font.setWeight(QFont.Weight.Normal)
        elif font_weight == 'bold':
            font.setWeight(QFont.Weight.Bold)
        elif font_weight == 'light':
            font.setWeight(QFont.Weight.Light)
        elif font_weight.isdigit():
            # Numeric weight (100-900)
            weight_value = int(font_weight)
            if 100 <= weight_value <= 900:
                # Map CSS numeric weights to Qt weights
                if weight_value <= 200:
                    font.setWeight(QFont.Weight.Thin)
                elif weight_value <= 300:
                    font.setWeight(QFont.Weight.ExtraLight)
                elif weight_value <= 400:
                    font.setWeight(QFont.Weight.Light)
                elif weight_value <= 500:
                    font.setWeight(QFont.Weight.Normal)
                elif weight_value <= 600:
                    font.setWeight(QFont.Weight.Medium)
                elif weight_value <= 700:
                    font.setWeight(QFont.Weight.DemiBold)
                elif weight_value <= 800:
                    font.setWeight(QFont.Weight.Bold)
                else:
                    font.setWeight(QFont.Weight.ExtraBold)
        
        # Set font style
        font_style = ui_config.font_style.lower()
        if font_style == 'italic':
            font.setItalic(True)
        elif font_style == 'oblique':
            font.setStyle(QFont.Style.StyleOblique)
        else:  # normal
            font.setItalic(False)
        
        return font

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
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
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
    def __init__(self, profile, url=None):
        super().__init__()
        if url is None:
            url = creature_config.general.home_page
        self.profile = profile
        layout = QVBoxLayout(self)

        # Navigation bar
        nav_layout = QHBoxLayout()

        self.back_btn = QPushButton("←")
        self.forward_btn = QPushButton("→")
        self.refresh_btn = QPushButton("⟳")
        self.home_btn = QPushButton("🏠")
        self.url_bar = QLineEdit()
        self.go_btn = QPushButton("Go")

        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.forward_btn)
        nav_layout.addWidget(self.refresh_btn)
        nav_layout.addWidget(self.home_btn)
        nav_layout.addWidget(self.url_bar)
        nav_layout.addWidget(self.go_btn)

        layout.addLayout(nav_layout)

        # Web view with custom profile - FIXED API USAGE
        self.web_view = QWebEngineView()

        # Create a new page with the profile
        from PyQt6.QtWebEngineCore import QWebEnginePage
        page = QWebEnginePage(self.profile, self.web_view)
        self.web_view.setPage(page)

        layout.addWidget(self.web_view)

        # Connect signals
        self.back_btn.clicked.connect(self.web_view.back)
        self.forward_btn.clicked.connect(self.web_view.forward)
        self.refresh_btn.clicked.connect(self.web_view.reload)
        self.home_btn.clicked.connect(self.navigate_home)
        self.go_btn.clicked.connect(self.navigate)
        self.url_bar.returnPressed.connect(self.navigate)
        self.web_view.urlChanged.connect(lambda url: self.url_bar.setText(url.toString()))

        # Load initial page
        self.web_view.load(QUrl(url))
        
        # Set up keyboard shortcuts
        self.setup_shortcuts()

    def navigate(self):
        user_input = self.url_bar.text().strip()
        if not user_input:
            return
        
        final_url, is_search = process_url_or_search(user_input)
        self.navigate_to(final_url)

    def navigate_to(self, url):
        """Navigate to a specific URL (should already be processed)."""
        self.web_view.load(QUrl(url))
    
    def navigate_home(self):
        """Navigate to the home page."""
        home_url = creature_config.general.home_page
        self.navigate_to(home_url)
    
    def setup_shortcuts(self):
        """Set up keyboard shortcuts for this tab."""
        # Ctrl+G to focus URL bar
        focus_url_shortcut = QShortcut(QKeySequence("Ctrl+G"), self)
        focus_url_shortcut.activated.connect(self.focus_url_bar)
    
    def focus_url_bar(self):
        """Focus the URL bar and select all text."""
        self.url_bar.setFocus()
        self.url_bar.selectAll()

class CreatureBrowser(QMainWindow):
    def __init__(self, profile_name=None, force_new_window=None, theme=None):
        super().__init__()
        
        # Use config values if not overridden by arguments
        self.force_new_window = force_new_window if force_new_window is not None else creature_config.general.force_new_window
        profile_name = profile_name or creature_config.general.default_profile
        
        # Get profile-specific theme if configured
        profile_theme = ""
        if hasattr(creature_config, 'profiles') and profile_name in creature_config.profiles:
            profile_config = creature_config.profiles[profile_name]
            profile_theme = profile_config.get('theme', '')
        
        # Use profile theme, then command line theme, then general theme
        theme = theme or profile_theme or creature_config.general.theme
        self.current_theme = theme
        
        # Set up profile
        profile_dir = creature_config.general.profile_directory
        if not profile_dir.startswith('/'):
            profile_dir = Path.home() / profile_dir
        self.profile_manager = ProfileManager(profile_dir)
        self.profile = self.profile_manager.create_profile(profile_name)
        
        # Get profile-specific title suffix
        title_suffix = ""
        if hasattr(creature_config, 'profiles') and profile_name in creature_config.profiles:
            profile_config = creature_config.profiles[profile_name]
            title_suffix = profile_config.get('title_suffix', '')
        
        # Build window title
        if title_suffix:
            self.setWindowTitle(f"Creature Browser - {profile_name} ({title_suffix})")
        else:
            self.setWindowTitle(f"Creature Browser - {profile_name}")
        self.setGeometry(
            creature_config.window.x, 
            creature_config.window.y, 
            creature_config.window.width, 
            creature_config.window.height
        )

        # Apply theme
        self.theme_manager = ThemeManager()

        if not self.force_new_window:
            # Tab widget for normal mode
            self.tabs = QTabWidget()
            self.tabs.setTabsClosable(True)
            self.tabs.tabCloseRequested.connect(self.close_tab)
            self.setCentralWidget(self.tabs)

            # Toolbar
            toolbar = QToolBar()
            new_tab_action = QAction("+ New Tab", self)
            new_tab_action.triggered.connect(self.add_new_tab)
            toolbar.addAction(new_tab_action)
            self.addToolBar(toolbar)

            # Add first tab
            self.add_new_tab()
            
            # Set up tab cycling shortcuts
            self.setup_tab_shortcuts()
        else:
            # Single tab mode for window manager
            self.single_tab = BrowserTab(self.profile)
            self.setCentralWidget(self.single_tab)

        # Menu bar
        self.create_menu_bar()

    def create_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')

        if not self.force_new_window:
            new_tab_action = QAction('New Tab', self)
            new_tab_action.triggered.connect(self.add_new_tab)
            file_menu.addAction(new_tab_action)

        new_window_action = QAction('New Window', self)
        new_window_action.triggered.connect(self.new_window)
        file_menu.addAction(new_window_action)

        # Profile menu
        profile_menu = menubar.addMenu('Profile')
        profile_info_action = QAction('Profile Info', self)
        profile_info_action.triggered.connect(self.show_profile_info)
        profile_menu.addAction(profile_info_action)

        # Theme menu
        theme_menu = menubar.addMenu('Theme')
        for theme_name in self.theme_manager.themes.keys():
            theme_action = QAction(theme_name.capitalize(), self)
            theme_action.triggered.connect(lambda checked, t=theme_name: self.change_theme(t))
            theme_menu.addAction(theme_action)

    def add_new_tab(self, url=None):
        if url is None or isinstance(url, bool):
            url = creature_config.general.home_page
        
        if self.force_new_window:
            self.new_window(url)
            return

        tab = BrowserTab(self.profile, url)
        index = self.tabs.addTab(tab, "New Tab")
        self.tabs.setCurrentIndex(index)

        # Update tab title when page title changes
        tab.web_view.titleChanged.connect(
            lambda title, idx=index: self.update_tab_title(idx, title)
        )

    def update_tab_title(self, index, title):
        if hasattr(self, 'tabs') and index < self.tabs.count():
            short_title = title[:20] + "..." if len(title) > 20 else title
            self.tabs.setTabText(index, short_title)

    def close_tab(self, index):
        if hasattr(self, 'tabs'):
            if self.tabs.count() > 1:
                self.tabs.removeTab(index)
            else:
                if creature_config.browser.tab_close_behavior == 'close_window':
                    self.close()
                else:
                    # Keep window open with last tab
                    pass

    def new_window(self, url=None):
        if url is None or isinstance(url, bool):
            url = creature_config.general.home_page
            
        # Get current profile name from window title
        profile_name = self.windowTitle().split("Profile: ")[1] if "Profile: " in self.windowTitle() else "default"

        # Create new window with same profile
        new_browser = CreatureBrowser(profile_name, self.force_new_window)
        new_browser.show()

        if hasattr(new_browser, 'single_tab'):
            new_browser.single_tab.navigate_to(url)
        else:
            new_browser.add_new_tab(url)

    def show_profile_info(self):
        profile_name = self.windowTitle().split("Profile: ")[1] if "Profile: " in self.windowTitle() else "default"
        profile_path = self.profile_manager.get_profile_path(profile_name)

        msg = QMessageBox()
        msg.setWindowTitle("Profile Information")
        msg.setText(f"Profile: {profile_name}\nPath: {profile_path}")
        msg.exec()

    def change_theme(self, theme_name):
        app = QApplication.instance()
        self.theme_manager.apply_theme(app, theme_name)
    
    def setup_tab_shortcuts(self):
        """Set up keyboard shortcuts for tab cycling and window management."""
        if not hasattr(self, 'tabs'):
            return
        
        # Ctrl+Shift+Right - Next tab
        next_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Right"), self)
        next_tab_shortcut.activated.connect(self.next_tab)
        
        # Ctrl+Shift+Left - Previous tab
        prev_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Left"), self)
        prev_tab_shortcut.activated.connect(self.previous_tab)
        
        # Ctrl+N - New window
        new_window_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        new_window_shortcut.activated.connect(self.new_window)
    
    def next_tab(self):
        """Switch to the next tab."""
        if not hasattr(self, 'tabs') or self.tabs.count() <= 1:
            return
        
        current_index = self.tabs.currentIndex()
        next_index = (current_index + 1) % self.tabs.count()
        self.tabs.setCurrentIndex(next_index)
    
    def previous_tab(self):
        """Switch to the previous tab."""
        if not hasattr(self, 'tabs') or self.tabs.count() <= 1:
            return
        
        current_index = self.tabs.currentIndex()
        prev_index = (current_index - 1) % self.tabs.count()
        self.tabs.setCurrentIndex(prev_index)

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
        os.environ.setdefault("QT_WAYLAND_DISABLE_WINDOWDECORATION", 
                             "1" if creature_config.wayland.disable_window_decoration else "0")
    
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", 
                         "1" if creature_config.wayland.auto_screen_scale_factor else "0")

    # Fix graphics rendering issues
    chromium_flags = []
    if creature_config.wayland.disable_gpu_sandbox:
        chromium_flags.append("--disable-gpu-sandbox")
    if creature_config.wayland.disable_software_rasterizer:
        chromium_flags.append("--disable-software-rasterizer")
    if creature_config.wayland.enable_vaapi_video_decoder:
        chromium_flags.append("--enable-features=VaapiVideoDecoder")
    
    # Only add Wayland-specific Chromium flags if we're actually on Wayland
    if is_wayland and ui_config.enable_high_dpi_scaling:
        # Use more conservative approach - don't force ozone platform
        chromium_flags.append("--enable-features=UseOzonePlatform")
        # Let Chromium auto-detect the platform instead of forcing wayland
    
    # Add general compatibility flags
    chromium_flags.append("--no-sandbox")  # Often needed for Chromium
    chromium_flags.append("--disable-dev-shm-usage")  # Helps with shared memory issues
    
    if chromium_flags:
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", " ".join(chromium_flags))

    # Additional Chromium flags for better compatibility
    if creature_config.wayland.disable_sandbox:
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

def main():
    parser = argparse.ArgumentParser(description="Creature Browser with Profile Support")
    parser.add_argument("--profile", "-p", default=None, 
                       help="Profile name for sandboxing (default: from config)")
    parser.add_argument("--new-window", "-w", action="store_true",
                       help="Force new windows instead of tabs")
    parser.add_argument("--theme", "-t", default=None, 
                       choices=["light", "dark", "nord", "slate", "earthy", "violet", "forest", "autumn"],
                       help="Theme to use (default: from config)")
    parser.add_argument("url", nargs="?", default=None,
                       help="URL to open (optional)")
    parser.add_argument("--profile-dir", default=None,
                       help="Custom directory for profiles")
    parser.add_argument("--config", "-c", default=None,
                       help="Path to configuration file")
    parser.add_argument("--no-profile-prompt", action="store_true",
                       help="Don't prompt for profile selection")

    args = parser.parse_args()

    # Set config path if provided
    if args.config:
        os.environ['CREATURE_CONFIG'] = args.config

    # Setup Wayland compatibility and fix graphics issues
    setup_wayland_compatibility()

    app = QApplication(sys.argv)
    
    # Determine profile to use
    profile_name = args.profile
    
    # If URL provided and no profile specified, show profile selection dialog
    if args.url and not profile_name and not args.no_profile_prompt:
        profile_dir = creature_config.general.profile_directory
        if not profile_dir.startswith('/'):
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
    browser = CreatureBrowser(
        profile_name=profile_name,
        force_new_window=args.new_window if args.new_window else None,
        theme=args.theme
    )

    # Apply theme (browser already determined the correct theme based on profile)
    theme_manager = ThemeManager()
    theme_manager.apply_theme(app, browser.current_theme)

    browser.show()

    # Load initial URL
    initial_url = args.url or creature_config.general.home_page
    if hasattr(browser, 'single_tab'):
        browser.single_tab.navigate_to(initial_url)
    else:
        browser.add_new_tab(initial_url)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
