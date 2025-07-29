# Quick Start Guide

Get up and running with Creature Browser in minutes!

## Installation (using uv)

```bash
# Clone the repository
git clone <repository-url>
cd browser

# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv

# Activate it
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
uv pip install -e .
```

## First Run

```bash
# Launch the browser
uv run python -m creature
```

This will:
1. Create default configuration in `~/.config/creature/config.ini`
2. Create a default profile
3. Open the browser with the default theme

## Basic Usage Examples

### Open a Website
```bash
uv run python -m creature https://github.com
```

### Use Different Profiles
```bash
# Work profile
uv run python -m creature https://github.com --profile work

# Personal browsing
uv run python -m creature https://reddit.com --profile personal
```

### Change Themes
```bash
# Dark theme for late night
uv run python -m creature --theme dark

# Forest theme for relaxed browsing
uv run python -m creature --theme forest
```

## Setting Up Profiles

### Quick Profile Setup

1. Launch with a new profile:
   ```bash
   uv run python -m creature --profile work
   ```

2. Or use the profile dialog:
   ```bash
   uv run python -m creature https://github.com
   # Select "Create New" in the dialog
   ```

### Configure Profile Themes

Edit `~/.config/creature/config.ini`:

```ini
[profiles]
[[work]]
theme = slate
title_suffix = Work

[[personal]]
theme = forest
title_suffix = Personal

[[banking]]
theme = light
title_suffix = Banking
```

## Keyboard Shortcuts

- `Ctrl+G` - Focus URL bar and select all text
- `Ctrl+N` - Open new window
- `Ctrl+Shift+Right` - Switch to next tab
- `Ctrl+Shift+Left` - Switch to previous tab
- `Ctrl+T` - New tab (when tabs enabled)
- `Ctrl+W` - Close tab
- `Alt+Left` - Back
- `Alt+Right` - Forward
- `F5` - Refresh

## Common Workflows

### Multiple Profiles Open
```bash
# Open different profiles in separate windows
uv run python -m creature --profile work &
uv run python -m creature --profile personal &
```

### Quick Research Session
```bash
# Open with a temporary profile
uv run python -m creature --profile research --theme dark https://scholar.google.com
```

### Privacy-Focused Browsing
```bash
# Create a privacy profile with specific settings
uv run python -m creature --profile private
```

## Making Creature Your Default Browser

### Linux (Desktop Entry)

1. Create the desktop file:
   ```bash
   cat > ~/.local/share/applications/creature.desktop << 'EOF'
   [Desktop Entry]
   Name=Creature Browser
   Comment=Privacy-focused browser with profiles
   Exec=/path/to/your/venv/bin/python /path/to/creature.py %u
   Terminal=false
   Type=Application
   Icon=web-browser
   Categories=Network;WebBrowser;
   MimeType=text/html;text/xml;application/xhtml+xml;x-scheme-handler/http;x-scheme-handler/https;
   EOF
   ```

2. Update the Exec path to match your installation

3. Set as default:
   ```bash
   xdg-settings set default-web-browser creature.desktop
   ```

### Create a Shell Alias

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
alias creature='cd /path/to/browser && source .venv/bin/activate && python creature.py'
```

Then use:
```bash
creature https://example.com
```

## Next Steps

- Read the [themes documentation](themes.md) to customize appearance
- Check [command-line usage](command-line-usage.md) for all options
- See [configuration guide](configuration.md) for advanced settings

## Troubleshooting

### Browser Won't Start

1. Check Python version:
   ```bash
   python --version  # Should be 3.13+
   ```

2. Verify dependencies:
   ```bash
   uv pip list
   ```

3. Check for errors:
   ```bash
   uv run python -m creature 2>&1 | less
   ```

### Profile Selection Dialog Not Appearing

- Make sure you're providing a URL
- Don't use `--profile` or `--no-profile-prompt` flags

### Theme Not Applying

1. Check theme exists:
   ```bash
   ls themes/
   ```

2. Verify theme name:
   ```bash
   python creature.py --theme dark  # Not "dark.ini"
   ```

