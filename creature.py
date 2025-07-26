#!/usr/bin/env python3
import sys
import os
import argparse
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                            QWidget, QLineEdit, QPushButton, QHBoxLayout,
                            QTabWidget, QToolBar, QStyleFactory, QMessageBox,
                            QDialog, QListWidget, QDialogButtonBox, QLabel,
                            QListWidgetItem, QSplashScreen, QTextBrowser, QFormLayout)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings, QWebEngineScript, QWebEnginePage, QWebEngineCertificateError
from PyQt6.QtCore import QUrl, QStandardPaths, QDir, QTimer, Qt, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QPalette, QColor, QShortcut, QKeySequence, QFont, QFontDatabase, QPixmap, QIcon
import json
import re
import urllib.parse
import subprocess
import tempfile
import socket
import ssl
from urllib.parse import urlparse
from creature_config import config as creature_config
from configobj import ConfigObj
from validate import Validator
from keepassxc_manager import keepass_manager, KeePassXCError

# Application constants
CREATURE_VERSION = "0.1.0"
CREATURE_AUTHOR = "micah@benchtop.tech"
CREATURE_LICENSE = "MIT"

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


def fetch_certificate_from_url(url_string):
    """Fetch SSL certificate from URL using Python SSL."""
    try:
        parsed_url = urlparse(url_string)
        if parsed_url.scheme != 'https':
            return None, "URL is not HTTPS"
        
        hostname = parsed_url.hostname
        port = parsed_url.port or 443
        
        print(f"[SSL DEBUG] Fetching certificate for {hostname}:{port}")
        
        # Create SSL context
        context = ssl.create_default_context()
        
        # Connect and get certificate
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                # Get certificate in DER format
                cert_der = ssock.getpeercert(binary_form=True)
                # Get certificate info
                cert_info = ssock.getpeercert()
                
                return cert_der, cert_info
                
    except Exception as e:
        print(f"[SSL DEBUG] Failed to fetch certificate: {e}")
        return None, str(e)


def export_certificate_to_file(cert_der, hostname):
    """Export certificate DER data to a temporary file."""
    try:
        # Create temporary file with .crt extension
        temp_fd, temp_path = tempfile.mkstemp(suffix=f'_{hostname}.crt', prefix='creature_cert_')
        
        with os.fdopen(temp_fd, 'wb') as temp_file:
            temp_file.write(cert_der)
        
        print(f"[SSL DEBUG] Certificate exported to: {temp_path}")
        return temp_path
        
    except Exception as e:
        print(f"[SSL DEBUG] Failed to export certificate: {e}")
        return None


def check_openssl_available():
    """Check if OpenSSL command-line tool is available."""
    try:
        result = subprocess.run(['openssl', 'version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"[SSL DEBUG] OpenSSL available: {result.stdout.strip()}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    print("[SSL DEBUG] OpenSSL not available")
    return False


def parse_certificate_with_openssl(cert_der):
    """Parse certificate using OpenSSL to get detailed information."""
    try:
        # Write certificate to temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.crt')
        with os.fdopen(temp_fd, 'wb') as temp_file:
            temp_file.write(cert_der)
        
        try:
            # Use OpenSSL to parse certificate details
            result = subprocess.run([
                'openssl', 'x509', '-in', temp_path, '-text', '-noout'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Parse the OpenSSL output
                cert_details = parse_openssl_output(result.stdout)
                print(f"[SSL DEBUG] Parsed certificate with OpenSSL: {len(cert_details)} fields")
                return cert_details
            else:
                print(f"[SSL DEBUG] OpenSSL parsing failed: {result.stderr}")
                return None
                
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        print(f"[SSL DEBUG] Failed to parse with OpenSSL: {e}")
        return None


def check_certificate_revocation(cert_der, hostname):
    """Check certificate revocation status using OCSP and CRL."""
    revocation_info = {
        'checked': False,
        'revoked': False,
        'method': None,
        'status': 'Unknown',
        'error': None
    }
    
    try:
        # Write certificate to temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.crt')
        with os.fdopen(temp_fd, 'wb') as temp_file:
            temp_file.write(cert_der)
        
        try:
            print(f"[SSL DEBUG] Checking certificate revocation for {hostname}")
            
            # First try OCSP check using OpenSSL
            print("[SSL DEBUG] Attempting OCSP check...")
            ocsp_result = check_ocsp_status(temp_path, hostname)
            
            if ocsp_result['checked']:
                revocation_info.update(ocsp_result)
                return revocation_info
            
            # If OCSP fails, try CRL check
            print("[SSL DEBUG] OCSP failed, attempting CRL check...")
            crl_result = check_crl_status(temp_path)
            
            if crl_result['checked']:
                revocation_info.update(crl_result)
                return revocation_info
            
            # If both fail, return with error info
            revocation_info['error'] = "Both OCSP and CRL checks failed"
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        print(f"[SSL DEBUG] Exception in revocation check: {e}")
        revocation_info['error'] = str(e)
    
    return revocation_info


def check_ocsp_status(cert_path, hostname):
    """Check OCSP status using OpenSSL."""
    ocsp_info = {
        'checked': False,
        'revoked': False,
        'method': 'OCSP',
        'status': 'Unknown',
        'error': None
    }
    
    try:
        # Try to get issuer certificate for OCSP check
        # This is a simplified approach - for production, you'd need the full chain
        result = subprocess.run([
            'openssl', 'x509', '-in', cert_path, '-noout', '-ocsp_uri'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            ocsp_url = result.stdout.strip()
            print(f"[SSL DEBUG] Found OCSP URL: {ocsp_url}")
            
            # For now, we'll indicate that OCSP is available but not perform the full check
            # Full OCSP checking requires the issuer certificate and is complex
            ocsp_info['status'] = 'OCSP available but not checked (requires issuer cert)'
            ocsp_info['checked'] = True
            ocsp_info['ocsp_url'] = ocsp_url
            
        else:
            ocsp_info['error'] = 'No OCSP URL found in certificate'
            
    except Exception as e:
        print(f"[SSL DEBUG] OCSP check failed: {e}")
        ocsp_info['error'] = str(e)
    
    return ocsp_info


def check_crl_status(cert_path):
    """Check CRL status using OpenSSL."""
    crl_info = {
        'checked': False,
        'revoked': False,
        'method': 'CRL',
        'status': 'Unknown',
        'error': None
    }
    
    try:
        # Get CRL distribution points from certificate
        result = subprocess.run([
            'openssl', 'x509', '-in', cert_path, '-noout', '-text'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            output = result.stdout
            # Look for CRL distribution points
            if 'CRL Distribution Points:' in output:
                # Extract CRL URLs (simplified)
                lines = output.split('\n')
                crl_urls = []
                in_crl_section = False
                
                for line in lines:
                    if 'CRL Distribution Points:' in line:
                        in_crl_section = True
                    elif in_crl_section and 'URI:' in line:
                        uri = line.split('URI:')[1].strip()
                        if uri.startswith('http'):
                            crl_urls.append(uri)
                    elif in_crl_section and line.strip() and not line.startswith(' '):
                        in_crl_section = False
                
                if crl_urls:
                    print(f"[SSL DEBUG] Found CRL URLs: {crl_urls}")
                    crl_info['status'] = f'CRL available but not checked (found {len(crl_urls)} distribution points)'
                    crl_info['checked'] = True
                    crl_info['crl_urls'] = crl_urls
                else:
                    crl_info['error'] = 'CRL Distribution Points found but no valid URLs'
            else:
                crl_info['error'] = 'No CRL Distribution Points found in certificate'
        else:
            crl_info['error'] = f'Failed to read certificate: {result.stderr}'
            
    except Exception as e:
        print(f"[SSL DEBUG] CRL check failed: {e}")
        crl_info['error'] = str(e)
    
    return crl_info


def parse_openssl_output(openssl_text):
    """Parse OpenSSL x509 text output into structured data."""
    print(f"[SSL DEBUG] Parsing OpenSSL output, length: {len(openssl_text)}")
    
    cert_details = {}
    lines = openssl_text.split('\n')
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Key certificate fields
        if line.startswith('Version:'):
            cert_details['version'] = line.split(':', 1)[1].strip()
        elif line.startswith('Serial Number:'):
            # Handle multiline serial numbers
            serial = line.split(':', 1)[1].strip()
            # If serial is empty, look at next line
            if not serial and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Serial number is usually on the next line with hex format
                if next_line and not next_line.startswith(('Version:', 'Signature Algorithm:')):
                    serial = next_line
            cert_details['serial_number'] = serial
        elif line.startswith('Issuer:'):
            cert_details['issuer'] = line.split(':', 1)[1].strip()
        elif line.startswith('Subject:'):
            cert_details['subject'] = line.split(':', 1)[1].strip()
        elif 'Not Before:' in line:
            cert_details['not_before'] = line.split('Not Before:', 1)[1].strip()
        elif 'Not After :' in line or 'Not After:' in line:
            cert_details['not_after'] = line.split('Not After', 1)[1].split(':', 1)[1].strip()
        elif line.startswith('Public Key Algorithm:'):
            cert_details['public_key_algorithm'] = line.split(':', 1)[1].strip()
        elif 'Public-Key:' in line:
            # Extract key size
            if '(' in line and 'bit)' in line:
                key_size = line.split('(')[1].split(' bit)')[0]
                cert_details['key_size'] = f"{key_size} bits"
        elif line.startswith('Signature Algorithm:'):
            cert_details['signature_algorithm'] = line.split(':', 1)[1].strip()
        elif 'DNS:' in line:
            # Extract Subject Alternative Names
            if 'subject_alt_names' not in cert_details:
                cert_details['subject_alt_names'] = []
            # Parse DNS entries from SAN
            dns_entries = []
            parts = line.split('DNS:')
            for part in parts[1:]:  # Skip first empty part
                dns_name = part.split(',')[0].strip()
                if dns_name:
                    dns_entries.append(dns_name)
            cert_details['subject_alt_names'].extend(dns_entries)
    
    print(f"[SSL DEBUG] Parsed {len(cert_details)} certificate fields")
    return cert_details


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
        
        # Store the original system font size to prevent cumulative scaling
        system_font = QFont()
        self.original_font_size = system_font.pointSize()
        if self.original_font_size <= 0:
            self.original_font_size = 12  # Fallback
        
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

        # Apply UI scaling and font adjustments (pass theme for border radius styling)
        self.apply_ui_scaling(app, theme)

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
    
    def get_border_radius_stylesheet(self, theme):
        """Generate border radius stylesheet for UI elements."""
        if 'ui_elements' not in theme:
            return ""
        
        ui_elements = theme['ui_elements']
        colors = theme['colors']
        
        # Build comprehensive stylesheet with border radius
        return f"""
            /* Button styling with border radius */
            QPushButton {{
                border-radius: {ui_elements.get('button_radius', 4)}px;
                padding: 6px 12px;
                border: 1px solid {colors.get('border_color', '#ccc')};
                background-color: {colors.get('button_bg', '#f0f0f0')};
                color: {colors.get('text_color', '#000')};
            }}
            
            QPushButton:hover {{
                background-color: {colors.get('tab_hover_bg', colors.get('button_bg', '#f0f0f0'))};
                border-color: {colors.get('accent', '#0078d4')};
            }}
            
            QPushButton:pressed {{
                background-color: {colors.get('accent', '#0078d4')};
                color: white;
            }}
            
            /* Input field styling with border radius */
            QLineEdit {{
                border-radius: {ui_elements.get('input_radius', 4)}px;
                padding: 8px 12px;
                border: 2px solid {colors.get('border_color', '#ccc')};
                background-color: {colors.get('url_bar_bg', '#fff')};
                color: {colors.get('text_color', '#000')};
                selection-background-color: {colors.get('accent', '#0078d4')};
            }}
            
            QLineEdit:focus {{
                border-color: {colors.get('accent', '#0078d4')};
            }}
            
            /* Tab styling with border radius */
            QTabWidget::pane {{
                border-radius: {ui_elements.get('tab_radius', 6)}px;
                border: 1px solid {colors.get('border_color', '#ccc')};
                background-color: {colors.get('window_bg', '#fff')};
            }}
            
            QTabBar::tab {{
                border-radius: {ui_elements.get('tab_radius', 6)}px;
                padding: 8px 16px;
                margin: 2px;
                background-color: {colors.get('tab_bg', '#f5f5f5')};
                color: {colors.get('text_color', '#000')};
                border: 1px solid {colors.get('border_color', '#ccc')};
            }}
            
            QTabBar::tab:selected {{
                background-color: {colors.get('tab_active_bg', '#fff')};
                border-color: {colors.get('accent', '#0078d4')};
            }}
            
            QTabBar::tab:hover {{
                background-color: {colors.get('tab_hover_bg', '#e8e8e8')};
            }}
            
            /* Menu styling with border radius */
            QMenu {{
                border-radius: {ui_elements.get('menu_radius', 4)}px;
                padding: 4px;
                border: 1px solid {colors.get('border_color', '#ccc')};
                background-color: {colors.get('window_bg', '#fff')};
                color: {colors.get('text_color', '#000')};
            }}
            
            QMenu::item {{
                border-radius: {max(0, ui_elements.get('menu_radius', 4) - 2)}px;
                padding: 8px 16px;
                margin: 1px;
            }}
            
            QMenu::item:selected {{
                background-color: {colors.get('accent', '#0078d4')};
                color: white;
            }}
            
            /* Dialog styling with border radius */
            QDialog {{
                border-radius: {ui_elements.get('dialog_radius', 8)}px;
                background-color: {colors.get('window_bg', '#fff')};
            }}
            
            /* Toolbar styling */
            QToolBar {{
                border-radius: {ui_elements.get('toolbar_radius', 0)}px;
                background-color: {colors.get('toolbar_bg', colors.get('window_bg', '#fff'))};
                border: 1px solid {colors.get('border_color', '#ccc')};
                spacing: 2px;
                padding: 4px;
            }}
            
            /* Message boxes and other dialogs */
            QMessageBox {{
                background-color: {colors.get('window_bg', '#fff')};
            }}
            
            /* List widgets */
            QListWidget {{
                border-radius: {ui_elements.get('input_radius', 4)}px;
                border: 1px solid {colors.get('border_color', '#ccc')};
                background-color: {colors.get('url_bar_bg', '#fff')};
                color: {colors.get('text_color', '#000')};
            }}
            
            QListWidget::item {{
                border-radius: {max(0, ui_elements.get('input_radius', 4) - 2)}px;
                padding: 6px;
                margin: 1px;
            }}
            
            QListWidget::item:selected {{
                background-color: {colors.get('accent', '#0078d4')};
                color: white;
            }}
        """
    
    def get_theme_color(self, theme_name, color_key):
        """Get a specific color from a theme."""
        if theme_name in self.themes:
            return self.themes[theme_name]['colors'].get(color_key, "")
        return ""
    
    def apply_ui_scaling(self, app, theme=None):
        """Apply UI scaling, font selection, and font size adjustments."""
        ui_config = creature_config.ui
        
        # Apply font family, weight, and style
        font = self.get_configured_font(app)
        
        # Always use the original system font size as the base to prevent cumulative scaling
        base_font_size = self.original_font_size
        
        # Apply font size adjustment to the original base size
        final_font_size = base_font_size + ui_config.font_size_adjustment
        font.setPointSize(max(8, final_font_size))
        
        app.setFont(font)
        
        # Clear any existing stylesheet first to prevent accumulation
        app.setStyleSheet("")
        
        # Build base stylesheet with scaling
        base_stylesheet = ""
        if ui_config.scale_factor != 1.0:
            scale_factor = ui_config.scale_factor
            # Calculate scaled font size from the final font size (not hardcoded 12)
            scaled_font_size = int(final_font_size * scale_factor)
            
            base_stylesheet = f"""
                QWidget {{
                    font-size: {scaled_font_size}px;
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
            """
        
        # Combine with border radius styling if theme is provided
        if theme and 'ui_elements' in theme:
            border_radius_stylesheet = self.get_border_radius_stylesheet(theme)
            combined_stylesheet = base_stylesheet + "\n" + border_radius_stylesheet
            app.setStyleSheet(combined_stylesheet)
        else:
            app.setStyleSheet(base_stylesheet)
    
    def get_configured_font(self, app):
        """Get font based on configuration settings."""
        ui_config = creature_config.ui
        
        # Start with a clean system default font (not the current app font)
        font = QFont()
        
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

class SSLAwarePage(QWebEnginePage):
    """Custom QWebEnginePage that handles SSL certificate information."""
    
    sslStatusChanged = pyqtSignal(dict)
    
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.ssl_info = {
            'is_secure': False,
            'certificate_valid': True,
            'certificate_info': None,
            'errors': []
        }
    
    def certificateError(self, error):
        """Handle SSL certificate errors and extract certificate information."""
        print(f"[SSL DEBUG] Certificate error detected: {error.description()}")
        
        cert_info = {
            'error_type': error.error(),
            'description': error.description(),
            'url': error.url().toString(),
            'is_overridable': error.isOverridable(),
            'certificate_chain': []
        }
        
        # Extract certificate details from chain
        cert_chain = error.certificateChain()
        print(f"[SSL DEBUG] Certificate chain length: {len(cert_chain)}")
        
        for i, cert in enumerate(cert_chain):
            print(f"[SSL DEBUG] Processing certificate {i+1}")
            cert_details = {
                'subject': cert.subjectDisplayName(),
                'issuer': cert.issuerDisplayName(),
                'expiry_date': cert.expiryDate().toString(),
                'effective_date': cert.effectiveDate().toString(),
                'is_self_signed': cert.isSelfSigned(),
                'serial_number': cert.serialNumber().toHex().data().decode('utf-8') if cert.serialNumber().toHex() else 'N/A',
                'version': str(cert.version()) if hasattr(cert, 'version') else 'N/A'
            }
            cert_info['certificate_chain'].append(cert_details)
            print(f"[SSL DEBUG] Certificate {i+1} subject: {cert_details['subject']}")
        
        # Update SSL status
        self.ssl_info.update({
            'certificate_valid': False,  # If this method is called, there's an error
            'certificate_info': cert_info,
            'errors': [cert_info]
        })
        
        print(f"[SSL DEBUG] Emitting SSL status: {self.ssl_info}")
        self.sslStatusChanged.emit(self.ssl_info)
        
        # Return True to accept certificate (override error) or False to reject
        # For now, accept overridable errors but mark as invalid
        return error.isOverridable()


class CertificateDetailsDialog(QDialog):
    """Dialog showing detailed SSL certificate information."""
    
    def __init__(self, ssl_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Certificate Details")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        self.setup_ui(ssl_info)
    
    def setup_ui(self, ssl_info):
        """Set up the certificate details UI."""
        layout = QVBoxLayout(self)
        
        # Security status header
        status_label = QLabel()
        if ssl_info.get('is_secure'):
            if ssl_info.get('certificate_valid'):
                status_label.setText("🔒 Secure Connection")
                status_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
            else:
                status_label.setText("⚠️ Secure Connection with Certificate Issues")
                status_label.setStyleSheet("color: orange; font-weight: bold; font-size: 14px;")
        else:
            status_label.setText("🔓 Insecure Connection (HTTP)")
            status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        
        layout.addWidget(status_label)
        
        # Certificate information
        cert_info = ssl_info.get('certificate_info')
        if cert_info and cert_info.get('certificate_chain'):
            # Show certificate chain details
            for i, cert in enumerate(cert_info['certificate_chain']):
                cert_widget = self.create_certificate_widget(cert, i)
                layout.addWidget(cert_widget)
        elif ssl_info.get('is_secure'):
            # For valid HTTPS connections without error info
            info_widget = self.create_secure_connection_widget()
            layout.addWidget(info_widget)
        else:
            # HTTP connection
            info_label = QLabel("No SSL certificate - connection is not encrypted")
            info_label.setStyleSheet("color: red;")
            layout.addWidget(info_label)
        
        # Error information
        if ssl_info.get('errors'):
            error_widget = self.create_error_widget(ssl_info['errors'])
            layout.addWidget(error_widget)
        
        # Store ssl_info for export functionality
        self.ssl_info = ssl_info
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Export certificate button
        if ssl_info.get('is_secure'):
            export_button = QPushButton("Export Certificate")
            export_button.clicked.connect(self.export_certificate)
            button_layout.addWidget(export_button)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def create_certificate_widget(self, cert_details, index):
        """Create widget displaying certificate details."""
        from PyQt6.QtWidgets import QGroupBox
        
        group_box = QGroupBox(f"Certificate {index + 1}")
        layout = QFormLayout(group_box)
        
        layout.addRow("Subject:", QLabel(cert_details.get('subject', 'N/A')))
        layout.addRow("Issuer:", QLabel(cert_details.get('issuer', 'N/A')))
        layout.addRow("Valid From:", QLabel(cert_details.get('effective_date', 'N/A')))
        layout.addRow("Valid Until:", QLabel(cert_details.get('expiry_date', 'N/A')))
        layout.addRow("Self-signed:", QLabel('Yes' if cert_details.get('is_self_signed', False) else 'No'))
        layout.addRow("Serial Number:", QLabel(cert_details.get('serial_number', 'N/A')))
        layout.addRow("Version:", QLabel(cert_details.get('version', 'N/A')))
        
        return group_box
    
    def create_secure_connection_widget(self):
        """Create widget for secure HTTPS connections without certificate errors."""
        from PyQt6.QtWidgets import QGroupBox
        
        group_box = QGroupBox("Connection Information")
        layout = QFormLayout(group_box)
        
        # Add basic security information
        security_label = QLabel("✅ Connection is encrypted using HTTPS")
        security_label.setStyleSheet("color: green; font-weight: bold;")
        layout.addRow(security_label)
        
        info_label = QLabel(
            "Your connection to this site is secure. Data sent between your browser "
            "and this website is encrypted and cannot be read by others."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; margin-top: 10px;")
        layout.addRow(info_label)
        
        # Try to fetch and display detailed certificate information
        self.add_detailed_cert_info(layout)
        
        # Force layout update
        self.updateGeometry()
        self.update()
        
        return group_box
    
    def add_detailed_cert_info(self, layout):
        """Add detailed certificate information if available."""
        print("[SSL DEBUG] Fetching detailed certificate information...")
        
        # Get current URL from parent
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, 'web_view'):
            parent_tab = parent_tab.parent()
        
        if not parent_tab:
            print("[SSL DEBUG] Could not find parent tab with web_view")
            return
        
        current_url = parent_tab.web_view.url().toString()
        print(f"[SSL DEBUG] Current URL: {current_url}")
        
        # Check if OpenSSL is available for detailed parsing
        openssl_available = check_openssl_available()
        
        if openssl_available:
            try:
                # Fetch certificate
                result = fetch_certificate_from_url(current_url)
                
                if result[0] is not None:
                    cert_der, cert_info = result
                    
                    # Parse with OpenSSL for detailed info
                    openssl_details = parse_certificate_with_openssl(cert_der)
                    
                    # Check certificate revocation status
                    parsed_url = urlparse(current_url)
                    hostname = parsed_url.hostname
                    revocation_info = check_certificate_revocation(cert_der, hostname)
                    
                    # Update SSL status with revocation info
                    if hasattr(parent_tab, 'ssl_status'):
                        parent_tab.ssl_status['revocation_checked'] = revocation_info['checked']
                        parent_tab.ssl_status['revocation_status'] = revocation_info
                    
                    if openssl_details:
                        # Add detailed certificate information
                        from PyQt6.QtWidgets import QGroupBox
                        cert_group = QGroupBox("Certificate Details")
                        cert_layout = QFormLayout(cert_group)
                        
                        # Add each field if available
                        fields_added = 0
                        if 'subject' in openssl_details and openssl_details['subject']:
                            cert_layout.addRow("Subject:", QLabel(openssl_details['subject']))
                            fields_added += 1
                        
                        if 'issuer' in openssl_details and openssl_details['issuer']:
                            cert_layout.addRow("Issuer:", QLabel(openssl_details['issuer']))
                            fields_added += 1
                        
                        if 'not_before' in openssl_details and openssl_details['not_before']:
                            cert_layout.addRow("Valid From:", QLabel(openssl_details['not_before']))
                            fields_added += 1
                        
                        if 'not_after' in openssl_details and openssl_details['not_after']:
                            cert_layout.addRow("Valid Until:", QLabel(openssl_details['not_after']))
                            fields_added += 1
                        
                        if 'serial_number' in openssl_details and openssl_details['serial_number']:
                            cert_layout.addRow("Serial Number:", QLabel(openssl_details['serial_number']))
                            fields_added += 1
                        
                        if 'signature_algorithm' in openssl_details and openssl_details['signature_algorithm']:
                            cert_layout.addRow("Signature Algorithm:", QLabel(openssl_details['signature_algorithm']))
                            fields_added += 1
                        
                        if 'public_key_algorithm' in openssl_details and openssl_details['public_key_algorithm']:
                            cert_layout.addRow("Public Key Algorithm:", QLabel(openssl_details['public_key_algorithm']))
                            fields_added += 1
                        
                        if 'key_size' in openssl_details and openssl_details['key_size']:
                            cert_layout.addRow("Key Size:", QLabel(openssl_details['key_size']))
                            fields_added += 1
                        
                        if 'subject_alt_names' in openssl_details and openssl_details['subject_alt_names']:
                            san_text = ', '.join(openssl_details['subject_alt_names'])
                            san_label = QLabel(san_text)
                            san_label.setWordWrap(True)
                            cert_layout.addRow("Subject Alt Names:", san_label)
                            fields_added += 1
                        
                        # Add revocation status
                        if revocation_info['checked']:
                            revocation_label = QLabel(revocation_info['status'])
                            if revocation_info['revoked']:
                                revocation_label.setStyleSheet("color: red; font-weight: bold;")
                            else:
                                revocation_label.setStyleSheet("color: green;")
                            cert_layout.addRow("Revocation Status:", revocation_label)
                            fields_added += 1
                        elif revocation_info['error']:
                            error_label = QLabel(f"Check failed: {revocation_info['error']}")
                            error_label.setStyleSheet("color: orange;")
                            error_label.setWordWrap(True)
                            cert_layout.addRow("Revocation Status:", error_label)
                            fields_added += 1
                        
                        if fields_added > 0:
                            layout.addRow(cert_group)
                            print(f"[SSL DEBUG] Added {fields_added} certificate fields to dialog")
                            return
                        
            except Exception as e:
                print(f"[SSL DEBUG] Exception in detailed cert info: {e}")
        
        # Fallback message
        fallback_msg = "Detailed certificate information "
        if openssl_available:
            fallback_msg += "could not be retrieved. Check debug output for details."
        else:
            fallback_msg += "requires OpenSSL command-line tools."
            
        limitation_label = QLabel(f"\n{fallback_msg}")
        limitation_label.setWordWrap(True)
        limitation_label.setStyleSheet("color: #888; font-size: 11px; font-style: italic; margin-top: 10px;")
        layout.addRow(limitation_label)
    
    def create_error_widget(self, errors):
        """Create widget displaying certificate errors."""
        from PyQt6.QtWidgets import QGroupBox
        
        group_box = QGroupBox("Certificate Errors")
        layout = QVBoxLayout(group_box)
        
        for error in errors:
            error_label = QLabel(f"Error: {error.get('description', 'Unknown error')}")
            error_label.setStyleSheet("color: red;")
            layout.addWidget(error_label)
        
        return group_box
    
    def export_certificate(self):
        """Export the SSL certificate to a temporary file and open it with system tools."""
        # We need to get the current URL from the parent browser tab
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, 'web_view'):
            parent_tab = parent_tab.parent()
        
        if not parent_tab:
            QMessageBox.warning(self, "Export Error", "Could not determine current URL")
            return
        
        current_url = parent_tab.web_view.url().toString()
        
        # Show progress message
        progress_msg = QMessageBox(self)
        progress_msg.setWindowTitle("Exporting Certificate")
        progress_msg.setText("Fetching certificate from server...")
        progress_msg.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress_msg.show()
        progress_msg.repaint()
        
        try:
            # Fetch certificate
            result = fetch_certificate_from_url(current_url)
            progress_msg.close()
            
            if result[0] is None:
                QMessageBox.warning(self, "Export Error", f"Failed to fetch certificate: {result[1]}")
                return
            
            cert_der, cert_info = result
            parsed_url = urlparse(current_url)
            hostname = parsed_url.hostname
            
            # Export to temporary file
            cert_path = export_certificate_to_file(cert_der, hostname)
            if not cert_path:
                QMessageBox.warning(self, "Export Error", "Failed to create certificate file")
                return
            
            # Show success message with path and options
            msg = QMessageBox(self)
            msg.setWindowTitle("Certificate Exported")
            msg.setText(f"Certificate exported to:\n{cert_path}")
            msg.setInformativeText("You can now inspect this certificate with system tools like:\n"
                                 "• openssl x509 -in <file> -text -noout\n"
                                 "• View in system certificate viewer\n"
                                 "• Import into keychain/certificate store")
            
            # Add buttons for different actions
            open_folder_btn = msg.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
            copy_path_btn = msg.addButton("Copy Path", QMessageBox.ButtonRole.ActionRole)
            close_btn = msg.addButton("Close", QMessageBox.ButtonRole.AcceptRole)
            
            msg.exec()
            
            clicked_button = msg.clickedButton()
            if clicked_button == open_folder_btn:
                # Open folder containing the certificate
                import platform
                cert_dir = os.path.dirname(cert_path)
                if platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", cert_dir])
                elif platform.system() == "Windows":
                    subprocess.run(["explorer", cert_dir])
                else:  # Linux
                    subprocess.run(["xdg-open", cert_dir])
            elif clicked_button == copy_path_btn:
                # Copy path to clipboard
                from PyQt6.QtWidgets import QApplication
                clipboard = QApplication.clipboard()
                clipboard.setText(cert_path)
                
        except Exception as e:
            progress_msg.close()
            QMessageBox.critical(self, "Export Error", f"Failed to export certificate: {str(e)}")


class KeePassXCWebEngineView(QWebEngineView):
    """Custom QWebEngineView with KeePassXC integration."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.master_password = None
        self._inject_bridge_script()
    
    def _inject_bridge_script(self):
        """Inject the KeePassXC bridge JavaScript into all pages."""
        if not keepass_manager.enabled:
            print("[KeePassXC DEBUG] Bridge injection skipped - KeePassXC disabled")
            return
        
        # Read the bridge script
        bridge_script_path = Path(__file__).parent / "keepassxc_bridge.js"
        print(f"[KeePassXC DEBUG] Looking for bridge script at: {bridge_script_path}")
        if not bridge_script_path.exists():
            print("[KeePassXC DEBUG] Warning: KeePassXC bridge script not found")
            return
        
        try:
            with open(bridge_script_path, 'r', encoding='utf-8') as f:
                bridge_code = f.read()
            print(f"[KeePassXC DEBUG] Bridge script loaded, {len(bridge_code)} characters")
        except Exception as e:
            print(f"[KeePassXC DEBUG] Failed to read KeePassXC bridge script: {e}")
            return
        
        # Create and inject the script
        script = QWebEngineScript()
        script.setSourceCode(bridge_code)
        script.setName("KeePassXCBridge")
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)  # Use MainWorld instead of ApplicationWorld
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)  # Inject earlier
        script.setRunsOnSubFrames(True)
        
        self.page().scripts().insert(script)
        print("[KeePassXC DEBUG] Bridge script injected successfully")
    
    def contextMenuEvent(self, event):
        """Override context menu to add KeePassXC options."""
        # Create our own context menu since PyQt6 doesn't have createStandardContextMenu
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        
        # Store the global position immediately to ensure accuracy
        global_pos = event.globalPos()
        
        # Get information about the clicked element
        pos = event.pos()
        js_code = f"""
        (function() {{
            var element = document.elementFromPoint({pos.x()}, {pos.y()});
            if (!element) return null;
            
            if (['input', 'textarea'].includes(element.tagName.toLowerCase())) {{
                return {{
                    isFormField: true,
                    type: element.type || 'text',
                    name: element.name || '',
                    id: element.id || '',
                    placeholder: element.placeholder || '',
                    isPassword: element.type === 'password',
                    isEmail: element.type === 'email' || element.name.toLowerCase().includes('email'),
                    isUsername: element.name.toLowerCase().includes('user') || 
                               element.id.toLowerCase().includes('user') ||
                               element.placeholder.toLowerCase().includes('user')
                }};
            }}
            return null;
        }})();
        """
        
        # Add basic browser actions first
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
        
        # Execute JavaScript to get element info, passing stored global position
        self.page().runJavaScript(js_code, lambda result: self._show_context_menu(menu, event, result, global_pos))
    
    def _show_context_menu(self, menu, event, element_info, global_pos):
        """Show context menu with KeePassXC options if applicable."""
        # Add KeePassXC options only if enabled and configured
        if keepass_manager.enabled and keepass_manager.config.show_context_menu:
            if element_info and element_info.get('isFormField'):
                menu.addSeparator()
                
                # Add KeePassXC actions
                if element_info.get('isPassword'):
                    fill_password_action = QAction("Fill Password from KeePassXC", self)
                    fill_password_action.triggered.connect(lambda: self._fill_password(event.pos()))
                    menu.addAction(fill_password_action)
                elif element_info.get('isUsername') or element_info.get('isEmail'):
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
    
    def _get_master_password(self):
        """Get master password from user if not cached."""
        if self.master_password and keepass_manager.test_database_access(self.master_password):
            return self.master_password
        
        # Prompt for master password
        from PyQt6.QtWidgets import QInputDialog, QLineEdit
        password, ok = QInputDialog.getText(
            self, 
            "KeePassXC Master Password", 
            "Enter your KeePassXC master password:",
            QLineEdit.EchoMode.Password
        )
        
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
        
        self.page().runJavaScript(js_code, lambda result: print(f"[KeePassXC DEBUG] Password fill result: {result}"))
    
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
        
        self.page().runJavaScript(js_code, lambda result: print(f"[KeePassXC DEBUG] Username fill result: {result}"))
    
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
            if result.get('success'):
                message = "Login form filled successfully"
                if result.get('errors'):
                    message += f"\nWarnings: {', '.join(result['errors'])}"
                QMessageBox.information(self, "KeePassXC", message)
            else:
                error_msg = "Failed to fill login form"
                if result.get('errors'):
                    error_msg += f"\nErrors: {', '.join(result['errors'])}"
                QMessageBox.warning(self, "Error", error_msg)
        else:
            print(f"Form fill result: {result}")
    
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
        return value.replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')

class SplashScreen(QSplashScreen):
    """Custom splash screen with Creature branding."""
    
    def __init__(self):
        # Load splash image
        splash_path = Path(__file__).parent / "splash.png"
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
        self.setWindowFlags(Qt.WindowType.SplashScreen | 
                           Qt.WindowType.FramelessWindowHint | 
                           Qt.WindowType.WindowStaysOnTopHint |
                           Qt.WindowType.Tool)
        
        # Set window class for Wayland/Hyprland recognition
        self.setProperty("_q_wayland_window_type", "splash")
        
        # Set window class name for window managers
        if hasattr(self, 'setWindowClassName'):
            self.setWindowClassName("creature-splash")
        
        # Center the splash screen on the screen
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2, (screen.height() - size.height()) // 2)
        
        # Show loading message with better styling
        self.showMessage(f"Starting Creature Browser v{CREATURE_VERSION}...", 
                        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, 
                        QColor(255, 255, 255))
        
        # Set up timer for loading messages
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_message)
        self.message_index = 0
        self.messages = [
            f"Starting Creature Browser v{CREATURE_VERSION}...",
            "Loading configuration...",
            "Initializing browser engine...",
            "Setting up profiles...",
            "Applying theme...",
            "Ready!"
        ]
        self.timer.start(300)  # Update every 300ms
        
        # Additional Wayland/Hyprland compatibility
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
    
    def update_message(self):
        """Update the loading message."""
        if self.message_index < len(self.messages):
            self.showMessage(self.messages[self.message_index], 
                            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, 
                            QColor(255, 255, 255))
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
        logo_path = Path(__file__).parent / "logo.png"
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
        import subprocess
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
            QMessageBox.information(
                self, 
                "Configuration Path", 
                f"Configuration file location:\n{self.config_path}\n\nUnable to open folder: {e}"
            )

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
                doc_name = doc_file.stem.replace('-', ' ').title()
                help_content += f'<li>{doc_name} - <code>{doc_file.name}</code></li>\n'
        
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
        
        # SSL indicator (make it a button to match other navigation buttons)
        self.ssl_indicator = QPushButton("🔓")
        self.ssl_indicator.setToolTip("Click for SSL certificate details")
        self.ssl_indicator.clicked.connect(self.show_certificate_details)
        self.ssl_indicator.setStyleSheet("""
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: transparent;
                font-size: 14px;
                padding: 6px 8px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        
        self.url_bar = QLineEdit()

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
        self.ssl_status = {
            'is_secure': False,
            'certificate_valid': True,
            'certificate_info': None,
            'errors': [],
            'revocation_checked': False,
            'revocation_status': None
        }

        layout.addWidget(self.web_view)

        # Connect signals
        self.back_btn.clicked.connect(self.web_view.back)
        self.forward_btn.clicked.connect(self.web_view.forward)
        self.refresh_btn.clicked.connect(self.web_view.reload)
        self.url_bar.returnPressed.connect(self.navigate)
        self.web_view.urlChanged.connect(self.on_url_changed)
        
        # Connect SSL status signals
        self.ssl_page.sslStatusChanged.connect(self.on_ssl_status_changed)

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
        
        # Alt+Home to navigate to home page
        home_shortcut = QShortcut(QKeySequence("Alt+Home"), self)
        home_shortcut.activated.connect(self.navigate_home)
    
    def focus_url_bar(self):
        """Focus the URL bar and select all text."""
        self.url_bar.setFocus()
        self.url_bar.selectAll()
    
    def on_url_changed(self, url):
        """Handle URL changes to detect HTTPS vs HTTP and update SSL indicator."""
        # Update URL bar
        self.url_bar.setText(url.toString())
        
        # Check if connection is secure
        is_secure = url.scheme().lower() == 'https'
        self.ssl_status['is_secure'] = is_secure
        
        print(f"[SSL DEBUG] URL changed to: {url.toString()}, is_secure: {is_secure}")
        
        # Update SSL indicator for URL scheme changes
        self.update_ssl_indicator()
    
    def on_ssl_status_changed(self, ssl_info):
        """Handle SSL status changes from the SSL-aware page."""
        print(f"[SSL DEBUG] SSL status changed: {ssl_info}")
        self.ssl_status.update(ssl_info)
        self.update_ssl_indicator()
    
    def update_ssl_indicator(self):
        """Update SSL indicator based on current status."""
        if self.ssl_status['is_secure']:
            if self.ssl_status['certificate_valid']:
                self.ssl_indicator.setText("🔒")
                self.ssl_indicator.setStyleSheet("""
                    QPushButton {
                        border: 1px solid #4CAF50;
                        border-radius: 4px;
                        background-color: #E8F5E8;
                        font-size: 14px;
                        color: #4CAF50;
                        padding: 6px 8px;
                        min-height: 20px;
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
                        font-size: 14px;
                        color: #FF9800;
                        padding: 6px 8px;
                        min-height: 20px;
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
                    font-size: 14px;
                    color: #F44336;
                    padding: 6px 8px;
                    min-height: 20px;
                }
                QPushButton:hover {
                    background-color: #FFCDD2;
                }
            """)
            self.ssl_indicator.setToolTip("Insecure HTTP connection - Click for details")
    
    def show_certificate_details(self):
        """Show certificate details dialog when SSL indicator is clicked."""
        print(f"[SSL DEBUG] Current SSL status: {self.ssl_status}")  # Debug print
        dialog = CertificateDetailsDialog(self.ssl_status, self)
        dialog.exec()


class CreatureBrowser(QMainWindow):
    def __init__(self, profile_name=None, force_new_window=None, theme=None):
        super().__init__()
        
        # Use config values if not overridden by arguments
        self.force_new_window = force_new_window if force_new_window is not None else creature_config.general.force_new_window
        self.profile_name = profile_name or creature_config.general.default_profile
        
        # Get profile-specific theme if configured
        profile_theme = ""
        if hasattr(creature_config, 'profiles') and self.profile_name in creature_config.profiles:
            profile_config = creature_config.profiles[self.profile_name]
            profile_theme = profile_config.get('theme', '')
        
        # Use profile theme, then command line theme, then general theme
        theme = theme or profile_theme or creature_config.general.theme
        self.current_theme = theme
        
        # Set up profile
        profile_dir = creature_config.general.profile_directory
        if not profile_dir.startswith('/'):
            profile_dir = Path.home() / profile_dir
        self.profile_manager = ProfileManager(profile_dir)
        self.profile = self.profile_manager.create_profile(self.profile_name)
        
        # Get profile-specific title suffix
        title_suffix = ""
        if hasattr(creature_config, 'profiles') and self.profile_name in creature_config.profiles:
            profile_config = creature_config.profiles[self.profile_name]
            title_suffix = profile_config.get('title_suffix', '')
        
        # Build window title
        if title_suffix:
            self.setWindowTitle(f"Creature Browser - {self.profile_name} ({title_suffix})")
        else:
            self.setWindowTitle(f"Creature Browser - {self.profile_name}")
        
        # Set application icon
        logo_path = Path(__file__).parent / "icon.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        
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

            # Initial tab will be added by main() with proper URL
            
            # Set up tab cycling shortcuts
            self.setup_tab_shortcuts()
        else:
            # Single tab mode for window manager
            self.single_tab = BrowserTab(self.profile)
            self.setCentralWidget(self.single_tab)

        # Set up hamburger menu (replaces traditional menu bar)
        self.setup_hamburger_menu()

    def setup_hamburger_menu(self):
        """Set up hamburger menu button in tab bar (replaces traditional menu bar)."""
        from PyQt6.QtWidgets import QPushButton
        from PyQt6.QtGui import QIcon, QPixmap
        from PyQt6.QtCore import Qt, QSize
        from pathlib import Path
        
        # Create hamburger menu button
        self.hamburger_button = QPushButton(self)
        
        # Load logo.png as the button icon
        logo_path = Path(__file__).parent / 'icon.png'
        if logo_path.exists():
            icon = QIcon(str(logo_path))
            self.hamburger_button.setIcon(icon)
            # Let Qt handle scaling by setting the desired icon size
            self.hamburger_button.setIconSize(QSize(36, 28))
        else:
            # Fallback to text if logo not found
            self.hamburger_button.setText('☰')
            
        self.hamburger_button.setFixedSize(40, 32)
        self.hamburger_button.setToolTip('Menu')
        self.hamburger_button.clicked.connect(self.show_hamburger_menu)
        
        # Remove border and background styling with minimal padding
        self.hamburger_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                padding: 0px;
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
        self.close_button = QPushButton('✕', self)
        self.close_button.setFixedSize(32, 32)
        self.close_button.setToolTip('Close Window')
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
        
        if not self.force_new_window and hasattr(self, 'tabs'):
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
    
    def show_hamburger_menu(self):
        """Show the hamburger menu with all menu options."""
        from PyQt6.QtWidgets import QMenu
        
        menu = QMenu(self)
        
        # File section
        if not self.force_new_window:
            new_tab_action = QAction('New Tab', self)
            new_tab_action.setShortcut('Ctrl+T')
            new_tab_action.triggered.connect(self.add_new_tab)
            menu.addAction(new_tab_action)
            menu.addSeparator()

        new_window_action = QAction('New Window', self)
        new_window_action.setShortcut('Ctrl+N')
        new_window_action.triggered.connect(self.new_window)
        menu.addAction(new_window_action)
        
        menu.addSeparator()
        
        # Profile section
        profile_info_action = QAction(f'Profile: {self.profile_name.capitalize()} - Info', self)
        profile_info_action.triggered.connect(self.show_profile_info)
        menu.addAction(profile_info_action)
        
        menu.addSeparator()

        # Theme section
        theme_submenu = menu.addMenu('Themes')
        for theme_name in self.theme_manager.themes.keys():
            theme_action = QAction(theme_name.capitalize(), self)
            theme_action.setCheckable(True)
            theme_action.setChecked(theme_name == self.current_theme)
            theme_action.triggered.connect(lambda checked, t=theme_name: self.change_theme(t))
            theme_submenu.addAction(theme_action)
        
        menu.addSeparator()
        
        # Help section
        help_action = QAction('Help...', self)
        help_action.setShortcut('F1')
        help_action.triggered.connect(self.show_help)
        menu.addAction(help_action)
        
        about_action = QAction('About Creature Browser', self)
        about_action.triggered.connect(self.show_about)
        menu.addAction(about_action)
        
        menu.addSeparator()
        
        # Quit action at bottom
        quit_action = QAction('Quit', self)
        quit_action.setShortcut('Ctrl+Q')
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)
        
        # Show menu below the hamburger button
        button_pos = self.hamburger_button.mapToGlobal(self.hamburger_button.rect().bottomLeft())
        menu.popup(button_pos)

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

        # Create new window with same profile
        new_browser = CreatureBrowser(self.profile_name, self.force_new_window)
        new_browser.show()

        if hasattr(new_browser, 'single_tab'):
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
    
    # Set application icon
    logo_path = Path(__file__).parent / "logo.png"
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
    
    # Close splash screen after browser is shown
    if splash:
        splash.finish(browser)

    # Load initial URL
    initial_url = args.url or creature_config.general.home_page
    if hasattr(browser, 'single_tab'):
        browser.single_tab.navigate_to(initial_url)
    else:
        browser.add_new_tab(initial_url)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
