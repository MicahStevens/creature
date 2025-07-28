# Command Line Usage

Creature Browser supports various command-line options for flexible usage and integration with your operating system.

## Basic Usage

```bash
# Launch browser with default settings
uv run creature.py

# Open a specific URL
uv run creature.py https://example.com

# Open URL with specific profile
uv run creature.py https://github.com --profile work
```

## Command Line Arguments

### Positional Arguments

- `url` (optional) - URL to open when launching the browser
  ```bash
  uv run creature.py https://www.google.com
  ```

### Optional Arguments

- `--profile, -p PROFILE` - Specify which profile to use
  ```bash
  uv run creature.py --profile work
  uv run creature.py -p personal
  ```

- `--theme, -t THEME` - Override the theme for this session
  ```bash
  uv run creature.py --theme dark
  uv run creature.py -t forest
  ```
  Available themes: light, dark, nord, slate, earthy, violet, forest, autumn

- `--new-window, -w` - Force new windows instead of tabs
  ```bash
  uv run creature.py --new-window
  uv run creature.py -w https://example.com
  ```

- `--no-profile-prompt` - Skip profile selection dialog (uses default profile)
  ```bash
  uv run creature.py https://example.com --no-profile-prompt
  ```

- `--config, -c CONFIG` - Use a specific configuration file
  ```bash
  uv run creature.py --config /path/to/config.ini
  ```

- `--profile-dir DIR` - Use a custom directory for profiles
  ```bash
  uv run creature.py --profile-dir /custom/profile/path
  ```

## Profile Selection

When you open a URL without specifying a profile, Creature will show a profile selection dialog:

```bash
# This will prompt for profile selection
uv run creature.py https://github.com

# This will use the 'work' profile directly
uv run creature.py https://github.com --profile work

# This will use the default profile without prompting
uv run creature.py https://github.com --no-profile-prompt
```

## Examples

### Development Workflow
```bash
# Open GitHub with work profile
uv run creature.py https://github.com --profile work

# Open documentation with research profile in dark theme
uv run creature.py https://docs.python.org --profile research --theme dark
```

### Personal Browsing
```bash
# Open social media with personal profile
uv run creature.py https://twitter.com --profile personal

# Quick search without profile prompt
uv run creature.py https://www.google.com --no-profile-prompt
```

### Multiple Windows
```bash
# Force separate windows for different contexts
uv run creature.py --profile work --new-window
uv run creature.py --profile personal --new-window
```

## Environment Variables

- `CREATURE_CONFIG` - Path to configuration file (alternative to --config)
  ```bash
  export CREATURE_CONFIG=/home/user/custom-config.ini
  uv run creature.py
  ```

## Integration with OS

### Linux Desktop Entry

Create a `.desktop` file for system integration:

```desktop
[Desktop Entry]
Name=Creature Browser
Comment=Privacy-focused browser with profile support
Exec=/path/to/uv run /path/to/creature.py %u
Terminal=false
Type=Application
Icon=/path/to/icon.png
Categories=Network;WebBrowser;
MimeType=text/html;text/xml;application/xhtml+xml;x-scheme-handler/http;x-scheme-handler/https;
```

### Setting as Default Browser

1. Save the `.desktop` file to `~/.local/share/applications/creature.desktop`
2. Run: `xdg-settings set default-web-browser creature.desktop`

### URL Handler Script

Create a wrapper script for easier URL handling:

```bash
#!/bin/bash
# Save as ~/bin/creature
cd /path/to/creature/directory
uv run creature.py "$@"
```

Make it executable: `chmod +x ~/bin/creature`

Now you can use: `creature https://example.com`