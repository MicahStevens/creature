# Creature Browser Configuration Specification

[general]
# Default theme for the browser
theme = option('light', 'dark', 'nord', 'slate', 'earthy', 'violet', 'forest', 'autumn', default='light')

# Default home page URL
home_page = string(default='https://www.google.com')

# Force new windows instead of tabs
force_new_window = boolean(default=False)

# Show splash screen on startup
show_splash_screen = boolean(default=True)

# Default profile to use
default_profile = string(default='default')

# Profile directory (relative to home or absolute path)
profile_directory = string(default='.config/creature')

[search]

# Search engines configuration - each engine has URL, shortcut, and default flag
# Use %s as placeholder for query in URLs
# Shortcuts: type in URL bar followed by space and query (e.g., 'g python tutorial')

[[google]]
url = string(default='https://www.google.com/search?q=%s')
shortcut = string(default='g')
default = boolean(default=False)

[[duckduckgo]]
url = string(default='https://duckduckgo.com/?q=%s')
shortcut = string(default='ddg')
default = boolean(default=True)

[[bing]]
url = string(default='https://www.bing.com/search?q=%s')
shortcut = string(default='b')
default = boolean(default=False)

[[kagi]]
url = string(default='https://kagi.com/search?q=%s')
shortcut = string(default='k')
default = boolean(default=False)

# Shopping and E-commerce
[[amazon]]
url = string(default='https://www.amazon.com/s?k=%s')
shortcut = string(default='a')
default = boolean(default=False)

[[ebay]]
url = string(default='https://www.ebay.com/sch/i.html?_nkw=%s')
shortcut = string(default='e')
default = boolean(default=False)

# Development and Technical
[[github]]
url = string(default='https://github.com/search?q=%s')
shortcut = string(default='gh')
default = boolean(default=False)

[[mdn]]
url = string(default='https://developer.mozilla.org/en-US/search?q=%s')
shortcut = string(default='mdn')
default = boolean(default=False)

[window]
# Initial window width
width = integer(min=600, max=4000, default=1400)

# Initial window height
height = integer(min=400, max=3000, default=900)

# Initial window X position
x = integer(default=100)

# Initial window Y position
y = integer(default=100)

[browser]
# Enable JavaScript
javascript_enabled = boolean(default=True)

# Enable local storage
local_storage_enabled = boolean(default=True)

# Enable plugins
plugins_enabled = boolean(default=True)

# Tab close behavior (close_window or show_last_tab)
tab_close_behavior = option('close_window', 'show_last_tab', default='close_window')

[wayland]
# Disable window decoration
disable_window_decoration = boolean(default=False)

# Auto screen scale factor
auto_screen_scale_factor = boolean(default=True)

# Disable GPU sandbox
disable_gpu_sandbox = boolean(default=True)

# Disable software rasterizer
disable_software_rasterizer = boolean(default=True)

# Enable Vaapi video decoder
enable_vaapi_video_decoder = boolean(default=True)

# Disable sandbox
disable_sandbox = boolean(default=True)

# Disable hardware acceleration (fixes black screen issues)
disable_hardware_acceleration = boolean(default=False)

[ui]
# UI scaling factor (1.0 = normal, 1.25 = 25% larger, etc.)
scale_factor = float(min=0.5, max=3.0, default=1.0)

# Font size adjustment (0 = normal, positive = larger, negative = smaller)
font_size_adjustment = integer(min=-10, max=20, default=0)

# Force Qt to use specific DPI value (0 = auto-detect)
force_dpi = integer(min=0, max=500, default=0)

# Enable high DPI scaling
enable_high_dpi_scaling = boolean(default=True)

# Font family (system, serif, sans-serif, monospace, or specific font name)
font_family = string(default='system')

# Font weight (normal, bold, light, or numeric 100-900)
font_weight = string(default='normal')

# Font style (normal, italic, oblique)
font_style = option('normal', 'italic', 'oblique', default='normal')

[keepassxc]
# Enable KeePassXC integration
enabled = boolean(default=False)

# Path to KeePassXC database file
database_path = string(default='')

# Path to key file (optional)
key_file = string(default='')

# Auto-search entries by current page URL
auto_search = boolean(default=True)

# Show KeePassXC options in context menu
show_context_menu = boolean(default=True)

# Clipboard timeout in seconds when copying credentials
clip_timeout = integer(min=0, max=300, default=10)

[logging]
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
level = option('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', default='WARNING')

# Profile sections are defined dynamically in the config file
# Each profile can have these settings:
# [profiles]
# [[profile_name]]
# theme = string
# title_suffix = string
# home_page = string
# webrtc_enabled = boolean(default=True)
# camera_enabled = boolean(default=True)
# microphone_enabled = boolean(default=True)
# screen_capture_enabled = boolean(default=True)
