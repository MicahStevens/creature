# Command Line Usage

Creature Browser supports various command-line options for flexible usage and integration with your operating system.

## Basic Usage

```bash
# Launch browser with default settings
uv run python -m creature

# Open a specific URL
uv run python -m creature https://example.com

# Open URL with specific profile
uv run python -m creature https://github.com --profile work
```

## Command Line Arguments

### Positional Arguments

- `url` (optional) - URL to open when launching the browser
  ```bash
  uv run python -m creature https://www.google.com
  ```

### Optional Arguments

- `--profile, -p PROFILE` - Specify which profile to use
  ```bash
  uv run python -m creature --profile work
  uv run python -m creature -p personal
  ```

- `--theme, -t THEME` - Override the theme for this session
  ```bash
  uv run python -m creature --theme dark
  uv run python -m creature -t forest
  ```
  Available themes: light, dark, nord, slate, earthy, violet, forest, autumn

- `--no-profile-prompt` - Skip profile selection dialog (uses default profile)
  ```bash
  uv run python -m creature https://example.com --no-profile-prompt
  ```

- `--config, -c CONFIG` - Use a specific configuration file
  ```bash
  uv run python -m creature --config /path/to/config.ini
  ```

- `--profile-dir DIR` - Use a custom directory for profiles
  ```bash
  uv run python -m creature --profile-dir /custom/profile/path
  ```

## Profile Selection

When you open a URL without specifying a profile, Creature will show a profile selection dialog:

```bash
# This will prompt for profile selection
uv run python -m creature https://github.com

# This will use the 'work' profile directly
uv run python -m creature https://github.com --profile work

# This will use the default profile without prompting
uv run python -m creature https://github.com --no-profile-prompt
```

## Examples

### Development Workflow
```bash
# Open GitHub with work profile
uv run python -m creature https://github.com --profile work

# Open documentation with research profile in dark theme
uv run python -m creature https://docs.python.org --profile research --theme dark
```

### Personal Browsing
```bash
# Open social media with personal profile
uv run python -m creature https://twitter.com --profile personal

# Quick search without profile prompt
uv run python -m creature https://www.google.com --no-profile-prompt
```

### Multiple Windows
```bash
# Open different profiles in separate windows (each invocation creates a new window)
uv run python -m creature --profile work
uv run python -m creature --profile personal
```

## Environment Variables

- `CREATURE_CONFIG` - Path to configuration file (alternative to --config)
  ```bash
  export CREATURE_CONFIG=/home/user/custom-config.ini
  uv run python -m creature
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
uv run python -m creature "$@"
```

Make it executable: `chmod +x ~/bin/creature`

Now you can use: `creature https://example.com`