![Creature](./splash2.png)
# Creature Browser

A web browser built with PyQt6 that supports multiple isolated profiles, custom themes, and flexible configuration options.

## Features

- **Profile Isolation** - Complete separation of cookies, storage, and cache between profiles. I wanted to have seperate work/personal profiles that could be initiated from the command line
- **Custom Themes** - 8 built-in themes with support for custom theme creation
- **Per-Profile Configuration** - Different themes, home pages, and settings for each profile
- **Profile Selection Dialog** - Smart profile picker when opening URLs without specifying a particular profile. This supports using this as default browser and still allow use of profiles. 
- **Bookmark Toolbar** - Per-profile bookmark sidebar with favicon support and hierarchical organization, compatible with Firefox JSON formatted bookmarks. 
- **Minimal Mode** - Distraction-free browsing with no tabs, menu, or navigation bar (--minimal flag)
- **KeePassXC Integration** - Secure password manager integration with context menu support via keepassxc-cli
- **Wayland Support** - Targeted for use in Hyprland, so wayland support is key. 
- **ConfigObj Integration** - Flexible configuration with validation


# Documentation
- [Installation, quickstart](docs/quickstart.md)
- [Command Line Usage](docs/command-line-usage.md)
- [Configuration Files](docs/configuration.md)
- [Keyboard-shortcuts](docs/keyboard-shortcuts.md)
- [UI scaling](docs/ui-scaling.md)
- [KeepassXC Integration](docs/keepassxc-integration.md)
- [Hyprland Notes](docs/hyprland-configuration.md)
- [Themes](docs/themes.md)

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
- Lots of Claude Code work
