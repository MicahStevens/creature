# Configuration Guide

Creature Browser uses ConfigObj for flexible configuration management with validation and dot-notation access.

## Configuration File Locations

Creature searches for configuration in this order:

1. **Environment Variable**: `CREATURE_CONFIG`
   ```bash
   export CREATURE_CONFIG=/path/to/config.ini
   ```

2. **User Config Directory**: `~/.config/creature/config.ini`

3. **Current Directory**: `./config.ini`

If no configuration exists, Creature will create a default configuration with all available options.

## Configuration Structure

### General Settings

```ini
[general]
# Default theme for new windows
theme = light  # Options: light, dark, nord, slate, earthy, violet, forest, autumn

# Default home page
home_page = https://www.google.com

# Force new windows instead of tabs
force_new_window = False

# Default profile to use
default_profile = default

# Profile directory (relative to home or absolute path)
profile_directory = .config/creature
```

### Search Engine Configuration

The browser includes a smart URL bar that automatically detects whether your input is a URL or search query. When it detects a search query, it uses your configured search engines.

```ini
[search]
# Default search engine to use for queries
# Must match one of the search engine names below
default_engine = duckduckgo

# Search engine URLs - use %s as placeholder for the search query
# You can add, remove, or modify these as needed
google = https://www.google.com/search?q=%s
duckduckgo = https://duckduckgo.com/?q=%s
bing = https://www.bing.com/search?q=%s
startpage = https://www.startpage.com/sp/search?query=%s
searx = https://searx.org/?q=%s
```

#### Smart URL Detection

The browser automatically determines whether your input is a URL or search query:

**Recognized as URLs:**
- `github.com` → `https://github.com`
- `https://example.com` → loads directly
- `localhost:3000` → `https://localhost:3000`
- `192.168.1.1` → `https://192.168.1.1`
- `server.local` → `https://server.local` (local DNS)

**Treated as Search Queries:**
- `python tutorial` → searches using default engine
- `how to install vim` → searches using default engine
- `recipe for chocolate cake` → searches using default engine

#### Adding Custom Search Engines

You can add your own search engines by adding new entries to the `[search]` section:

```ini
[search]
# Custom search engines
wikipedia = https://en.wikipedia.org/wiki/Special:Search?search=%s
github = https://github.com/search?q=%s
stackoverflow = https://stackoverflow.com/search?q=%s
youtube = https://www.youtube.com/results?search_query=%s
reddit = https://www.reddit.com/search/?q=%s
arxiv = https://arxiv.org/search/?query=%s
```

**Important**: The `%s` placeholder is replaced with your search query (URL-encoded automatically).

#### Search Engine Examples

**Privacy-focused engines:**
```ini
duckduckgo = https://duckduckgo.com/?q=%s
startpage = https://www.startpage.com/sp/search?query=%s
searx = https://searx.org/?q=%s
```

**Regional/Language-specific:**
```ini
baidu = https://www.baidu.com/s?wd=%s
yandex = https://yandex.com/search/?text=%s
qwant = https://www.qwant.com/?q=%s
```

**Specialized searches:**
```ini
scholar = https://scholar.google.com/scholar?q=%s
images = https://www.google.com/search?tbm=isch&q=%s
news = https://news.google.com/search?q=%s
maps = https://www.google.com/maps/search/%s
```

#### Changing the Default Search Engine

To change which search engine is used by default:

1. Make sure the search engine is defined in the `[search]` section
2. Set `default_engine` to match the name exactly:

```ini
[search]
default_engine = google  # Use Google instead of DuckDuckGo
```

### UI Scaling Settings

```ini
[ui]
# UI scaling factor (1.0 = normal size)
# 1.25 = 25% larger, 1.5 = 50% larger, 2.0 = 200% (double size)
scale_factor = 1.0

# Font size adjustment in points
# 0 = normal, +3 = 3 points larger, -2 = 2 points smaller
font_size_adjustment = 0

# Force specific DPI value (0 = auto-detect)
# Common values: 96 (standard), 144 (1.5x), 192 (2x)
force_dpi = 0

# Enable Qt's automatic high DPI scaling
enable_high_dpi_scaling = True

# Font family selection
# Options: system, serif, sans-serif, monospace, or specific font name
font_family = system

# Font weight (normal, bold, light, or numeric 100-900)
font_weight = normal

# Font style (normal, italic, oblique)
font_style = normal
```

### Window Settings

```ini
[window]
# Initial window dimensions
width = 1400
height = 900

# Initial window position
x = 100
y = 100
```

### Browser Settings

```ini
[browser]
# Enable JavaScript
javascript_enabled = True

# Enable local storage
local_storage_enabled = True

# Enable plugins
plugins_enabled = True

# Tab close behavior
# Options: close_window, show_last_tab
tab_close_behavior = close_window
```

### Wayland Settings

```ini
[wayland]
# Wayland-specific compatibility settings
disable_window_decoration = False
auto_screen_scale_factor = True
disable_gpu_sandbox = True
disable_software_rasterizer = True
enable_vaapi_video_decoder = True
disable_sandbox = True
```

### Profile-Specific Settings

```ini
[profiles]
# Each subsection is a profile with custom settings

[[work]]
theme = dark
title_suffix = Work
home_page = https://github.com

[[personal]]
theme = nord
title_suffix = Personal
home_page = https://www.google.com

[[banking]]
theme = light
title_suffix = Banking
home_page = https://bank.example.com
```

## Complete Example Configuration

```ini
# Creature Browser Configuration

[general]
theme = dark
home_page = https://start.duckduckgo.com
force_new_window = False
default_profile = personal
profile_directory = .config/creature

[window]
width = 1600
height = 1000
x = 50
y = 50

[browser]
javascript_enabled = True
local_storage_enabled = True
plugins_enabled = True
tab_close_behavior = close_window

[wayland]
disable_window_decoration = False
auto_screen_scale_factor = True
disable_gpu_sandbox = True
disable_software_rasterizer = True
enable_vaapi_video_decoder = True
disable_sandbox = True

[profiles]
[[work]]
theme = slate
title_suffix = Work
home_page = https://github.com

[[personal]]
theme = forest
title_suffix = Personal
home_page = https://news.ycombinator.com

[[research]]
theme = dark
title_suffix = Research
home_page = https://scholar.google.com

[[banking]]
theme = light
title_suffix = Banking
home_page = ""

[[shopping]]
theme = autumn
title_suffix = Shopping
home_page = https://www.amazon.com
```

## Configuration Access in Code

The configuration uses dot notation for easy access:

```python
from creature_config import config

# Access general settings
theme = config.general.theme
home_page = config.general.home_page

# Access profile settings
work_theme = config.profiles.work.theme
work_home = config.profiles.work.home_page

# Modify settings
config.general.theme = "dark"
config.save()  # Save changes
```

## Environment-Specific Configurations

### Development Configuration

```ini
[general]
theme = dark
home_page = http://localhost:3000

[browser]
javascript_enabled = True
# Enable developer tools
```

### Production Configuration

```ini
[general]
theme = light
home_page = https://company.com

[browser]
javascript_enabled = True
plugins_enabled = False  # Disable plugins for security
```

## Tips and Best Practices

1. **Profile Organization**
   - Use descriptive profile names
   - Assign unique themes to each profile for visual identification
   - Set appropriate home pages for each context

2. **Security Considerations**
   - Disable unnecessary features for sensitive profiles (banking)
   - Use separate profiles for different security contexts
   - Consider disabling JavaScript for high-security profiles

3. **Performance Tuning**
   - Adjust Wayland settings based on your graphics setup
   - Disable unused features to reduce memory usage

4. **Backup Configuration**
   ```bash
   cp ~/.config/creature/config.ini ~/.config/creature/config.ini.backup
   ```

## Troubleshooting Configuration Issues

### Configuration Not Loading

1. Check file permissions:
   ```bash
   ls -la ~/.config/creature/config.ini
   ```

2. Verify syntax with Python:
   ```python
   from configobj import ConfigObj
   config = ConfigObj('config.ini')
   ```

### Invalid Values

If you see validation errors:
1. Check values match the types in `config.spec`
2. Ensure boolean values are True/False
3. Verify choice fields use allowed values

### Missing Profiles

If profiles aren't appearing:
1. Check indentation (use `[[profile_name]]` format)
2. Ensure profiles section exists
3. Verify no syntax errors above the profiles section

## Advanced Configuration

### Multiple Configuration Files

Use different configs for different purposes:

```bash
# Development
python creature.py --config dev-config.ini

# Testing
python creature.py --config test-config.ini

# Production
CREATURE_CONFIG=prod-config.ini python creature.py
```

### Configuration Templates

Create template configurations for different use cases:

```bash
# Create templates directory
mkdir config-templates

# Save different configurations
cp config.ini config-templates/developer.ini
cp config.ini config-templates/privacy-focused.ini
cp config.ini config-templates/minimal.ini
```

### Scripting Configuration Changes

```python
#!/usr/bin/env python3
from creature_config import CreatureConfig

# Load specific config
config = CreatureConfig()

# Modify settings
config.profiles.work.theme = "slate"
config.profiles.personal.theme = "forest"

# Save changes
config.save()
```