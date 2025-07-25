# UI Scaling Guide

Creature Browser provides comprehensive UI scaling options to ensure optimal readability and usability across different display types and environments.

## Why UI Scaling Matters

- **High DPI Displays**: Modern displays often have very high pixel density, making default UI elements appear tiny
- **Wayland Scaling**: Some Wayland environments don't handle application scaling automatically
- **Accessibility**: Users may need larger fonts or UI elements for better visibility
- **Personal Preference**: Some users prefer larger or smaller interface elements

## Configuration Options

### Scale Factor

```ini
[ui]
scale_factor = 1.25  # 25% larger than normal
```

**Values:**
- `1.0` - Normal size (default)
- `1.25` - 25% larger (recommended for high DPI)
- `1.5` - 50% larger
- `2.0` - Double size
- `0.8` - 20% smaller (for large displays)

**What it affects:**
- Button sizes and padding
- Input field heights
- Tab dimensions
- Toolbar spacing
- Overall widget sizing

### Font Size Adjustment

```ini
[ui]
font_size_adjustment = 2  # 2 points larger
```

**Values:**
- `0` - Normal font size (default)
- `+3` - 3 points larger
- `-2` - 2 points smaller
- Range: -10 to +20 points

**What it affects:**
- All text in the interface
- Menu text
- Button labels
- URL bar text

### Force DPI

```ini
[ui]
force_dpi = 144  # Force 150% DPI scaling
```

**Common values:**
- `0` - Auto-detect (default)
- `96` - Standard DPI (100% scaling)
- `120` - 125% scaling
- `144` - 150% scaling
- `192` - 200% scaling

**When to use:**
- When Qt's auto-detection fails
- For consistent scaling across different displays
- When you know your display's exact DPI

### High DPI Scaling

```ini
[ui]
enable_high_dpi_scaling = True
```

**Options:**
- `True` - Enable Qt's automatic high DPI scaling (default)
- `False` - Disable automatic scaling

**When to disable:**
- If you experience scaling issues
- If you prefer manual control
- For debugging display problems

### Font Family

```ini
[ui]
font_family = "Ubuntu"
```

**Options:**
- `system` - Use system default font (default)
- `serif` - Generic serif font (Times-style)
- `sans-serif` - Generic sans-serif font (Arial-style)
- `monospace` - Generic monospace font (Courier-style)
- `"Specific Font Name"` - Use a specific installed font

**Examples:**
- `font_family = "Roboto"`
- `font_family = "Source Code Pro"`
- `font_family = "Noto Sans"`
- `font_family = "Inter"`

### Font Weight

```ini
[ui]
font_weight = bold
```

**Options:**
- `normal` - Regular weight (default)
- `bold` - Bold weight
- `light` - Light weight
- `100-900` - Numeric weight (CSS-style)

**Numeric weights:**
- `100-200` - Thin
- `300` - Light
- `400` - Normal
- `500` - Medium
- `600` - Semi-bold
- `700` - Bold
- `800-900` - Extra bold

### Font Style

```ini
[ui]
font_style = italic
```

**Options:**
- `normal` - Regular style (default)
- `italic` - Italic style
- `oblique` - Oblique style

## Common Scenarios

### Small UI on High DPI Display

**Problem**: Everything appears tiny on a 4K monitor or high DPI laptop.

**Solution**:
```ini
[ui]
scale_factor = 1.5
font_size_adjustment = 2
enable_high_dpi_scaling = True
```

### Wayland Scaling Issues

**Problem**: UI doesn't scale properly on Wayland desktop environment.

**Solution**:
```ini
[ui]
scale_factor = 1.25
force_dpi = 144
```

### Text Too Small

**Problem**: Interface size is okay, but text is hard to read.

**Solution**:
```ini
[ui]
font_size_adjustment = 4
```

### Interface Too Large

**Problem**: UI elements are too big and waste screen space.

**Solution**:
```ini
[ui]
scale_factor = 0.85
font_size_adjustment = -1
```

### Font Readability Issues

**Problem**: Default system font is hard to read or looks unprofessional.

**Solution**:
```ini
[ui]
font_family = "Inter"
font_weight = 500
font_size_adjustment = 1
```

### Programming/Technical Use

**Problem**: Need a monospace font for technical work.

**Solution**:
```ini
[ui]
font_family = "Source Code Pro"
font_weight = normal
```

### Accessibility - Dyslexia Friendly

**Problem**: Need a font that's easier for dyslexic users to read.

**Solution**:
```ini
[ui]
font_family = "OpenDyslexic"
font_weight = normal
font_size_adjustment = 2
```

### Mixed Display Setup

**Problem**: Using multiple displays with different DPI.

**Solution**:
```ini
[ui]
force_dpi = 120  # Use middle-ground DPI
scale_factor = 1.0
enable_high_dpi_scaling = False
```

## Testing and Adjustment

### Step-by-Step Process

1. **Start with defaults**: Begin with all values at default
2. **Identify the issue**: Is text too small? Are buttons too small? Both?
3. **Make small adjustments**: Change one setting at a time
4. **Restart required**: UI scaling changes require restarting the browser
5. **Fine-tune**: Adjust until comfortable

### Recommended Starting Points

**For 1080p displays (24" or smaller):**
```ini
scale_factor = 1.0
font_size_adjustment = 0
```

**For 1440p displays:**
```ini
scale_factor = 1.15
font_size_adjustment = 1
```

**For 4K displays:**
```ini
scale_factor = 1.5
font_size_adjustment = 2
```

**For very large displays (32"+):**
```ini
scale_factor = 1.25
font_size_adjustment = 3
```

## Environment Variables

Creature Browser also sets Qt environment variables based on your configuration:

- `QT_SCALE_FACTOR` - Overall application scaling
- `QT_FONT_DPI` - Font DPI override
- `QT_ENABLE_HIGHDPI_SCALING` - High DPI support

These are set automatically based on your config, but you can override them:

```bash
QT_SCALE_FACTOR=1.25 python creature.py
```

## Troubleshooting

### Changes Don't Apply

**Solution**: Restart the browser completely. UI scaling is applied at startup.

### Mixed Scaling

**Problem**: Some elements scale, others don't.

**Cause**: Qt WebEngine (the web content) uses different scaling than the UI.

**Solution**: Use `scale_factor` instead of environment variables.

### Blurry Text

**Problem**: Fonts appear blurry after scaling.

**Solutions**:
1. Try `font_size_adjustment` instead of `scale_factor`
2. Use exact DPI values: `force_dpi = 144`
3. Disable high DPI scaling: `enable_high_dpi_scaling = False`

### Performance Impact

**Problem**: UI feels slow with scaling enabled.

**Solutions**:
1. Use `font_size_adjustment` for text-only scaling
2. Reduce `scale_factor` value
3. Check graphics drivers

## Per-Profile Scaling

Currently, UI scaling is global. Future versions may support per-profile scaling for users who switch between different display environments.

## Advanced Configuration

### Custom CSS Scaling

For advanced users, you can create custom themes with specific sizing. See the themes documentation for details.

### System Integration

Consider setting environment variables in your desktop environment's startup files for consistent scaling across all Qt applications:

```bash
# In ~/.profile or ~/.bashrc
export QT_SCALE_FACTOR=1.25
export QT_ENABLE_HIGHDPI_SCALING=1
```