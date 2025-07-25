# GUI Improvements

This document describes the recent GUI improvements made to Creature Browser.

## Overview

The following improvements have been implemented to enhance the user experience:

1. **Application Icon** - Custom octopus logo throughout the application
2. **Splash Screen** - Optional startup splash screen with branding
3. **Improved Menu Structure** - Reorganized menu bar with new Help menu
4. **About Dialog** - Professional about dialog with version and author information
5. **Help System** - Built-in help dialog with documentation

## Features

### Application Icon

- **Logo Integration**: The purple octopus logo (`logo.png`) is now used as the application icon
- **Window Icon**: Appears in window title bars and taskbar
- **Scaling**: Automatically scaled to appropriate sizes (128x128 for dialogs)
- **Fallback**: Gracefully handles missing logo file

### Splash Screen

- **Configuration**: Controlled by `show_splash_screen` option in `[general]` section
- **Custom Image**: Uses `splash.png` as background with Creature branding
- **Loading Message**: Shows version information during startup
- **Automatic Timing**: Appears during application initialization and closes when browser is ready
- **Scaling**: Automatically scales large images (max 600x400)
- **Fallback**: Creates a simple colored splash if image is missing

**Configuration:**
```ini
[general]
show_splash_screen = true  # Enable splash screen (default: true)
                          # Set to false to disable completely
```

**Duration**: Fixed at 2 seconds minimum for optimal visibility

### Menu Structure Improvements

#### File Menu
- **New Tab** (Ctrl+T) - Moved from toolbar button to menu
- **New Window** (Ctrl+N) - With keyboard shortcut
- **Separator** - Clean organization

#### Help Menu (New)
- **Help...** (F1) - Opens comprehensive help dialog
- **About Creature Browser** - Shows version, author, and license information

### About Dialog

Professional about dialog featuring:
- **Logo Display** - Scaled application logo
- **Version Information** - Current version number (1.0.0)
- **Developer Credit** - micah@benchtop.tech + Claude Code
- **License** - MIT License
- **Description** - Brief feature overview

### Help System

Comprehensive help dialog with:
- **Quick Start Guide** - Overview of main features
- **Keyboard Shortcuts** - Complete shortcut reference table
- **Configuration Guide** - File locations and basic setup
- **Documentation Links** - Lists all available documentation files
- **Support Information** - Troubleshooting guidance

## Technical Implementation

### Class Structure

```
SplashScreen(QSplashScreen)
├── Custom splash with image loading
├── Automatic scaling and positioning
└── Loading message display

AboutDialog(QDialog)
├── Logo display with scaling
├── Version and author information
└── Professional layout

HelpDialog(QDialog)
├── HTML-formatted help content
├── Documentation file listing
└── Keyboard shortcuts table
```

### Configuration Options

| Option | Section | Default | Description |
|--------|---------|---------|-------------|
| `show_splash_screen` | `[general]` | `true` | Enable/disable startup splash screen (2 second duration) |

### File Requirements

- **logo.png** - Application icon (any size, auto-scaled)
- **splash.png** - Splash screen background (recommended: 400x300 or larger)

### Version Management

Version information is centrally managed:
```python
CREATURE_VERSION = "1.0.0"
CREATURE_AUTHOR = "micah@benchtop.tech + Claude Code"
CREATURE_LICENSE = "MIT"
```

## User Experience Improvements

### Before
- No application icon
- Toolbar with new tab button
- Limited help system
- No version information

### After
- Professional branding with custom logo
- Clean menu structure
- Comprehensive help system
- Version and author information
- Optional splash screen for professional startup

## Configuration Examples

### Enable All Features
```ini
[general]
theme = dark
show_splash_screen = true
home_page = https://www.google.com
```

### Minimal Configuration (No Splash)
```ini
[general]
theme = light
show_splash_screen = false
home_page = https://duckduckgo.com
```

## Keyboard Shortcuts

The following shortcuts are now properly documented and available:

| Shortcut | Action | Menu Location |
|----------|--------|---------------|
| Ctrl+T | New Tab | File → New Tab |
| Ctrl+N | New Window | File → New Window |
| F1 | Help | Help → Help... |
| Ctrl+G | Focus URL Bar | (Global) |
| Ctrl+Shift+Left/Right | Switch Tabs | (Global) |

## Maintenance

### Updating Version Information

To update version information, modify the constants in `creature.py`:
```python
CREATURE_VERSION = "1.1.0"  # Update version number
```

### Customizing Graphics

- Replace `logo.png` with custom application icon
- Replace `splash.png` with custom splash screen
- Images are automatically scaled to appropriate sizes

### Adding Documentation

Help dialog automatically detects documentation files in the `docs/` directory. Add new `.md` files to automatically include them in the help system.

## Future Enhancements

Potential future improvements:
- Animated splash screen
- Theme-aware icons
- Custom splash screen per profile
- Online help system integration
- Automatic update notifications in about dialog

The GUI improvements provide a professional, polished user experience while maintaining the application's focus on privacy and functionality.