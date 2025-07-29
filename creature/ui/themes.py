"""
Theme management for Creature Browser.
Handles application theming, UI scaling, and visual styling.
"""

import logging
from pathlib import Path
import importlib.resources

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtWidgets import QStyleFactory, QApplication

from configobj import ConfigObj
from validate import Validator

from creature.config.manager import config as creature_config

logger = logging.getLogger(__name__)


class ThemeManager:
    def __init__(self):
        # Use data directory for themes
        try:
            self.themes_dir = importlib.resources.files('creature').parent / 'data' / 'config' / 'themes'
        except Exception:
            # Fallback to relative path
            self.themes_dir = Path(__file__).parent.parent.parent / 'data' / 'config' / 'themes'
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
                logger.error(f"Failed to load theme {theme_file}: {e}")
    
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
        else:
            # Try to parse numeric weight
            try:
                numeric_weight = int(font_weight)
                # Map numeric weights to Qt constants
                if numeric_weight <= 100:
                    font.setWeight(QFont.Weight.Thin)
                elif numeric_weight <= 200:
                    font.setWeight(QFont.Weight.ExtraLight)
                elif numeric_weight <= 300:
                    font.setWeight(QFont.Weight.Light)
                elif numeric_weight <= 400:
                    font.setWeight(QFont.Weight.Normal)
                elif numeric_weight <= 500:
                    font.setWeight(QFont.Weight.Medium)
                elif numeric_weight <= 600:
                    font.setWeight(QFont.Weight.DemiBold)
                elif numeric_weight <= 700:
                    font.setWeight(QFont.Weight.Bold)
                elif numeric_weight <= 800:
                    font.setWeight(QFont.Weight.ExtraBold)
                else:
                    font.setWeight(QFont.Weight.Black)
            except ValueError:
                # Default to normal if can't parse
                font.setWeight(QFont.Weight.Normal)
        
        # Set font style
        font_style = ui_config.font_style.lower()
        if font_style == 'italic':
            font.setItalic(True)
        elif font_style == 'oblique':
            font.setStyle(QFont.Style.StyleOblique)
        
        return font