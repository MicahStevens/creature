# Bug Fixes

This document tracks recent bug fixes applied to Creature Browser.

## Fixed Issues

### 1. Font Size Growth on Theme Changes

**Issue**: Font size increased cumulatively each time a theme was changed via the Theme menu.

**Root Cause**: 
- Multiple font sizing layers were applying adjustments cumulatively
- `QFont()` was returning different base sizes depending on current application font
- Stylesheet font-size was being applied on top of existing scaling

**Fix Applied**:
```python
class ThemeManager:
    def __init__(self):
        # Store the original system font size to prevent cumulative scaling
        system_font = QFont()
        self.original_font_size = system_font.pointSize()
        if self.original_font_size <= 0:
            self.original_font_size = 12  # Fallback

    def apply_ui_scaling(self, app):
        # Always use the original system font size as the base
        base_font_size = self.original_font_size
        final_font_size = base_font_size + ui_config.font_size_adjustment
        
        # Clear existing stylesheet first
        app.setStyleSheet("")
        
        # Apply scaling from consistent baseline
        scaled_font_size = int(final_font_size * scale_factor)
```

**Result**: Theme changes now maintain consistent font size.

### 2. KeePassXC Context Menu Crash

**Issue**: Right-clicking on web pages caused application crash with:
```
AttributeError: 'QWebEnginePage' object has no attribute 'createStandardContextMenu'
```

**Root Cause**: 
- `createStandardContextMenu()` method doesn't exist in PyQt6's QWebEnginePage
- This is a PyQt5 → PyQt6 compatibility issue

**Fix Applied**:
```python
def contextMenuEvent(self, event):
    # Create our own context menu since PyQt6 doesn't have createStandardContextMenu
    from PyQt6.QtWidgets import QMenu
    menu = QMenu(self)
    
    # Add basic browser actions
    back_action = QAction("Back", self)
    back_action.setEnabled(self.page().history().canGoBack())
    back_action.triggered.connect(self.back)
    menu.addAction(back_action)
    
    # Add forward, reload actions...
    
    # Add KeePassXC options conditionally
    if keepass_manager.enabled and keepass_manager.config.show_context_menu:
        # Add KeePassXC form filling options
```

**Result**: Context menu now works properly with both browser actions and KeePassXC integration.

## Technical Details

### Font Scaling Fix

The key insight was that we needed to capture the original system font size **before any scaling** was applied and store it as a reference point. Each theme change now:

1. Starts from the stored original font size
2. Applies font_size_adjustment from that baseline
3. Applies scale_factor from the adjusted size
4. Clears existing stylesheets to prevent accumulation

### Context Menu Fix

PyQt6 removed several convenience methods from PyQt5. The solution was to:

1. Create our own QMenu instead of relying on createStandardContextMenu()
2. Add basic browser functionality (Back, Forward, Reload)
3. Conditionally add KeePassXC options based on configuration
4. Properly handle element detection via JavaScript

## Testing

Both fixes have been tested to ensure:

### Font Scaling
- ✅ Multiple theme changes don't increase font size
- ✅ Font size respects font_size_adjustment setting
- ✅ Scale factor applies correctly
- ✅ All UI elements maintain consistent sizing

### Context Menu
- ✅ Right-click no longer crashes the application
- ✅ Basic browser actions (Back/Forward/Reload) work
- ✅ KeePassXC options appear when enabled
- ✅ Context menu works on both form fields and regular content

## Prevention

To prevent similar issues in the future:

### Font Management
- Always store baseline values before applying transformations
- Clear accumulated state (stylesheets) before reapplying
- Use consistent calculation methods across theme changes

### PyQt6 Compatibility
- Check PyQt6 documentation for method availability
- Test context menus and UI interactions thoroughly
- Provide fallbacks for removed convenience methods

These fixes ensure a stable, consistent user experience when changing themes and using KeePassXC integration features.