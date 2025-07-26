"""
Bookmark management for Creature Browser.
Contains classes for managing bookmarks, favicons, and the bookmark toolbar.
"""

import json
import logging
import re
import requests
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import Qt, QSize, QUrl
from PyQt6.QtGui import QIcon, QPixmap, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea,
    QMenu, QInputDialog, QMessageBox
)

from utilities import generate_guid, datetime_to_firefox_timestamp, firefox_timestamp_to_datetime

logger = logging.getLogger(__name__)


class BookmarkManager:
    """Manages per-profile bookmarks with hierarchical organization."""
    
    def __init__(self, profile_name):
        self.profile_name = profile_name
        self.bookmarks_file = self._get_bookmarks_path()
        self.bookmarks = self._load_bookmarks()
        self.favicon_cache = {}
        
    def _get_bookmarks_path(self):
        """Get the path to the bookmarks file for this profile."""
        profile_dir = Path.home() / '.config' / 'creature' / 'profiles' / self.profile_name
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir / 'bookmarks.json'
    
    def _load_bookmarks(self):
        """Load bookmarks from file, handling both old and Firefox formats."""
        if self.bookmarks_file.exists():
            try:
                with open(self.bookmarks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Check if it's Firefox format (has guid and root)
                    if isinstance(data, dict) and 'guid' in data and 'root' in data:
                        return data
                    
                    # Check if it's old format wrapped in bookmarks key
                    elif isinstance(data, dict) and 'bookmarks' in data:
                        # Convert old format to Firefox format
                        return self._convert_old_format_to_firefox(data['bookmarks'])
                    
                    # Check if it's old format as array
                    elif isinstance(data, list):
                        # Convert old format to Firefox format
                        return self._convert_old_format_to_firefox(data)
                        
            except Exception as e:
                logger.error(f"Failed to load bookmarks: {e}")
        
        # Return default bookmarks if file doesn't exist or loading fails
        return self._get_default_bookmarks()
    
    def _get_default_bookmarks(self):
        """Return default bookmarks in Firefox format."""
        now = datetime_to_firefox_timestamp()
        
        return {
            "guid": "root________",
            "title": "",
            "index": 0,
            "dateAdded": now,
            "lastModified": now,
            "id": 1,
            "typeCode": 2,
            "type": "text/x-moz-place-container",
            "root": "placesRoot",
            "children": [
                {
                    "guid": "menu________",
                    "title": "Bookmarks Menu",
                    "index": 0,
                    "dateAdded": now,
                    "lastModified": now,
                    "id": 2,
                    "typeCode": 2,
                    "type": "text/x-moz-place-container",
                    "root": "bookmarksMenuFolder",
                    "children": [
                        {
                            "guid": generate_guid(),
                            "title": "Creature Browser",
                            "index": 0,
                            "dateAdded": now,
                            "lastModified": now,
                            "id": 3,
                            "typeCode": 1,
                            "type": "text/x-moz-place",
                            "uri": "https://github.com/anthropics/claude-code"
                        },
                        {
                            "guid": generate_guid(),
                            "title": "🔍 Search Engines",  # Icon in title for custom folder icon
                            "index": 1,
                            "dateAdded": now,
                            "lastModified": now,
                            "id": 4,
                            "typeCode": 2,
                            "type": "text/x-moz-place-container",
                            "children": [
                                {
                                    "guid": generate_guid(),
                                    "title": "Google",
                                    "index": 0,
                                    "dateAdded": now,
                                    "lastModified": now,
                                    "id": 5,
                                    "typeCode": 1,
                                    "type": "text/x-moz-place",
                                    "uri": "https://www.google.com"
                                },
                                {
                                    "guid": generate_guid(),
                                    "title": "DuckDuckGo",
                                    "index": 1,
                                    "dateAdded": now,
                                    "lastModified": now,
                                    "id": 6,
                                    "typeCode": 1,
                                    "type": "text/x-moz-place",
                                    "uri": "https://duckduckgo.com"
                                }
                            ]
                        },
                        {
                            "guid": generate_guid(),
                            "title": "⚡ Development",  # Icon in title for custom folder icon
                            "index": 2,
                            "dateAdded": now,
                            "lastModified": now,
                            "id": 7,
                            "typeCode": 2,
                            "type": "text/x-moz-place-container",
                            "children": [
                                {
                                    "guid": generate_guid(),
                                    "title": "GitHub",
                                    "index": 0,
                                    "dateAdded": now,
                                    "lastModified": now,
                                    "id": 8,
                                    "typeCode": 1,
                                    "type": "text/x-moz-place",
                                    "uri": "https://github.com"
                                },
                                {
                                    "guid": generate_guid(),
                                    "title": "📚 Documentation",  # Nested folder with icon
                                    "index": 1,
                                    "dateAdded": now,
                                    "lastModified": now,
                                    "id": 9,
                                    "typeCode": 2,
                                    "type": "text/x-moz-place-container",
                                    "children": [
                                        {
                                            "guid": generate_guid(),
                                            "title": "MDN Web Docs",
                                            "index": 0,
                                            "dateAdded": now,
                                            "lastModified": now,
                                            "id": 10,
                                            "typeCode": 1,
                                            "type": "text/x-moz-place",
                                            "uri": "https://developer.mozilla.org"
                                        },
                                        {
                                            "guid": generate_guid(),
                                            "title": "Python Docs",
                                            "index": 1,
                                            "dateAdded": now,
                                            "lastModified": now,
                                            "id": 11,
                                            "typeCode": 1,
                                            "type": "text/x-moz-place",
                                            "uri": "https://docs.python.org"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    
    def _convert_old_format_to_firefox(self, old_bookmarks):
        """Convert old bookmark format to Firefox format."""
        now = datetime_to_firefox_timestamp()
        next_id = 1
        
        def convert_item(item, index=0):
            nonlocal next_id
            current_id = next_id
            next_id += 1
            
            if item.get('type') == 'bookmark':
                return {
                    "guid": generate_guid(),
                    "title": item.get('title', 'Untitled'),
                    "index": index,
                    "dateAdded": datetime_to_firefox_timestamp(item.get('date_added')),
                    "lastModified": now,
                    "id": current_id,
                    "typeCode": 1,
                    "type": "text/x-moz-place",
                    "uri": item.get('url', '')
                }
            elif item.get('type') == 'folder':
                # Extract icon from title if it starts with an emoji
                title = item.get('title', 'Folder')
                icon = item.get('icon', '')
                if icon and not title.startswith(icon):
                    title = f"{icon} {title}"
                
                folder = {
                    "guid": generate_guid(),
                    "title": title,
                    "index": index,
                    "dateAdded": datetime_to_firefox_timestamp(item.get('date_added')),
                    "lastModified": now,
                    "id": current_id,
                    "typeCode": 2,
                    "type": "text/x-moz-place-container"
                }
                
                if 'children' in item:
                    folder['children'] = [convert_item(child, i) for i, child in enumerate(item['children'])]
                
                return folder
            
            return None
        
        # Convert items and wrap in Firefox root structure
        converted_children = [convert_item(item, i) for i, item in enumerate(old_bookmarks) if item]
        converted_children = [item for item in converted_children if item is not None]
        
        return {
            "guid": "root________",
            "title": "",
            "index": 0,
            "dateAdded": now,
            "lastModified": now,
            "id": next_id,
            "typeCode": 2,
            "type": "text/x-moz-place-container",
            "root": "placesRoot",
            "children": [
                {
                    "guid": "menu________",
                    "title": "Bookmarks Menu",
                    "index": 0,
                    "dateAdded": now,
                    "lastModified": now,
                    "id": next_id + 1,
                    "typeCode": 2,
                    "type": "text/x-moz-place-container",
                    "root": "bookmarksMenuFolder",
                    "children": converted_children
                }
            ]
        }
    
    def save_bookmarks(self):
        """Save bookmarks to file in Firefox format."""
        try:
            # Save directly as Firefox format (self.bookmarks is already Firefox format)
            with open(self.bookmarks_file, 'w', encoding='utf-8') as f:
                json.dump(self.bookmarks, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved bookmarks to {self.bookmarks_file}")
        except Exception as e:
            logger.error(f"Failed to save bookmarks: {e}")
    
    def add_bookmark(self, title, url, parent_folder=None):
        """Add a new bookmark."""
        bookmark = {
            'type': 'bookmark',
            'title': title,
            'url': url,
            'favicon': None,
            'date_added': datetime.now().isoformat()
        }
        
        if parent_folder is None:
            self.bookmarks.append(bookmark)
        else:
            # Find parent folder and add bookmark
            folder = self._find_folder(parent_folder)
            if folder:
                folder['children'].append(bookmark)
        
        self.save_bookmarks()
        return bookmark
    
    def add_folder(self, title, parent_folder=None):
        """Add a new folder."""
        folder = {
            'type': 'folder',
            'title': title,
            'expanded': True,
            'children': [],
            'date_added': datetime.now().isoformat()
        }
        
        if parent_folder is None:
            self.bookmarks.append(folder)
        else:
            parent = self._find_folder(parent_folder)
            if parent:
                parent['children'].append(folder)
        
        self.save_bookmarks()
        return folder
    
    def _find_folder(self, folder_title):
        """Find a folder by title (recursive search)."""
        def search_items(items):
            for item in items:
                if item.get('type') == 'folder' and item.get('title') == folder_title:
                    return item
                if item.get('type') == 'folder' and 'children' in item:
                    result = search_items(item['children'])
                    if result:
                        return result
            return None
        
        return search_items(self.bookmarks)
    
    def get_flat_bookmarks(self):
        """Get all bookmarks in a flat list (for easy iteration)."""
        def flatten_items(items, result=None):
            if result is None:
                result = []
            
            for item in items:
                if item.get('type') == 'bookmark':
                    result.append(item)
                elif item.get('type') == 'folder' and 'children' in item:
                    flatten_items(item['children'], result)
            
            return result
        
        return flatten_items(self.bookmarks)


class FaviconManager:
    """Manages favicon fetching and caching."""
    
    def __init__(self, profile_name):
        self.profile_name = profile_name
        self.cache_dir = self._get_cache_dir()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Creature Browser'
        })
    
    def _get_cache_dir(self):
        """Get the favicon cache directory for this profile."""
        cache_dir = Path.home() / '.config' / 'creature' / 'profiles' / self.profile_name / 'favicons'
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir
    
    def get_favicon_path(self, url):
        """Get cached favicon path or fetch it."""
        try:
            # Create a safe filename from the URL
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            safe_name = re.sub(r'[^\w\.-]', '_', domain)
            
            favicon_path = self.cache_dir / f"{safe_name}.ico"
            
            # Return cached favicon if exists and not too old
            if favicon_path.exists():
                # Check if cache is less than 7 days old
                cache_time = datetime.fromtimestamp(favicon_path.stat().st_mtime)
                if datetime.now() - cache_time < timedelta(days=7):
                    return str(favicon_path)
            
            # Try to fetch favicon
            favicon_data = self.fetch_favicon(url)
            if favicon_data:
                with open(favicon_path, 'wb') as f:
                    f.write(favicon_data)
                logger.debug(f"Cached favicon for {domain}")
                return str(favicon_path)
            
        except Exception as e:
            logger.debug(f"Error getting favicon for {url}: {e}")
        
        return None
    
    def fetch_favicon(self, url):
        """Fetch favicon from URL."""
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            # Common favicon locations to try
            favicon_urls = [
                f"{base_url}/favicon.ico",
                f"{base_url}/favicon.png",
                f"{base_url}/apple-touch-icon.png",
                f"{base_url}/apple-touch-icon-precomposed.png"
            ]
            
            # Try to get favicon from HTML first
            try:
                response = self.session.get(url, timeout=5)
                if response.status_code == 200:
                    html_favicon = self._extract_favicon_from_html(response.text, base_url)
                    if html_favicon:
                        favicon_urls.insert(0, html_favicon)
            except:
                pass
            
            # Try each favicon URL
            for favicon_url in favicon_urls:
                try:
                    response = self.session.get(favicon_url, timeout=3)
                    if response.status_code == 200 and len(response.content) > 0:
                        # Verify it's an image
                        if response.headers.get('content-type', '').startswith(('image/', 'application/octet-stream')):
                            return response.content
                except:
                    continue
            
        except Exception as e:
            logger.debug(f"Error fetching favicon: {e}")
        
        return None
    
    def _extract_favicon_from_html(self, html, base_url):
        """Extract favicon URL from HTML."""
        try:
            # Simple regex to find favicon link tags
            import re
            
            # Look for various favicon link tags
            patterns = [
                r'<link[^>]*rel=["\'](?:shortcut )?icon["\'][^>]*href=["\']([^"\']+)["\']',
                r'<link[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\'](?:shortcut )?icon["\']'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    favicon_url = matches[0]
                    # Make absolute URL if relative
                    if favicon_url.startswith('//'):
                        favicon_url = f"{urlparse(base_url).scheme}:{favicon_url}"
                    elif favicon_url.startswith('/'):
                        favicon_url = f"{base_url}{favicon_url}"
                    elif not favicon_url.startswith('http'):
                        favicon_url = f"{base_url}/{favicon_url}"
                    
                    return favicon_url
        except:
            pass
        
        return None


class BookmarkToolbar(QWidget):
    """Vertical bookmark toolbar with favicon buttons."""
    
    def __init__(self, profile_name, parent=None):
        super().__init__(parent)
        self.profile_name = profile_name
        self.bookmark_manager = BookmarkManager(profile_name)
        self.favicon_manager = FaviconManager(profile_name)
        
        self.setFixedWidth(48)  # Fixed width for vertical toolbar
        
        # Get current theme colors - traverse up to find the browser window
        from themes import ThemeManager
        self.theme_manager = ThemeManager()
        parent_browser = parent
        while parent_browser and not hasattr(parent_browser, 'current_theme'):
            parent_browser = parent_browser.parent()
        
        current_theme = getattr(parent_browser, 'current_theme', 'light') if parent_browser else 'light'
        theme = self.theme_manager.themes.get(current_theme, self.theme_manager.themes.get('light', {}))
        self.colors = theme.get('colors', {}) if theme else {}
        
        # Debug information
        logger.debug(f"BookmarkToolbar: Found theme '{current_theme}', window_bg: {self.colors.get('window_bg', 'NOT_FOUND')}, toolbar_bg: {self.colors.get('toolbar_bg', 'NOT_FOUND')}")
        
        # Apply themed styles
        self.setStyleSheet(f"""
            BookmarkToolbar {{
                background-color: {self.colors.get('toolbar_bg', self.colors.get('window_bg', '#f5f5f5'))};
                border-right: 1px solid {self.colors.get('border_color', '#ddd')};
            }}
        """)
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(2)
        
        # Scroll area for bookmarks
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        # Content widget for bookmarks
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(2)
        
        self.scroll_area.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll_area)
        
        # Add bookmark button at bottom
        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(36, 36)
        self.add_button.setToolTip("Add bookmark")
        self.add_button.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {self.colors.get('border_color', '#ccc')};
                border-radius: 4px;
                background-color: {self.colors.get('button_bg', '#fff')};
                color: {self.colors.get('text_color', '#666')};
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.colors.get('tab_hover_bg', '#e8e8e8')};
                border-color: {self.colors.get('accent', '#999')};
            }}
            QPushButton:pressed {{
                background-color: {self.colors.get('accent', '#ddd')};
                color: white;
            }}
        """)
        self.add_button.clicked.connect(self.add_bookmark_dialog)
        self.main_layout.addWidget(self.add_button)
        
        # Spacer to push add button to bottom
        self.main_layout.addStretch()
        
        # Load and display bookmarks
        self.refresh_bookmarks()
    
    def refresh_theme(self):
        """Refresh the theme styling for the bookmark toolbar."""
        # Re-get current theme colors
        parent_browser = self.parent()
        while parent_browser and not hasattr(parent_browser, 'current_theme'):
            parent_browser = parent_browser.parent()
        
        current_theme = getattr(parent_browser, 'current_theme', 'light') if parent_browser else 'light'
        theme = self.theme_manager.themes.get(current_theme, self.theme_manager.themes.get('light', {}))
        self.colors = theme.get('colors', {}) if theme else {}
        
        # Debug information
        logger.debug(f"BookmarkToolbar.refresh_theme: Found theme '{current_theme}', window_bg: {self.colors.get('window_bg', 'NOT_FOUND')}, toolbar_bg: {self.colors.get('toolbar_bg', 'NOT_FOUND')}")
        
        # Re-apply themed styles
        self.setStyleSheet(f"""
            BookmarkToolbar {{
                background-color: {self.colors.get('toolbar_bg', self.colors.get('window_bg', '#f5f5f5'))};
                border-right: 1px solid {self.colors.get('border_color', '#ddd')};
            }}
        """)
    
    def refresh_bookmarks(self):
        """Refresh the bookmark display."""
        # Clear existing bookmark widgets
        for i in reversed(range(self.content_layout.count())):
            child = self.content_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        # Add bookmark widgets (extract bookmarks from Firefox format)
        bookmarks_data = self._get_bookmarks_menu_items()
        self._add_bookmark_items(bookmarks_data)
        
        # Add stretch at end
        self.content_layout.addStretch()
    
    def _get_bookmarks_menu_items(self):
        """Extract bookmark items from Firefox format."""
        bookmarks_root = self.bookmark_manager.bookmarks
        
        # Navigate to bookmarks menu folder
        if isinstance(bookmarks_root, dict) and 'children' in bookmarks_root:
            for child in bookmarks_root['children']:
                if child.get('root') == 'bookmarksMenuFolder':
                    return child.get('children', [])
        
        # Fallback to root children if no bookmarks menu found
        if isinstance(bookmarks_root, dict) and 'children' in bookmarks_root:
            return bookmarks_root.get('children', [])
        
        # If it's old format (list), return as-is
        if isinstance(bookmarks_root, list):
            return bookmarks_root
            
        return []
    
    def _add_bookmark_items(self, items, indent_level=0):
        """Recursively add bookmark items to the layout."""
        for item in items:
            item_type = item.get('type', '')
            
            # Handle Firefox format folder types
            if item_type == 'text/x-moz-place-container' or item_type == 'folder':
                # Create folder button (show folders at all levels as clickable buttons)
                folder_widget = self._create_folder_widget(item, indent_level)
                self.content_layout.addWidget(folder_widget)
                    
            # Handle Firefox format bookmark types
            elif item_type == 'text/x-moz-place' or item_type == 'bookmark':
                bookmark_widget = self._create_bookmark_widget(item, indent_level)
                self.content_layout.addWidget(bookmark_widget)
    
    def _create_bookmark_widget(self, bookmark, indent_level=0):
        """Create a bookmark button widget."""
        button = QPushButton()
        button.setFixedSize(36, 36)
        # Get URL from Firefox format (uri) or old format (url)
        url = bookmark.get('uri', bookmark.get('url', ''))
        button.setToolTip(f"{bookmark.get('title', 'Untitled')}\n{url}")
        
        # Set favicon icon
        favicon_path = self.favicon_manager.get_favicon_path(url)
        if favicon_path and Path(favicon_path).exists():
            icon = QIcon(favicon_path)
            button.setIcon(icon)
            button.setIconSize(QSize(24, 24))
        else:
            # Use first letter of title as fallback
            title = bookmark.get('title', '?')
            button.setText(title[0].upper())
            button.setStyleSheet(f"""
                QPushButton {{
                    border: 1px solid {self.colors.get('border_color', '#ccc')};
                    border-radius: 4px;
                    background-color: {self.colors.get('button_bg', '#fff')};
                    color: {self.colors.get('text_color', '#666')};
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {self.colors.get('tab_hover_bg', '#e8f4fd')};
                    border-color: {self.colors.get('accent', '#0078d4')};
                }}
                QPushButton:pressed {{
                    background-color: {self.colors.get('accent', '#cde7f7')};
                    color: white;
                }}
            """)
        
        # Connect click to navigation
        button.clicked.connect(lambda: self.navigate_to_bookmark(bookmark))
        
        # Add right-click context menu
        button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        button.customContextMenuRequested.connect(
            lambda pos: self.show_bookmark_context_menu(bookmark, button, pos)
        )
        
        return button
    
    def _create_folder_widget(self, folder, indent_level):
        """Create a folder button widget with submenu functionality."""
        button = QPushButton()
        button.setFixedSize(36, 36)
        button.setToolTip(folder.get('title', 'Folder'))
        
        # Extract folder icon from title (Firefox format stores icon in title)
        title = folder.get('title', 'Folder')
        folder_icon = '📁'  # default
        
        # Check if title starts with an emoji (for Firefox format)
        if title and len(title) > 0:
            first_char = title[0]
            # Check if first character is likely an emoji (basic check)
            if ord(first_char) > 127:  # Non-ASCII, likely emoji
                folder_icon = first_char
        
        # Fallback to custom icon field (for old format compatibility)
        if 'icon' in folder:
            folder_icon = folder['icon']
            
        button.setText(folder_icon)
        
        # Apply themed styling similar to bookmark buttons
        button.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {self.colors.get('border_color', '#ccc')};
                border-radius: 4px;
                background-color: {self.colors.get('button_bg', '#fff')};
                color: {self.colors.get('text_color', '#666')};
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.colors.get('tab_hover_bg', '#e8f4fd')};
                border-color: {self.colors.get('accent', '#0078d4')};
            }}
            QPushButton:pressed {{
                background-color: {self.colors.get('accent', '#cde7f7')};
                color: white;
            }}
        """)
        
        # Connect to show folder submenu
        button.clicked.connect(lambda: self.show_folder_submenu(folder, button))
        
        return button
    
    def show_folder_submenu(self, folder, button):
        """Show a popup menu with folder contents."""
        menu = QMenu(self)
        children = folder.get('children', [])
        
        if not children:
            # Empty folder
            empty_action = menu.addAction("(Empty folder)")
            empty_action.setEnabled(False)
        else:
            # Add folder contents to menu
            self._add_folder_contents_to_menu(menu, children)
        
        # Show menu at button position
        button_pos = button.mapToGlobal(button.rect().bottomLeft())
        menu.exec(button_pos)
    
    def _add_folder_contents_to_menu(self, menu, items):
        """Recursively add folder contents to menu."""
        for item in items:
            item_type = item.get('type', '')
            
            # Handle Firefox format bookmark types
            if item_type == 'text/x-moz-place' or item_type == 'bookmark':
                # Add bookmark as menu action
                title = item.get('title', 'Untitled')
                action = menu.addAction(title)
                action.triggered.connect(lambda checked, bookmark=item: self.navigate_to_bookmark(bookmark))
                
                # Add favicon if available (handle both Firefox uri and old url)
                url = item.get('uri', item.get('url', ''))
                favicon_path = self.favicon_manager.get_favicon_path(url)
                if favicon_path:
                    try:
                        pixmap = QPixmap(favicon_path)
                        if not pixmap.isNull():
                            # Scale favicon to menu icon size
                            scaled_pixmap = pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            action.setIcon(QIcon(scaled_pixmap))
                    except Exception:
                        pass  # Use text-only if favicon fails
                        
            # Handle Firefox format folder types
            elif item_type == 'text/x-moz-place-container' or item_type == 'folder':
                # Add submenu for nested folder
                folder_title = item.get('title', 'Folder')
                
                # Extract icon from title (Firefox format) or use icon field (old format)
                folder_icon = '📁'  # default
                if folder_title and len(folder_title) > 0:
                    first_char = folder_title[0]
                    if ord(first_char) > 127:  # Non-ASCII, likely emoji
                        folder_icon = first_char
                        # Remove icon from displayed title
                        if folder_title.startswith(folder_icon + ' '):
                            folder_title = folder_title[2:]
                
                # Fallback to custom icon field (old format)
                if 'icon' in item:
                    folder_icon = item['icon']
                    
                submenu = menu.addMenu(f"{folder_icon} {folder_title}")
                
                # Recursively add nested folder contents
                nested_children = item.get('children', [])
                if nested_children:
                    self._add_folder_contents_to_menu(submenu, nested_children)
                else:
                    empty_action = submenu.addAction("(Empty folder)")
                    empty_action.setEnabled(False)
    
    def navigate_to_bookmark(self, bookmark):
        """Navigate to bookmark URL."""
        # Get URL from Firefox format (uri) or old format (url)
        url = bookmark.get('uri', bookmark.get('url'))
        if url:
            # Find parent browser tab and navigate
            parent_tab = self.parent()
            while parent_tab and not hasattr(parent_tab, 'web_view'):
                parent_tab = parent_tab.parent()
            
            if parent_tab and hasattr(parent_tab, 'web_view'):
                parent_tab.web_view.load(QUrl(url))
    
    def show_bookmark_context_menu(self, bookmark, button, pos):
        """Show context menu for bookmark."""
        menu = QMenu(self)
        
        # Open in new tab action
        open_action = QAction("Open", self)
        open_action.triggered.connect(lambda: self.navigate_to_bookmark(bookmark))
        menu.addAction(open_action)
        
        menu.addSeparator()
        
        # Edit bookmark action
        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(lambda: self.edit_bookmark_dialog(bookmark))
        menu.addAction(edit_action)
        
        # Delete bookmark action
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.delete_bookmark(bookmark))
        menu.addAction(delete_action)
        
        # Show menu
        menu.exec(button.mapToGlobal(pos))
    
    def add_bookmark_dialog(self):
        """Show add bookmark dialog."""
        # Get current URL from browser if available
        current_url = ""
        current_title = ""
        
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, 'web_view'):
            parent_tab = parent_tab.parent()
        
        if parent_tab and hasattr(parent_tab, 'web_view'):
            current_url = parent_tab.web_view.url().toString()
            current_title = parent_tab.web_view.title()
        
        # Simple input dialogs for now
        title, ok1 = QInputDialog.getText(self, "Add Bookmark", "Title:", text=current_title)
        if ok1 and title:
            url, ok2 = QInputDialog.getText(self, "Add Bookmark", "URL:", text=current_url)
            if ok2 and url:
                self.bookmark_manager.add_bookmark(title, url)
                self.refresh_bookmarks()
    
    def edit_bookmark_dialog(self, bookmark):
        """Show edit bookmark dialog."""
        title, ok1 = QInputDialog.getText(
            self, "Edit Bookmark", "Title:", text=bookmark.get('title', '')
        )
        if ok1:
            url, ok2 = QInputDialog.getText(
                self, "Edit Bookmark", "URL:", text=bookmark.get('url', '')
            )
            if ok2:
                bookmark['title'] = title
                bookmark['url'] = url
                self.bookmark_manager.save_bookmarks()
                self.refresh_bookmarks()
    
    def delete_bookmark(self, bookmark):
        """Delete a bookmark."""
        reply = QMessageBox.question(
            self, "Delete Bookmark", 
            f"Delete bookmark '{bookmark.get('title', 'Untitled')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._remove_bookmark_from_data(bookmark)
            self.bookmark_manager.save_bookmarks()
            self.refresh_bookmarks()
    
    def _remove_bookmark_from_data(self, bookmark_to_remove):
        """Remove bookmark from the data structure."""
        def remove_from_items(items):
            for i, item in enumerate(items):
                if item is bookmark_to_remove:
                    del items[i]
                    return True
                elif item.get('type') == 'folder' and 'children' in item:
                    if remove_from_items(item['children']):
                        return True
            return False
        
        remove_from_items(self.bookmark_manager.bookmarks)