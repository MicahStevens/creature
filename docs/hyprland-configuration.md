# Hyprland Configuration for Creature Browser

This document provides Hyprland window manager configuration for optimal Creature Browser experience.

## Splash Screen Configuration

To make the splash screen appear as a floating window in Hyprland, add the following rules to your `~/.config/hypr/hyprland.conf`:

```bash
# Creature Browser splash screen
windowrulev2 = float, class:^(creature)$, title:^(Creature Browser)$
windowrulev2 = center, class:^(creature)$, title:^(Creature Browser)$
windowrulev2 = stayfocused, class:^(creature)$, title:^(Creature Browser)$
windowrulev2 = pin, class:^(creature)$, title:^(Creature Browser)$

# Alternative rule for splash screen specifically
windowrulev2 = float, class:^(creature-splash)$
windowrulev2 = center, class:^(creature-splash)$
windowrulev2 = stayfocused, class:^(creature-splash)$
windowrulev2 = pin, class:^(creature-splash)$
```

## General Browser Configuration

For the main browser windows, you may want to add:

```bash
# Creature Browser main windows
windowrulev2 = workspace 2, class:^(creature)$, title:^(Creature Browser - )
windowrulev2 = maximize, class:^(creature)$, title:^(Creature Browser - )

# Optional: Set specific workspace for different profiles
windowrulev2 = workspace 2, class:^(creature)$, title:^(Creature Browser - work)
windowrulev2 = workspace 3, class:^(creature)$, title:^(Creature Browser - personal)
```

## Profile-Specific Rules

You can create workspace rules for different profiles:

```bash
# Work profile - Workspace 2
windowrulev2 = workspace 2, class:^(creature)$, title:^(Creature Browser - work)

# Personal profile - Workspace 3  
windowrulev2 = workspace 3, class:^(creature)$, title:^(Creature Browser - personal)

# Banking profile - Workspace 4 (more secure)
windowrulev2 = workspace 4, class:^(creature)$, title:^(Creature Browser - banking)
windowrulev2 = nofocus, class:^(creature)$, title:^(Creature Browser - banking)
```

## Application Launcher Integration

If using a launcher like rofi or dmenu, you can create desktop entries:

### ~/.local/share/applications/creature-work.desktop
```ini
[Desktop Entry]
Name=Creature Browser (Work)
Exec=/path/to/creature.py --profile work
Icon=/path/to/logo.png
Type=Application
Categories=Network;WebBrowser;
```

### ~/.local/share/applications/creature-personal.desktop
```ini
[Desktop Entry]
Name=Creature Browser (Personal)  
Exec=/path/to/creature.py --profile personal
Icon=/path/to/logo.png
Type=Application
Categories=Network;WebBrowser;
```

## Keybindings

Add custom keybindings to quickly launch different profiles:

```bash
# Launch different Creature Browser profiles
bind = $mainMod, B, exec, /path/to/creature.py --profile personal
bind = $mainMod SHIFT, B, exec, /path/to/creature.py --profile work
bind = $mainMod CTRL, B, exec, /path/to/creature.py --profile banking
```

## Troubleshooting

### Splash Screen Still Not Floating

If the splash screen still appears as a tiled window:

1. **Check window class**:
   ```bash
   hyprctl clients | grep creature
   ```

2. **Add more specific rules**:
   ```bash
   # Try different class matching
   windowrulev2 = float, class:^(python)$, title:^(Creature Browser)$
   windowrulev2 = center, class:^(python)$, title:^(Creature Browser)$
   ```

3. **Disable splash screen** if problematic:
   ```ini
   # In your config.ini
   [general]
   show_splash_screen = False
   ```

### Window Manager Detection Issues

If Hyprland doesn't recognize the windows properly:

1. **Set Qt platform explicitly**:
   ```bash
   export QT_QPA_PLATFORM=wayland
   /path/to/creature.py
   ```

2. **Use X11 backend if needed**:
   ```bash
   export QT_QPA_PLATFORM=xcb
   /path/to/creature.py
   ```

## Complete Example Configuration

Here's a complete section for your `hyprland.conf`:

```bash
# ===== Creature Browser Configuration =====

# Splash screen - floating and centered
windowrulev2 = float, class:^(creature)$, title:^(Creature Browser)$
windowrulev2 = center, class:^(creature)$, title:^(Creature Browser)$
windowrulev2 = stayfocused, class:^(creature)$, title:^(Creature Browser)$
windowrulev2 = pin, class:^(creature)$, title:^(Creature Browser)$

# Main browser windows - workspace assignment
windowrulev2 = workspace 2, class:^(creature)$, title:^(Creature Browser - work)
windowrulev2 = workspace 3, class:^(creature)$, title:^(Creature Browser - personal)
windowrulev2 = workspace 4, class:^(creature)$, title:^(Creature Browser - banking)

# Keybindings for quick access
bind = $mainMod, B, exec, /path/to/creature.py --profile personal
bind = $mainMod SHIFT, B, exec, /path/to/creature.py --profile work  
bind = $mainMod CTRL, B, exec, /path/to/creature.py --profile banking

# ===== End Creature Browser Configuration =====
```

## Notes

- Replace `/path/to/creature.py` with the actual path to your Creature Browser executable
- Adjust workspace numbers to match your preferred layout
- The `$mainMod` variable is typically set to your Super/Windows key
- Reload Hyprland configuration with `hyprctl reload` after making changes

This configuration should provide a seamless Creature Browser experience with proper splash screen floating behavior in Hyprland.