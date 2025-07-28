# Creature Browser

A web browser built with PyQt6 that supports multiple isolated profiles, custom themes, and flexible configuration options.

## Features

- **Profile Isolation** - Complete separation of cookies, storage, and cache between profiles
- **Custom Themes** - 8 built-in themes with support for custom theme creation
- **Per-Profile Configuration** - Different themes, home pages, and settings for each profile
- **Profile Selection Dialog** - Smart profile picker when opening URLs
- **Smart URL Bar** - Automatically detects URLs vs search queries with configurable search engines
- **Bookmark Toolbar** - Per-profile bookmark sidebar with favicon support and hierarchical organization
- **SSL Certificate Inspection** - Comprehensive SSL status indicator with OpenSSL integration for detailed certificate analysis
- **Minimal Mode** - Distraction-free browsing with no tabs, menu, or navigation bar (--minimal flag)
- **Modal URL Bar** - Clean navigation popup (Ctrl+G) for minimal mode
- **KeePassXC Integration** - Secure password manager integration with context menu support
- **Wayland Support** - Optimized for modern Linux desktop environments
- **ConfigObj Integration** - Flexible configuration with validation

## Requirements

- Python 3.13+
- PyQt6
- PyQt6-WebEngine
- ConfigObj
- uv (for dependency management)

## Installation

### Using uv (Recommended)

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd browser
   ```

2. Install uv if you haven't already:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   

3. Create and activate the virtual environment:
   ```bash
   uv venv
   source .venv/bin/activate  # On Linux/Mac
   # or
   .venv\Scripts\activate  # On Windows
   ```

4. Install dependencies:
   ```bash
   uv pip install -e .
   ```

### Manual Installation

If not using uv, you can install with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # You'll need to generate this from pyproject.toml
```

## Quick Start

### Basic Usage

```bash
# Launch browser with default profile
python creature.py

# Open a URL
python creature.py https://github.com

# Open URL with specific profile
python creature.py https://github.com --profile work
```

### Profile Management

When opening a URL without specifying a profile, Creature will show a profile selection dialog where you can:
- Choose an existing profile
- Create a new profile on the fly
- Set different themes for visual distinction

## Configuration

### Configuration File Location

Creature looks for configuration in the following order:
1. Path specified by `CREATURE_CONFIG` environment variable
2. `~/.config/creature/config.ini`
3. `./config.ini` in the current directory

### Basic Configuration

```ini
[general]
theme = dark
home_page = https://www.google.com
default_profile = default

[window]
width = 1400
height = 900

[profiles]
[[work]]
theme = slate
title_suffix = Work
home_page = https://github.com

[[personal]]
theme = forest
title_suffix = Personal
```

## Profiles

Each profile maintains separate:
- Cookies and session data
- Local storage
- Cache
- Form data
- Custom theme
- Home page

Profile data is stored in `~/.config/creature/profile_<name>/`

## Smart URL Bar

The URL bar intelligently determines whether your input is a URL or search query:

### Recognized as URLs:
- `github.com` → `https://github.com`
- `https://example.com` → loads directly
- `localhost:3000` → `https://localhost:3000`
- `192.168.1.1` → `https://192.168.1.1`
- `server.local` → `https://server.local` (local DNS)
- `http://myserver` → loads directly

### Treated as Search:
- `python tutorial` → searches using default engine
- `how to install vim` → searches using default engine

### Configuration:
```ini
[search]
default_engine = duckduckgo  # or google, bing, startpage, searx
```

## UI Scaling for High DPI / Wayland

Creature Browser supports comprehensive UI scaling for better readability on high DPI displays and Wayland systems:

```ini
[ui]
# Overall UI scaling (1.25 = 25% larger, 1.5 = 50% larger)
scale_factor = 1.25

# Font size adjustment (+2 = 2 points larger)
font_size_adjustment = 2

# Font family (system, serif, sans-serif, monospace, or specific name)
font_family = "Ubuntu"

# Font weight and style
font_weight = normal
font_style = normal

# Force specific DPI (144 for high DPI displays)
force_dpi = 144

# Enable Qt's high DPI scaling
enable_high_dpi_scaling = True
```

**Quick fixes for small UI:**
- Set `scale_factor = 1.25` for 25% larger UI
- Set `font_size_adjustment = 3` for larger fonts
- Set `force_dpi = 144` for high DPI displays

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+G` | Focus URL bar (or open modal URL bar in minimal mode) |
| `Ctrl+X` | Exit browser |
| `Ctrl+N` | Open new window |
| `Ctrl+Shift+Right` | Switch to next tab |
| `Ctrl+Shift+Left` | Switch to previous tab |
| `Ctrl+T` | New tab (standard Qt shortcut) |
| `Ctrl+W` | Close tab (standard Qt shortcut) |
| `Alt+Home` | Navigate to home page |
| `F5` | Refresh page |
| `Alt+Left` | Back |
| `Alt+Right` | Forward |

## Themes

### Built-in Themes
- **light** - Clean, bright theme
- **dark** - Dark theme for reduced eye strain
- **nord** - Nordic-inspired color scheme
- **slate** - Professional gray/blue theme
- **earthy** - Warm brown tones
- **violet** - Rich purple theme
- **forest** - Deep green theme
- **autumn** - Warm orange theme

### Custom Themes

Create custom themes by adding `.ini` files to the `themes/` directory. See [docs/themes.md](docs/themes.md) for detailed instructions.

## Command Line Options

| Option | Description |
|--------|-------------|
| `url` | URL to open (positional argument) |
| `--profile, -p` | Specify profile to use |
| `--theme, -t` | Override theme for this session |
| `--new-window, -w` | Force new windows instead of tabs |
| `--minimal, -m` | Minimal mode: no tabs, menu, or navigation bar |
| `--no-profile-prompt` | Skip profile selection dialog |
| `--config, -c` | Use specific config file |

See [docs/command-line-usage.md](docs/command-line-usage.md) for complete usage information.

For all keyboard shortcuts, see [docs/keyboard-shortcuts.md](docs/keyboard-shortcuts.md).

For detailed UI scaling configuration, see [docs/ui-scaling.md](docs/ui-scaling.md).

For KeePassXC password manager integration, see [docs/keepassxc-integration.md](docs/keepassxc-integration.md).

## Advanced Usage

### System Installation

For system-wide access, copy the launcher script:

```bash
# Copy launcher script to system bin directory
sudo cp creature.sh /usr/local/bin/creature
sudo chmod +x /usr/local/bin/creature

# Now you can run from anywhere
creature --minimal
creature --profile work https://github.com
```

### Setting as Default Browser

1. Create a desktop entry file:
   ```bash
   cat > ~/.local/share/applications/creature.desktop << EOF
   [Desktop Entry]
   Name=Creature Browser
   Exec=/usr/local/bin/creature %u
   Type=Application
   Categories=Network;WebBrowser;
   MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;
   EOF
   ```

2. Set as default:
   ```bash
   xdg-settings set default-web-browser creature.desktop
   ```

### Multiple Profiles Workflow

```bash
# Launch different profiles in separate windows
python creature.py --profile work --new-window &
python creature.py --profile personal --new-window &
python creature.py --profile banking --new-window &
```

### Minimal Mode

For distraction-free browsing, use minimal mode:

```bash
# Clean interface with only bookmark sidebar and web content
python creature.py --minimal

# Minimal mode with specific URL and theme
python creature.py --minimal --theme dark https://example.com
```

**Minimal Mode Features:**
- No tab bar, menu, or navigation bar
- Vertical bookmark toolbar on the left
- Ctrl+G opens modal URL bar for navigation
- Ctrl+X exits the browser
- Perfect for focused reading or kiosk-style usage

### Bookmark Management

Bookmarks are stored per-profile with automatic favicon fetching:

- **Add bookmarks**: Click the "+" button in the bookmark toolbar
- **Edit bookmarks**: Right-click bookmark → Edit
- **Delete bookmarks**: Right-click bookmark → Delete
- **Hierarchical organization**: Support for bookmark folders
- **Favicon caching**: Automatic website icon fetching and caching

Bookmarks are stored in `~/.config/creature/profiles/<profile>/bookmarks.json`

## Development

### Project Structure

```
browser/
␜␀␀ creature.py          # Main application file
␜␀␀ creature_config.py   # Configuration management
␜␀␀ config.spec         # Configuration specification
␜␀␀ config.ini          # User configuration
␜␀␀ themes/             # Theme files
␂   ␜␀␀ theme.spec      # Theme specification
␂   ␜␀␀ light.ini       # Built-in themes
␂   ␜␀␀ dark.ini
␂   ␔␀␀ ...
␜␀␀ docs/               # Documentation
␂   ␜␀␀ command-line-usage.md
␂   ␔␀␀ themes.md
␔␀␀ pyproject.toml      # Project dependencies
```

### Adding New Features

1. Configuration options go in `config.spec`
2. Themes go in `themes/` directory
3. Follow existing code patterns for consistency

## Troubleshooting

### Common Issues

**"Cannot find config.spec"**
- Ensure you're running from the project directory
- Check file permissions

**Theme not loading**
- Verify theme file exists in `themes/`
- Check for syntax errors in theme file
- Ensure theme name matches filename (without .ini)

**Profile not persisting data**
- Check profile directory permissions
- Verify `~/.config/creature/` is writable

### Debug Mode

Run with Python warnings enabled:
```bash
python -W all creature.py
```

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License 

## Acknowledgments

- Built with PyQt6 and Qt WebEngine
- Configuration management via ConfigObj
