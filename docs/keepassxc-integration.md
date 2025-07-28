# KeePassXC Integration Guide

Creature Browser includes built-in integration with KeePassXC password manager, allowing you to securely fill login forms with your saved credentials. This is still a little clunky, but seems to generally work. #todo

## Prerequisites

1. **KeePassXC installed** with `keepassxc-cli` available in your PATH
2. **KeePassXC database** file (.kdbx) with your passwords
3. **Master password** to access your KeePassXC database

## Configuration

### Enable KeePassXC Integration

Edit your `config.ini` file and configure the KeePassXC section:

```ini
[keepassxc]
# Enable KeePassXC integration
enabled = true

# Path to your KeePassXC database file
database_path = ~/.config/keepassxc/passwords.kdbx

# Path to key file if you use one (optional)
key_file = ~/.config/keepassxc/keyfile.key

# Auto-search entries by current page URL
auto_search = true

# Show KeePassXC options in context menu
show_context_menu = true

# Clipboard timeout in seconds when copying credentials
clip_timeout = 10
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `enabled` | Enable/disable KeePassXC integration | `false` |
| `database_path` | Path to your .kdbx database file | (empty) |
| `key_file` | Path to key file for additional security | (empty) |
| `auto_search` | Automatically search entries by current URL | `true` |
| `show_context_menu` | Show KeePassXC options in right-click menu | `true` |
| `clip_timeout` | Seconds before clearing clipboard | `10` |

## How to Use

### Method 1: Context Menu (Recommended)

1. **Navigate to a login page** in your browser
2. **Right-click on any form field** (username, password, email, etc.)
3. **Select a KeePassXC option** from the context menu:
   - **Fill Username from KeePassXC** - Fill username/email fields
   - **Fill Password from KeePassXC** - Fill password fields
   - **Fill from KeePassXC** - Generic field filling with choice dialog
   - **Fill Login Form from KeePassXC** - Automatically fill entire login form
   - **Search KeePassXC Entries...** - Browse and select from all entries

4. **Enter your master password** when prompted (cached for session)
5. **Select an entry** if multiple matches are found
6. **Credentials are filled automatically**

### Method 2: Direct Form Filling

The **"Fill Login Form from KeePassXC"** option will:
- Automatically detect username and password fields
- Search your database for entries matching the current domain
- Fill both fields with one action
- Support email fields as username alternatives

## Features

### Smart Form Detection

The integration includes intelligent form field detection:

- **Password fields**: Detects `input[type="password"]`
- **Username fields**: Detects fields with names/IDs containing "user", "login", "account"
- **Email fields**: Detects `input[type="email"]` and fields containing "email", "mail"
- **Login forms**: Identifies forms containing password fields or login-related attributes

### URL-Based Search

When you use KeePassXC options:
1. The browser extracts the domain from the current URL
2. Searches your KeePassXC database for entries matching that domain
3. Presents matching entries for selection
4. Falls back to manual entry selection if no matches found

### Security Features

- **Master password caching**: Password is cached only for the browser session
- **Secure JavaScript injection**: All user input is properly escaped
- **No credential storage**: Browser never stores your actual passwords
- **Process isolation**: KeePassXC CLI runs in separate processes

## Supported Entry Formats

The integration works best with KeePassXC entries that include:

- **Title**: Descriptive name for the entry
- **Username**: Your login username
- **Password**: Your login password  
- **URL**: Website URL (helps with automatic matching)

### Example Entry Structure
```
Title: GitHub Account
Username: john.doe@example.com
Password: MySecurePassword123
URL: https://github.com
```

## Troubleshooting

### KeePassXC Integration Not Working

**Check prerequisites:**
```bash
# Verify keepassxc-cli is available
which keepassxc-cli

# Test database access
keepassxc-cli ls /path/to/your/database.kdbx
```

**Common issues:**

1. **"keepassxc-cli is not available"**
   - Install KeePassXC: `sudo apt install keepassxc` (Ubuntu/Debian)
   - Or download from: https://keepassxc.org/download/

2. **"Database file not found"**
   - Check the `database_path` in your config
   - Use absolute paths or proper `~` expansion
   - Verify file permissions

3. **"Invalid master password"**
   - Ensure you're entering the correct master password
   - Check if your database requires a key file

4. **Context menu not showing KeePassXC options**
   - Verify `enabled = true` in config
   - Check that `show_context_menu = true`
   - Right-click specifically on form fields (not empty space)

### JavaScript Bridge Issues

**If form filling doesn't work:**

1. **Check browser console** (F12 → Console) for JavaScript errors
2. **Verify script injection**: Look for "KeePassXC Bridge loaded successfully"
3. **Test on different websites**: Some sites may block script injection
4. **Clear browser cache**: Reload the page after configuration changes

### Database Access Issues

**Permission problems:**
```bash
# Check file permissions
ls -la ~/.config/keepassxc/passwords.kdbx

# Should be readable by your user
chmod 600 ~/.config/keepassxc/passwords.kdbx
```

**Key file issues:**
```bash
# If using key file, verify path and permissions
ls -la ~/.config/keepassxc/keyfile.key
chmod 600 ~/.config/keepassxc/keyfile.key
```

## Advanced Usage

### Multiple Databases

Currently, the integration supports one database per browser instance. For multiple databases:

1. **Use different browser profiles** with different KeePassXC configurations
2. **Switch database_path** in config and restart browser
3. **Use KeePassXC's database switching** within the KeePassXC application

### Custom Search Terms

The integration searches entries using:
- Domain name from current URL
- Entry titles containing the domain
- Entry URLs matching the domain

For better matching, ensure your KeePassXC entries have:
- Descriptive titles including site names
- Proper URL fields
- Consistent naming conventions

### Keyboard Shortcuts

While there are no built-in keyboard shortcuts for KeePassXC, you can:
1. **Use standard context menu shortcuts** (right-click)
2. **Navigate entry selection dialogs** with arrow keys and Enter
3. **Cancel operations** with Escape key

## Security Considerations

### Best Practices

1. **Use strong master passwords** for your KeePassXC database
2. **Enable database timeout** in KeePassXC settings
3. **Use key files** for additional security
4. **Keep KeePassXC updated** to latest version
5. **Backup your database** regularly

### What's Transmitted

- **Between browser and CLI**: Only search terms and entry names
- **No passwords in memory**: Credentials are retrieved only when needed
- **Secure cleanup**: Master password is cleared on browser close
- **No network transmission**: All communication is local

### Potential Risks

- **Malicious websites**: Could potentially exploit JavaScript injection
- **Process monitoring**: Other processes might observe CLI execution
- **Memory analysis**: Advanced attacks might extract cached passwords

**Mitigation**: The integration uses secure coding practices and limits exposure time.

## Limitations

### Current Limitations

1. **Single database support**: Only one database per browser instance
2. **CLI dependency**: Requires keepassxc-cli to be installed
3. **No TOTP support**: Two-factor authentication codes not supported
4. **Basic search**: Simple domain-based matching only

### Future Enhancements

Planned features for future versions:
- Multiple database support
- TOTP code generation
- Automatic form detection on page load
- Integration with KeePassXC browser protocol

## Support

For issues with:
- **KeePassXC integration**: Check this documentation and browser console
- **KeePassXC itself**: Visit https://keepassxc.org/docs/
- **General browser issues**: See main Creature Browser documentation

The integration is tested with KeePassXC 2.7+ and should work with most standard KeePassXC database configurations.