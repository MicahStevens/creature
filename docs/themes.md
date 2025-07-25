# Themes Documentation

Creature Browser supports a flexible theming system that allows you to customize the appearance of your browser windows. Themes can be applied globally, per-profile, or per-session.

## Available Themes

### Built-in Themes

1. **Light** - Clean, bright theme for daytime use
2. **Dark** - Dark theme for reduced eye strain
3. **Nord** - Arctic, north-bluish color palette
4. **Slate** - Sophisticated slate gray with blue undertones
5. **Earthy** - Warm browns and natural earth tones
6. **Violet** - Rich, saturated purple theme
7. **Forest** - Deep forest green inspired by woodlands
8. **Autumn** - Warm orange and amber tones

## Using Themes

### Global Theme Setting

Set a default theme in `config.ini`:

```ini
[general]
theme = dark
```

### Per-Profile Themes

Configure different themes for each profile:

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

### Command Line Override

Override theme for a single session:

```bash
python creature.py --theme violet
```

## Creating Custom Themes

### Theme File Structure

Themes are stored in the `themes/` directory as `.ini` files. Here's the structure:

```ini
# themes/custom.ini

[metadata]
name = "Custom Theme"
description = "My custom theme"
author = "Your Name"
version = "1.0.0"

[colors]
# Core colors
window_bg = "#2b2b2b"      # Main window background
button_bg = "#404040"      # Button background
text_color = "#ffffff"     # Primary text color
url_bar_bg = "#353535"     # URL bar background
accent = "#0078d4"         # Accent color (links, highlights)

# Tab colors
tab_bg = "#323232"         # Inactive tab background
tab_active_bg = "#404040"  # Active tab background
tab_hover_bg = "#383838"   # Tab hover state
toolbar_bg = "#2b2b2b"     # Toolbar background
border_color = "#1a1a1a"   # Border colors

# Status colors
success = "#4caf50"        # Success messages
warning = "#ff9800"        # Warning messages
error = "#f44336"          # Error messages
info = "#2196f3"           # Info messages

[window]
border_radius = 0          # Window border radius (0-20)
opacity = 1.0              # Window opacity (0.5-1.0)
```

### Color Guidelines

1. **Contrast** - Ensure sufficient contrast between text and background
2. **Consistency** - Use a cohesive color palette
3. **Accessibility** - Consider users with visual impairments
4. **Purpose** - Use color to convey meaning (red for errors, green for success)

### Creating a New Theme

1. Create a new `.ini` file in the `themes/` directory:
   ```bash
   touch themes/mytheme.ini
   ```

2. Copy the structure from an existing theme and modify colors:
   ```bash
   cp themes/dark.ini themes/mytheme.ini
   ```

3. Edit the theme file with your preferred colors

4. The theme will be automatically available after restarting the browser

## Theme Examples

### Minimalist Light Theme
```ini
[colors]
window_bg = "#fafafa"
button_bg = "#e0e0e0"
text_color = "#212121"
url_bar_bg = "#ffffff"
accent = "#1976d2"
```

### High Contrast Theme
```ini
[colors]
window_bg = "#000000"
button_bg = "#ffffff"
text_color = "#ffffff"
url_bar_bg = "#000000"
accent = "#ffff00"
```

### Solarized Dark Theme
```ini
[colors]
window_bg = "#002b36"
button_bg = "#073642"
text_color = "#839496"
url_bar_bg = "#073642"
accent = "#268bd2"
```

## Profile Identification

Themes help identify different browser profiles at a glance:

- **Work Profile** - Use a professional theme (Slate)
- **Personal Profile** - Use a relaxed theme (Forest)
- **Banking Profile** - Use a high-visibility theme (Light)
- **Development Profile** - Use a dark theme (Dark or Violet)

## Theme Configuration Tips

1. **Profile Association** - Assign distinct themes to different profiles for easy visual identification
2. **Time of Day** - Use lighter themes during day, darker at night
3. **Task-Based** - Choose themes that match your activity (calm for reading, vibrant for creative work)
4. **Consistency** - Use similar themes across profiles if you prefer a uniform experience

## Troubleshooting

### Theme Not Loading

1. Check file name ends with `.ini`
2. Verify file is in `themes/` directory
3. Ensure valid INI syntax
4. Check color values are valid hex codes

### Theme Looks Wrong

1. Verify all required color keys are present
2. Check color contrast ratios
3. Ensure hex color format is correct (#RRGGBB)

### Creating Theme Variants

To create variations of existing themes:

```bash
# Copy and modify
cp themes/dark.ini themes/dark-blue.ini
# Edit to change accent colors
```

## Advanced Theming

### Dynamic Theme Switching

You can switch themes programmatically by modifying the config:

```python
# In your scripts
config.profiles.work.theme = "dark"
config.save()
```

### Theme Inheritance

While not directly supported, you can create theme families by copying base themes and modifying specific colors:

```bash
# Create a theme family
cp themes/dark.ini themes/dark-red.ini
cp themes/dark.ini themes/dark-green.ini
cp themes/dark.ini themes/dark-blue.ini
```

Then modify only the accent colors in each variant.