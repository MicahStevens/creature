# Theme Configuration Specification

[metadata]
name = string()
description = string(default="")
author = string(default="")
version = string(default="1.0.0")

[colors]
# Window and background colors
window_bg = string()
button_bg = string()
text_color = string()
url_bar_bg = string()
accent = string()

# Additional colors for better customization
tab_bg = string(default="")
tab_active_bg = string(default="")
tab_hover_bg = string(default="")
toolbar_bg = string(default="")
border_color = string(default="")

# Status colors
success = string(default="#4caf50")
warning = string(default="#ff9800")
error = string(default="#f44336")
info = string(default="#2196f3")

[window]
# Window styling options
border_radius = integer(min=0, max=20, default=0)
opacity = float(min=0.5, max=1.0, default=1.0)

[ui_elements]
# Border radius settings for UI elements (in pixels)
button_radius = integer(min=0, max=20, default=4)
input_radius = integer(min=0, max=20, default=4)
tab_radius = integer(min=0, max=20, default=6)
menu_radius = integer(min=0, max=20, default=4)
dialog_radius = integer(min=0, max=20, default=8)
toolbar_radius = integer(min=0, max=20, default=0)