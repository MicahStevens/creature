# Keyboard Shortcuts

Creature Browser supports various keyboard shortcuts for efficient navigation and control.

## URL Bar and Search

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+G` | Focus URL bar | Focuses the URL bar and selects all text for quick typing |

**Usage**: Press `Ctrl+G` to quickly jump to the URL bar from anywhere in the browser. All existing text will be selected, so you can immediately start typing a new URL or search query.

## Window and Tab Management

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+N` | New window | Open a new browser window with the same profile |
| `Ctrl+Shift+Right` | Next tab | Switch to the next tab (cycles to first tab after last) |
| `Ctrl+Shift+Left` | Previous tab | Switch to the previous tab (cycles to last tab before first) |
| `Ctrl+T` | New tab | Create a new tab (standard Qt shortcut) |
| `Ctrl+W` | Close tab | Close the current tab (standard Qt shortcut) |

**New Window**: `Ctrl+N` opens a new browser window using the same profile as the current window. This is useful for:
- Separating different tasks into different windows
- Working with multiple contexts simultaneously
- Better window management on multi-monitor setups

**Tab Cycling**: The tab shortcuts cycle through tabs in order. If you're on the last tab and press `Ctrl+Shift+Right`, you'll go to the first tab.

## Navigation

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Alt+Left` | Back | Go back in browser history |
| `Alt+Right` | Forward | Go forward in browser history |
| `F5` | Refresh | Reload the current page |
| `Enter` | Navigate | In URL bar, navigate to URL or search |

## Profile Management

Currently, profile switching must be done through the profile selection dialog or command-line arguments. Future versions may include keyboard shortcuts for profile switching.

## Customization

Currently, keyboard shortcuts are hardcoded. Future versions may support:
- Custom shortcut configuration
- Profile-specific shortcuts
- Additional navigation shortcuts

## Standard Qt Shortcuts

These shortcuts work automatically due to Qt's built-in functionality:
- `Ctrl+C` - Copy selected text
- `Ctrl+V` - Paste text
- `Ctrl+A` - Select all text (in URL bar or web page)
- `Ctrl+Z` - Undo (in text fields)



## Platform Differences

- **Linux**: All shortcuts work as documented
- **Windows**: Should work the same, but untested (Qt handles platform differences)
- **macOS**: `Cmd` key may be used instead of `Ctrl` (Qt handles this automatically - UNTESTED)